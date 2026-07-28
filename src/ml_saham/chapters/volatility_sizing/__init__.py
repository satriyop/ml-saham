"""Ch.10 Volatility sizing — realized vol + position scale demo."""

from __future__ import annotations

import math

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult, CompareResult
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
        "Opsi algoritma",
        "  1) GARCH(1,1) Volatility Forecasting (default, SOTA)",
        "  2) EWMA (compare, baseline)",
        "",
        "Caveat",
        "  • Vol clustering — model sederhana mudah overfit",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"         ml-saham compare {META.slug}",
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


def _ewma_vol(closes: list[float], lambda_param: float = 0.94) -> list[float | None]:
    """Compute Exponentially Weighted Moving Average (EWMA) volatility (RiskMetrics style)."""
    rets = [0.0] + [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    out: list[float | None] = [None] * len(closes)
    if len(closes) < 5:
        return out
    variance = rets[1] ** 2
    out[1] = math.sqrt(variance)
    for i in range(2, len(closes)):
        variance = lambda_param * variance + (1.0 - lambda_param) * (rets[i] ** 2)
        out[i] = math.sqrt(variance)
    return out


def _build_series(conn, ticker: str) -> tuple[list[str], list[float], list[float | None], list[float | None]]:
    rows = sorted(load_candles(conn, [ticker]), key=lambda r: r["date"])
    if len(rows) < 60:
        raise ChapterDataError(f"History {ticker} terlalu pendek (n={len(rows)}).")
    dates = [r["date"] for r in rows]
    closes = [float(r["close"]) for r in rows]
    vols = _realized_vol(closes, window=20)
    ewma_vols = _ewma_vol(closes, lambda_param=0.94)
    return dates, closes, vols, ewma_vols


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        from arch import arch_model
        import numpy as np
        from sklearn.metrics import mean_absolute_error
    except ImportError as exc:
        raise ChapterError("Butuh arch dan scikit-learn: pip install arch scikit-learn") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=5)
        ticker = "IHSG" if "IHSG" in uni or not uni else uni[0]
        if ticker != "IHSG":
            ihsg_rows = load_candles(conn, ["IHSG"])
            if ihsg_rows:
                ticker = "IHSG"
        dates, closes, vols, ewma_vols = _build_series(conn, ticker)

    rets = [math.log(closes[i] / closes[i - 1]) * 100.0 for i in range(1, len(closes))]
    
    if len(rets) < 60:
        raise ChapterDataError(f"Sample vol terlalu kecil (n={len(rets)}).")
        
    split = int(len(rets) * 0.7)
    
    am = arch_model(rets, vol='Garch', p=1, q=1, rescale=False)
    res = am.fit(last_obs=split, disp="off")
    cond_vol = res.conditional_volatility[split:]
    
    test_r_abs = np.abs(rets[split:])
    
    mae_garch = float(mean_absolute_error(test_r_abs, cond_vol))
    
    forecasts = res.forecast(horizon=1)
    next_vol_pct = float(math.sqrt(forecasts.variance.iloc[-1, 0]))
    next_vol_dec = next_vol_pct / 100.0
    
    raw_w = 1.0 / max(next_vol_dec, 1e-6)
    cap_w = min(raw_w, 0.25)  # demo cap 25%

    lines = [
        f"ticker={ticker}  n={len(rets)}  train={split} test={len(rets)-split}",
        f"MAE |return| besok — GARCH(1,1): {mae_garch:.5f}",
        "",
        "Contoh sizing (target risk kasar, bukan live):",
        f"  GARCH(1,1)_vol={next_vol_dec:.4f}  (1/vol weight={raw_w:.2f}, capped={cap_w:.2f})",
        "",
        "Catatan: vol-scaling mengurangi exposure saat vol tinggi —",
        "bukan jaminan Sharpe lebih baik tanpa backtest penuh.",
    ]

    metrics = {
        "ticker": ticker,
        "n": len(rets),
        "mae_garch": mae_garch,
        "garch_vol": next_vol_dec,
        "weight_raw": raw_w,
        "weight_capped": cap_w,
    }
    return DemoResult(
        title="Volatility sizing · GARCH(1,1) + 1/vol demo",
        lines=lines,
        metrics=metrics,
        model="garch_1_1",
        summary_md=(
            f"# Volatility sizing\n\n{ticker}: GARCH(1,1) MAE={mae_garch:.5f}. "
            f"1/vol weight demo.\n"
        ),
        scoreboard=True,
    )


def run_compare(ctx: ChapterContext) -> CompareResult:
    try:
        from arch import arch_model
        import numpy as np
        from sklearn.metrics import mean_absolute_error
    except ImportError as exc:
        raise ChapterError("Butuh arch dan scikit-learn: pip install arch scikit-learn") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=5)
        ticker = "IHSG" if "IHSG" in uni or not uni else uni[0]
        if ticker != "IHSG":
            ihsg_rows = load_candles(conn, ["IHSG"])
            if ihsg_rows:
                ticker = "IHSG"
        dates, closes, vols, ewma_vols = _build_series(conn, ticker)

    rets = [math.log(closes[i] / closes[i - 1]) * 100.0 for i in range(1, len(closes))]
    
    if len(rets) < 60:
        raise ChapterDataError(f"Sample vol terlalu kecil (n={len(rets)}).")
        
    split = int(len(rets) * 0.7)
    
    # GARCH(1,1)
    am = arch_model(rets, vol='Garch', p=1, q=1, rescale=False)
    res = am.fit(last_obs=split, disp="off")
    cond_vol = res.conditional_volatility[split:]
    
    test_r_abs = np.abs(rets[split:])
    
    # EWMA
    test_ewma = np.array(ewma_vols[:-1])[split:]
    test_ewma_pct = np.array([float(x or 0.0) for x in test_ewma]) * 100.0
    
    mae_garch = float(mean_absolute_error(test_r_abs, cond_vol))
    mae_ewma = float(mean_absolute_error(test_r_abs, test_ewma_pct))

    winner = "GARCH(1,1)" if mae_garch < mae_ewma else "EWMA"
    diff = abs(mae_garch - mae_ewma)
    
    lines = [
        f"Bandingkan MAE prediktor volatilitas untuk {ticker} (n={len(rets)})",
        f"1) GARCH(1,1) (SOTA): {mae_garch:.5f}",
        f"2) EWMA (Baseline):   {mae_ewma:.5f}",
        "",
        f"Pemenang MAE: {winner} (selisih {diff:.5f})",
    ]
    
    return CompareResult(
        title="Bandingkan Volatility Sizing (GARCH vs EWMA)",
        lines=lines,
        metrics={"mae_garch": mae_garch, "mae_ewma": mae_ewma},
        compare={"winner": winner, "diff": diff},
        model="garch_vs_ewma",
        summary_md=f"# Bandingkan GARCH vs EWMA\n\nPemenang: {winner} untuk {ticker}.",
        scoreboard=True,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="risk / position sizing hooks di ai-saham (manual)",
        bring_back="realized vol + 1/vol sizing habit sebelum live sizing",
    )
