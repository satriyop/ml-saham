"""Ch.33 Meta-ensemble — multi-factor stacked super learner."""

from __future__ import annotations

import math
from collections import defaultdict

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    pick_as_of,
    resolve_universe,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles
from ml_saham.eval.metrics import rank_ic

META = get_meta("meta-ensemble")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Menggabungkan prediksi dari berbagai model dasar (Value, Momentum, Kualitas, Volatilitas, Flow)",
        "  menggunakan Stacked Generalization (Super Learner / Meta-Classifier Level-1).",
        "",
        "Opsi pendekatan",
        "  1) Vektor Sinyal Multi-Faktor Cross-Sectional",
        "  2) Stacked Meta-Learner (Level-1 Ridge Regression Ensemble)",
        "  3) Rank IC Meta-Score vs 5-Day Forward Return",
        "",
        "Caveat",
        "  • Meta-ensemble membutuhkan pembagian data Purged Cross-Validation untuk mencegah overfitting",
        "  • Korelasi tinggi antar faktor (multicollinearity) dapat mendistorsi bobot meta-learner",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: E2E multi-factor stacked generalization di ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import Ridge
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        candles = load_candles(conn, uni, end=as_of)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    if not candles:
        raise ChapterDataError("Data candles kosong.")

    by_t = defaultdict(list)
    for r in candles:
        by_t[r["ticker"]].append(r)

    meta_features: list[list[float]] = []
    meta_tickers: list[str] = []

    for t, rows in by_t.items():
        if len(rows) < 30 or t not in fwd:
            continue
        rows = sorted(rows, key=lambda x: x["date"])
        closes = [float(r["close"]) for r in rows]
        vols = [float(r["volume"] or 0) for r in rows]

        # Multi-factor base signals
        mom_20d = closes[-1] / (closes[-20] or 1.0) - 1.0
        ret_1d = closes[-1] / (closes[-2] or 1.0) - 1.0
        vol_20d = float(np.std([math.log(closes[i] / closes[i - 1]) for i in range(-19, 0)]))
        vol_surge = vols[-1] / (np.mean(vols[-10:]) or 1.0)

        meta_features.append([mom_20d, ret_1d, vol_20d, vol_surge])
        meta_tickers.append(t)

    if len(meta_tickers) < 10:
        raise ChapterDataError(f"Panel meta-ensemble terlalu kecil (n={len(meta_tickers)}).")

    X = np.array(meta_features)
    y = np.array([fwd[t] for t in meta_tickers])

    # Base models (Level 0)
    rf_base = RandomForestRegressor(n_estimators=30, max_depth=3, random_state=42)
    rf_base.fit(X, y)
    rf_preds = rf_base.predict(X)

    ridge_base = Ridge(alpha=1.0)
    ridge_base.fit(X, y)
    ridge_preds = ridge_base.predict(X)

    # Meta Learner (Level 1)
    X_meta = np.column_stack([rf_preds, ridge_preds])
    meta_learner = Ridge(alpha=0.5, random_state=42)
    meta_learner.fit(X_meta, y)
    meta_scores = meta_learner.predict(X_meta).tolist()

    rets = maybe_haircut([fwd[t] for t in meta_tickers], with_costs=ctx.with_costs)
    ic = rank_ic(meta_scores, rets)

    meta_weights = {
        "random_forest_base": float(meta_learner.coef_[0]),
        "ridge_linear_base": float(meta_learner.coef_[1]),
    }

    order = sorted(range(len(meta_tickers)), key=lambda i: meta_scores[i], reverse=True)
    top = [
        {"ticker": meta_tickers[i], "meta_score": meta_scores[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(meta_tickers)}  base_models=2 (RF+Ridge)",
        f"Stacked Meta-Ensemble Rank IC vs 5d fwd return: {ic:+.3f}",
        "",
        "Meta-Learner Level-1 Ensemble Weights:",
        f"  RandomForest Base Weight: {meta_weights['random_forest_base']:+.4f}",
        f"  Ridge Linear Base Weight: {meta_weights['ridge_linear_base']:+.4f}",
        "",
        "Top Meta-Ensemble Stacked Signal Names:",
    ]

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} MetaScore={t['meta_score']:+6.4f}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(meta_tickers),
        "rank_ic_meta_ensemble": ic,
        "meta_weights": meta_weights,
    }
    return DemoResult(
        title="Meta-ensemble · stacked super learner",
        lines=lines,
        metrics=metrics,
        model="stacked_meta_ensemble",
        summary_md=f"# Meta-ensemble\n\nRank IC={ic:+.3f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="E2E multi-factor stacked generalization di ai-saham",
        bring_back="Stacked Generalization Level-1 ensemble + Rank IC habit",
    )
