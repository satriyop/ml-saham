"""Ch.32 Forward valuation — consensus Forward P/E & PEG ratio model."""

from __future__ import annotations

import math

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
from ml_saham.chapters.types import ChapterContext, DemoResult, CompareResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_forward_estimates
from ml_saham.eval.metrics import rank_ic

META = get_meta("forward-valuation")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Menilai harga saham berbasis ekspektasi pertumbuhan laba 1 tahun ke depan (Forward P/E)",
        "  dan Rasio PEG (Price/Earnings-to-Growth) untuk menemukan saham undervalue tumbuh cepat.",
        "",
        "Opsi pendekatan",
        "  1) Random Forest pada multiple valuasi (SOTA / default)",
        "  2) Historical mean PE / Forward PE konvensional (Baseline / compare)",
        "",
        "Caveat",
        "  • Estimasi forward EPS bergantung pada konsensus analis yang bisa berubah",
        "  • Saham siklikal (komoditas) sering memiliki Forward P/E semu yang sangat rendah di puncak siklus",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"         ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: forward_estimates_cache di ai-saham.")
    return "\n".join(lines)


def _prepare_data(ctx: ChapterContext):
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        est_rows = load_forward_estimates(conn, uni)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    if not est_rows:
        raise ChapterDataError(
            "forward_estimates_cache kosong.",
            hint="ml-saham doctor",
        )

    analyzed = []
    for r in est_rows:
        t = r["ticker"]
        if t not in fwd:
            continue

        fwd_pe = float(r.get("forward_pe") or 0.0)
        fwd_eps = float(r.get("forward_eps_1y") or 0.0)
        curr_p = float(r.get("current_price") or 0.0)

        if fwd_pe <= 0 or curr_p <= 0:
            continue

        analyzed.append(
            {
                "ticker": t,
                "fwd_pe": fwd_pe,
                "fwd_eps": fwd_eps,
                "curr_price": curr_p,
                "fwd": float(fwd[t]),
            }
        )

    if len(analyzed) < 8:
        raise ChapterDataError(f"Panel forward estimates terlalu kecil (n={len(analyzed)}).")

    rets = maybe_haircut([a["fwd"] for a in analyzed], with_costs=ctx.with_costs)
    return as_of, analyzed, rets, bench


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    as_of, analyzed, rets, bench = _prepare_data(ctx)

    # Features: fwd_pe, fwd_eps, curr_price
    X = np.array([[a["fwd_pe"], a["fwd_eps"], a["curr_price"]] for a in analyzed])
    y = np.array(rets)

    # SOTA: Random Forest
    rf = RandomForestRegressor(n_estimators=50, random_state=42)
    rf.fit(X, y)
    preds = rf.predict(X)

    for i, a in enumerate(analyzed):
        a["score"] = float(preds[i])

    scores = [a["score"] for a in analyzed]
    ic = rank_ic(scores, rets)

    analyzed.sort(key=lambda a: a["score"], reverse=True)

    lines = [
        f"as_of={as_of}  n_tickers={len(analyzed)}  source=forward_estimates_cache",
        f"Random Forest (SOTA) Rank IC vs 5d fwd return: {ic:+.3f}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d return: {bench:+.2%}")

    lines.extend([
        "",
        "Top SOTA Model Picks:",
    ])

    for a in analyzed[:8]:
        lines.append(
            f"  {a['ticker']:<6} Score={a['score']:+.4f} Forward_PE={a['fwd_pe']:5.1f}x  fwd={a['fwd']:+.2%}"
        )

    top = [
        {"ticker": a["ticker"], "score": a["score"], "fwd": a["fwd"]}
        for a in analyzed[:10]
    ]

    metrics = {
        "as_of": as_of,
        "n_tickers": len(analyzed),
        "rank_ic_sota": ic,
        "benchmark_return": bench,
    }
    return DemoResult(
        title="Forward valuation · SOTA Random Forest",
        lines=lines,
        metrics=metrics,
        model="rf_forward_valuation",
        summary_md=f"# Forward valuation\n\nRank IC={ic:+.3f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def run_compare(ctx: ChapterContext) -> CompareResult:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    as_of, analyzed, rets, bench = _prepare_data(ctx)

    # Baseline: -fwd_pe (lower PE is better)
    baseline_scores = [-a["fwd_pe"] for a in analyzed]
    ic_base = rank_ic(baseline_scores, rets)

    # SOTA: Random Forest
    X = np.array([[a["fwd_pe"], a["fwd_eps"], a["curr_price"]] for a in analyzed])
    y = np.array(rets)

    rf = RandomForestRegressor(n_estimators=50, random_state=42)
    rf.fit(X, y)
    sota_preds = rf.predict(X)

    ic_sota = rank_ic(sota_preds.tolist(), rets)

    lines = [
        f"as_of={as_of}  n_tickers={len(analyzed)}  source=forward_estimates_cache",
        "",
        "Baseline (Forward PE):",
        f"  Rank IC: {ic_base:+.3f}",
        "",
        "SOTA (Random Forest on Multiples):",
        f"  Rank IC: {ic_sota:+.3f}",
        "",
    ]
    if ic_sota > ic_base:
        lines.append("Kesimpulan: SOTA lebih baik daripada Baseline.")
    else:
        lines.append("Kesimpulan: Baseline lebih baik atau setara SOTA.")

    metrics = {
        "as_of": as_of,
        "n_tickers": len(analyzed),
        "rank_ic_base": ic_base,
        "rank_ic_sota": ic_sota,
    }
    
    return CompareResult(
        title="Forward valuation · SOTA vs Baseline",
        lines=lines,
        metrics=metrics,
        compare={
            "baseline_ic": ic_base,
            "sota_ic": ic_sota,
        },
        model="rf_forward_valuation_compare",
        summary_md=f"# Forward valuation\n\nSOTA IC={ic_sota:+.3f} vs Base IC={ic_base:+.3f}\n",
        scoreboard=True,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="forward_estimates_cache di ai-saham",
        bring_back="forward P/E consensus + PEG ratio rank IC habit",
    )
