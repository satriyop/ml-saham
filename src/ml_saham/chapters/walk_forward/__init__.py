"""Ch.12 Walk-forward — time split + leakage honesty lesson."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    load_fundie_map,
    momentum_nday,
    pick_as_of,
    resolve_universe,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_forward_labels
from ml_saham.eval.metrics import rank_ic

META = get_meta("walk-forward")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Fit model pada masa lalu, uji di masa depan — tanpa shuffle leakage.",
        "",
        "Opsi pendekatan",
        "  1) signal_forward_labels (phase2) bila ada",
        "  2) Build panel dari candles + fundamentals",
        "  3) ElasticNet/Ridge + bandingkan IC train vs test",
        "  4) Demo leakage: shuffle split → IC palsu lebih tinggi",
        "",
        "Caveat",
        "  • Satu split ≠ walk-forward penuh (rolling re-fit)",
        "  • Feature drift antar rezim",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: 70% train / 30% test time-ordered.")
    return "\n".join(lines)


def _from_labels(conn, uni: list[str]) -> list[dict]:
    rows = load_forward_labels(conn, uni, horizon=5, limit=3000)
    fundies = load_fundie_map(conn, uni)
    out = []
    mom_cache: dict[tuple[str, str], float | None] = {}
    for r in rows:
        ret = r.get("close_return")
        if ret is None:
            continue
        try:
            t = r["ticker"]
            d = r["signal_date"]
            key = (t, d)
            if key not in mom_cache:
                m = momentum_nday(conn, [t], as_of=d, window=20)
                mom_cache[key] = m.get(t)
            pe = fundies.get(t, {}).get("pe_ratio_ttm")
            pe_f = float(pe) if pe is not None else 0.0
            out.append(
                {
                    "date": d,
                    "ticker": t,
                    "fwd": float(ret),
                    "mom": mom_cache[key],
                    "pe": pe_f if pe_f > 0 else 0.0,
                }
            )
        except (TypeError, ValueError, KeyError):
            continue
    return out


def _from_panel(conn, uni: list[str]) -> list[dict]:
    as_of = pick_as_of(conn, uni, min_forward=5)
    if not as_of:
        return []
    fundies = load_fundie_map(conn, uni)
    mom = momentum_nday(conn, uni, as_of=as_of, window=20)
    from ml_saham.chapters.panel import forward_returns_by_ticker

    fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
    rows = []
    for t in uni:
        if t not in fwd or t not in mom:
            continue
        f = fundies.get(t, {})
        pe = f.get("pe_ratio_ttm")
        try:
            pe_f = float(pe) if pe is not None else 0.0
        except (TypeError, ValueError):
            pe_f = 0.0
        rows.append(
            {
                "date": as_of,
                "ticker": t,
                "fwd": float(fwd[t]),
                "mom": float(mom[t]),
                "pe": pe_f if pe_f > 0 else 0.0,
            }
        )
    return rows


def _build_features(rows: list[dict]) -> tuple[list[list[float]], list[float], list[str]]:
    X, y, dates = [], [], []
    for r in rows:
        mom = r.get("mom")
        pe = r.get("pe")
        if mom is None:
            continue
        pe_val = float(pe) if pe is not None else 0.0
        value = -pe_val if pe_val > 0 else 0.0
        X.append([float(mom), value])
        y.append(float(r["fwd"]))
        dates.append(r["date"])
    return X, y, dates


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.linear_model import ElasticNet, Ridge
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=40)
        rows = _from_labels(conn, uni)
        source = "signal_forward_labels"
        if len(rows) < 30:
            rows = _from_panel(conn, uni)
            source = "candles+fundies panel"
        if len(rows) < 20:
            raise ChapterDataError(f"Panel walk-forward terlalu kecil (n={len(rows)}).")

    X, y, dates = _build_features(rows)
    if len(X) < 20:
        raise ChapterDataError(f"Fitur valid terlalu sedikit (n={len(X)}).")

    order = sorted(range(len(dates)), key=lambda i: dates[i])
    Xo = [X[i] for i in order]
    yo = [y[i] for i in order]
    split = int(len(Xo) * 0.7)
    Xtr, Xte = np.array(Xo[:split]), np.array(Xo[split:])
    ytr, yte = np.array(yo[:split]), np.array(yo[split:])

    model = ElasticNet(alpha=0.05, l1_ratio=0.5, random_state=42, max_iter=8000)
    model.fit(Xtr, ytr)
    pred_tr = model.predict(Xtr).tolist()
    pred_te = model.predict(Xte).tolist()
    ic_tr = rank_ic(pred_tr, ytr.tolist())
    ic_te = rank_ic(pred_te, yte.tolist())

    # leakage demo: shuffled split inflates IC
    Xs, ys = np.array(Xo), np.array(yo)
    Xtr_s, Xte_s, ytr_s, yte_s = train_test_split(
        Xs, ys, test_size=0.3, random_state=42, shuffle=True
    )
    leak = Ridge(alpha=1.0, random_state=42)
    leak.fit(Xtr_s, ytr_s)
    ic_leak = rank_ic(leak.predict(Xte_s).tolist(), yte_s.tolist())

    lines = [
        f"source={source}  n={len(Xo)}  split=70/30 time-ordered",
        f"Train rank IC (ElasticNet): {ic_tr:+.3f}",
        f"Test  rank IC (ElasticNet): {ic_te:+.3f}",
        "",
        "Pelajaran leakage (sengaja salah):",
        f"  Shuffled-split test IC:     {ic_leak:+.3f}  ← biasanya lebih optimis",
        "",
        "Kesimpulan: jangan shuffle time series — IC test jujur biasanya",
        "lebih rendah dari demo shuffle di atas.",
    ]

    metrics = {
        "source": source,
        "n": len(Xo),
        "rank_ic_train": ic_tr,
        "rank_ic_test": ic_te,
        "rank_ic_shuffled_leak": ic_leak,
        "model": "elastic-net",
    }
    return DemoResult(
        title="Walk-forward · time split + leakage demo",
        lines=lines,
        metrics=metrics,
        model="elastic-net",
        summary_md=(
            f"# Walk-forward\n\nTrain IC={ic_tr:.3f}, test IC={ic_te:.3f}. "
            f"Shuffled leak IC={ic_leak:.3f}.\n"
        ),
        scoreboard=True,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="signal_forward_labels / rolling re-fit pipeline ai-saham",
        bring_back="time-ordered split + train/test IC habit",
    )
