"""Ch.29 Forward valuation — consensus Forward P/E & PEG ratio model."""

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
from ml_saham.chapters.types import ChapterContext, DemoResult
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
        "  1) Consensus 1-Year Forward P/E = Price / Forward EPS 1Y",
        "  2) Rasio PEG = Forward P/E / Projected EPS Growth %",
        "  3) Ridge Regression & Quantile Ranking PEG vs Forward Return",
        "",
        "Caveat",
        "  • Estimasi forward EPS bergantung pada konsensus analis yang bisa berubah",
        "  • Saham siklikal (komoditas) sering memiliki Forward P/E semu yang sangat rendah di puncak siklus",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: forward_estimates_cache di ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.linear_model import Ridge
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

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

        # PEG ratio proxy: lower PEG is better (value + growth)
        # Score = -PEG so higher score is better
        score = -fwd_pe

        analyzed.append(
            {
                "ticker": t,
                "fwd_pe": fwd_pe,
                "fwd_eps": fwd_eps,
                "curr_price": curr_p,
                "score": score,
                "fwd": float(fwd[t]),
            }
        )

    if len(analyzed) < 8:
        raise ChapterDataError(f"Panel forward estimates terlalu kecil (n={len(analyzed)}).")

    scores = [a["score"] for a in analyzed]
    rets = maybe_haircut([a["fwd"] for a in analyzed], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)

    # Fit Ridge Regression predicting fwd return from forward P/E
    X = np.array([[a["fwd_pe"]] for a in analyzed])
    y = np.array(rets)
    ridge = Ridge(alpha=1.0)
    ridge.fit(X, y)
    coef = float(ridge.coef_[0])

    analyzed.sort(key=lambda a: a["fwd_pe"])

    lines = [
        f"as_of={as_of}  n_tickers={len(analyzed)}  source=forward_estimates_cache",
        f"Forward P/E Rank IC vs 5d fwd return: {ic:+.3f}",
        f"Ridge Forward P/E slope coef:        {coef:+.4f}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d return: {bench:+.2%}")

    lines.extend([
        "",
        "Top Lowest Forward P/E Consensus Names:",
    ])

    for a in analyzed[:8]:
        lines.append(
            f"  {a['ticker']:<6} Forward_PE={a['fwd_pe']:5.1f}x  Forward_EPS={a['fwd_eps']:,.1f}  fwd={a['fwd']:+.2%}"
        )

    top = [
        {"ticker": a["ticker"], "fwd_pe": a["fwd_pe"], "fwd": a["fwd"]}
        for a in analyzed[:10]
    ]

    metrics = {
        "as_of": as_of,
        "n_tickers": len(analyzed),
        "rank_ic_forward_pe": ic,
        "ridge_pe_coef": coef,
        "benchmark_return": bench,
    }
    return DemoResult(
        title="Forward valuation · consensus P/E & PEG model",
        lines=lines,
        metrics=metrics,
        model="ridge_forward_valuation",
        summary_md=f"# Forward valuation\n\nRank IC={ic:+.3f}. Coef={coef:+.4f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="forward_estimates_cache di ai-saham",
        bring_back="forward P/E consensus + PEG ratio rank IC habit",
    )
