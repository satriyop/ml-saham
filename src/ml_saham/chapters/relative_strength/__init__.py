"""Ch.24 Relative strength — Mansfield RS vs IHSG benchmark momentum."""

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
from ml_saham.data.aisaham_read import connect, load_candles
from ml_saham.eval.metrics import rank_ic

META = get_meta("relative-strength")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mengukur kekuatan relatif saham terhadap acuan IHSG (Mansfield Relative Strength)",
        "  untuk memisahkan kenaikan harga riil dari kenaikan yang sekadar mengekor pasar.",
        "",
        "Opsi pendekatan",
        "  1) Mansfield Relative Strength = ((Price / IHSG) / SMA50(Price / IHSG) - 1) * 100",
        "  2) ElasticNet / Ridge Regression Mansfield RS vs Forward Return",
        "  3) Rank IC RS Mansfield vs 5-Day Forward Return",
        "",
        "Caveat",
        "  • Relative strength murni tidak memperhitungkan rasio fundamental",
        "  • Sering kali saham ber-RS tinggi mengalami profit taking mendadak",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: strategies/rs-momentum di ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.linear_model import ElasticNet
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        candles = load_candles(conn, [*uni, "IHSG"], end=as_of)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    if not candles:
        raise ChapterDataError("Data candles kosong.")

    by_t: dict[str, list[tuple[str, float]]] = {}
    for r in candles:
        by_t.setdefault(r["ticker"], []).append((r["date"], float(r["close"])))

    ihsg_series = sorted(by_t.get("IHSG", []), key=lambda x: x[0])
    if len(ihsg_series) < 50:
        raise ChapterDataError("History IHSG tidak cukup (butuh >= 50 bar).")

    ihsg_dates = [d for d, _ in ihsg_series]
    ihsg_closes = [c for _, c in ihsg_series]

    rs_mansfield: dict[str, float] = {}
    tickers = []

    for t in uni:
        if t == "IHSG" or t not in by_t or t not in fwd:
            continue
        series = sorted(by_t[t], key=lambda x: x[0])
        if len(series) < 50:
            continue

        # Align stock and IHSG ratio
        t_dict = dict(series)
        ratios = []
        for d, c_idx in zip(ihsg_dates[-50:], ihsg_closes[-50:], strict=True):
            if d in t_dict and c_idx > 0:
                ratios.append(t_dict[d] / c_idx)

        if len(ratios) < 50:
            continue

        sma50_ratio = sum(ratios) / len(ratios)
        if sma50_ratio > 0:
            mansfield = ((ratios[-1] / sma50_ratio) - 1.0) * 100.0
            rs_mansfield[t] = mansfield
            tickers.append(t)

    if len(tickers) < 10:
        raise ChapterDataError(f"Panel RS terlalu kecil (n={len(tickers)}).")

    scores = [rs_mansfield[t] for t in tickers]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)

    # ElasticNet regression
    X = np.array(scores).reshape(-1, 1)
    y = np.array(rets)
    enet = ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42)
    enet.fit(X, y)
    coef = float(enet.coef_[0])

    order = sorted(range(len(tickers)), key=lambda i: scores[i], reverse=True)
    top = [
        {"ticker": tickers[i], "rs_mansfield": scores[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}  benchmark=IHSG",
        f"Mansfield RS Rank IC vs 5d fwd return: {ic:+.3f}",
        f"ElasticNet RS slope coef:             {coef:+.4f}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d return: {bench:+.2%}")

    lines.extend([
        "",
        "Top Mansfield Relative Strength names vs IHSG:",
    ])

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} RS_Mansfield={t['rs_mansfield']:+6.2f}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_mansfield_rs": ic,
        "elasticnet_rs_coef": coef,
        "benchmark_return": bench,
    }
    return DemoResult(
        title="Relative strength · Mansfield RS momentum",
        lines=lines,
        metrics=metrics,
        model="elasticnet_mansfield_rs",
        summary_md=f"# Relative strength\n\nRank IC={ic:+.3f}. Coef={coef:+.4f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="strategies/rs-momentum di ai-saham",
        bring_back="Mansfield RS relative strength + ElasticNet slope habit",
    )
