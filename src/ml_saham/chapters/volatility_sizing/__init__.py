"""Ch.10 Volatility sizing — realized vol + position scale demo."""

from __future__ import annotations

import math

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles

META = get_meta("volatility-sizing")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Volatilitas historis membantu skala ukuran posisi — bukan prediksi arah.",
        "",
        "Opsi pendekatan",
        "  1) Realized vol rolling → target risk parity kasar (1/vol)",
        "  2) RandomForest prediksi |return| besok vs naive lag-vol",
        "  3) Bandingkan sizing equal-weight vs vol-scaled",
        "",
        "Caveat",
        "  • Vol clustering — model sederhana mudah overfit",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: gunakan IHSG atau ticker likuid dari universe.")
    return "\n".join(lines)


def _realized_vol(closes: list[float], window: int = 20) -> list[float | None]:
    rets = [0.0] + [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    out: list[float | None] = [None] * len(closes)
    for i in range(window, len(closes)):
        chunk = rets[i - window + 1 : i + 1]
        mean = sum(chunk) / len(chunk)
        var = sum((x - mean) ** 2 for x in chunk) / len(chunk)
        out[i] = math.sqrt(var) if var > 0 else 0.0
    return out


def _build_series(conn, ticker: str) -> tuple[list[str], list[float], list[float | None]]:
    rows = sorted(load_candles(conn, [ticker]), key=lambda r: r["date"])
    if len(rows) < 60:
        raise ChapterDataError(f"History {ticker} terlalu pendek (n={len(rows)}).")
    dates = [r["date"] for r in rows]
    closes = [float(r["close"]) for r in rows]
    vols = _realized_vol(closes, window=20)
    return dates, closes, vols


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=5)
        ticker = "IHSG" if "IHSG" in uni or not uni else uni[0]
        if ticker != "IHSG":
            ihsg_rows = load_candles(conn, ["IHSG"])
            if ihsg_rows:
                ticker = "IHSG"
        dates, closes, vols = _build_series(conn, ticker)

    X, y, vol_lag = [], [], []
    for i in range(21, len(closes) - 1):
        if vols[i] is None or vols[i - 1] is None:
            continue
        abs_ret = abs(closes[i + 1] / closes[i] - 1.0)
        X.append([float(vols[i]), float(vols[i - 1])])
        y.append(abs_ret)
        vol_lag.append(float(vols[i - 1]))

    if len(X) < 40:
        raise ChapterDataError(f"Sample vol terlalu kecil (n={len(X)}).")

    split = int(len(X) * 0.7)
    Xtr, Xte = np.array(X[:split]), np.array(X[split:])
    ytr, yte = np.array(y[:split]), np.array(y[split:])
    naive_te = np.array(vol_lag[split:])

    rf = RandomForestRegressor(n_estimators=50, max_depth=4, random_state=42)
    rf.fit(Xtr, ytr)
    mae_rf = float(mean_absolute_error(yte, rf.predict(Xte)))
    mae_naive = float(mean_absolute_error(yte, naive_te))

    last_vol = float(vols[-2] or 1e-6)
    raw_w = 1.0 / max(last_vol, 1e-6)
    cap_w = min(raw_w, 0.25)  # demo cap 25%

    lines = [
        f"ticker={ticker}  n={len(X)}  train={split} test={len(X)-split}",
        f"MAE |return| besok — RandomForest: {mae_rf:.5f}",
        f"MAE |return| besok — naive lag-vol: {mae_naive:.5f}",
        "",
        "Contoh sizing (target risk kasar, bukan live):",
        f"  realized_vol_20d={last_vol:.4f}",
        f"  weight_raw=1/vol={raw_w:.2f}  capped={cap_w:.2f}",
        "",
        "Catatan: vol-scaling mengurangi exposure saat vol tinggi —",
        "bukan jaminan Sharpe lebih baik tanpa backtest penuh.",
    ]

    metrics = {
        "ticker": ticker,
        "n": len(X),
        "mae_rf": mae_rf,
        "mae_naive": mae_naive,
        "realized_vol": last_vol,
        "weight_raw": raw_w,
        "weight_capped": cap_w,
    }
    return DemoResult(
        title="Volatility sizing · vol forecast + 1/vol demo",
        lines=lines,
        metrics=metrics,
        model="random_forest_abs_return",
        summary_md=(
            f"# Volatility sizing\n\n{ticker}: RF MAE={mae_rf:.5f}, "
            f"naive={mae_naive:.5f}. 1/vol weight demo.\n"
        ),
        scoreboard=True,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="risk / position sizing hooks di ai-saham (manual)",
        bring_back="realized vol + 1/vol sizing habit sebelum live sizing",
    )
