"""Ch.32 Microstructure impact — Amihud illiquidity & price impact estimator."""

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

META = get_meta("microstructure-impact")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mengukur kedalaman pasar dan dampak harga per transaksi 1 Miliar IDR",
        "  menggunakan Rasio Ilikuiditas Amihud & Estimator Spread Bid-Ask High-Low Corwin-Schultz.",
        "",
        "Opsi pendekatan",
        "  1) Amihud Illiquidity Ratio = |Return| / (Volume * Price)",
        "  2) Corwin-Schultz High-Low Spread Estimator",
        "  3) SVR / ElasticNet Market Impact Model vs Forward Volatility & Return",
        "",
        "Caveat",
        "  • Emiten berkapitalisasi kecil (small cap) memiliki Amihud sangat tinggi (likuiditas tipis)",
        "  • Biaya transaksi & slippage harus disesuaikan dengan Amihud ratio",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_candles di ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.svm import SVR
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

    amihud_map: dict[str, float] = {}
    details: dict[str, dict] = {}

    for t, rows in by_t.items():
        if len(rows) < 20 or t not in fwd:
            continue
        rows = sorted(rows, key=lambda x: x["date"])
        amihud_vals = []
        for i in range(1, len(rows)):
            c0 = float(rows[i - 1]["close"] or 0)
            c1 = float(rows[i]["close"] or 0)
            vol = float(rows[i]["volume"] or 0)
            val = float(rows[i].get("value") or (vol * c1))
            if c0 > 0 and val > 0:
                ret_abs = abs(c1 / c0 - 1.0)
                # Amihud ratio per IDR 1B traded
                amihud = (ret_abs / (val / 1e9)) * 100.0
                amihud_vals.append(amihud)

        if amihud_vals:
            avg_amihud = float(np.mean(amihud_vals[-20:]))
            # Liquidity score = -Amihud (higher = more liquid)
            liq_score = -avg_amihud
            amihud_map[t] = avg_amihud
            details[t] = {"amihud": avg_amihud, "liq_score": liq_score}

    tickers = sorted(amihud_map.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel illiquidity terlalu kecil (n={len(tickers)}).")

    scores = [details[t]["liq_score"] for t in tickers]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)

    X = np.array([[details[t]["amihud"]] for t in tickers])
    y = np.array(rets)
    svr = SVR(kernel="rbf", C=1.0)
    svr.fit(X, y)

    order = sorted(range(len(tickers)), key=lambda i: scores[i], reverse=True)
    top = [
        {"ticker": tickers[i], "amihud": details[tickers[i]]["amihud"], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}  source=candles",
        f"Amihud Liquidity Score Rank IC vs 5d fwd return: {ic:+.3f}",
        "SVR Non-Linear Market Impact Model fitted",
        "",
        "Top Most Liquid Names (Lowest Amihud Price Impact per IDR 1B):",
    ]

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} AmihudRatio={t['amihud']:6.3f}%/1B  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_amihud_liquidity": ic,
    }
    return DemoResult(
        title="Microstructure impact · Amihud illiquidity & SVR model",
        lines=lines,
        metrics=metrics,
        model="svr_amihud_impact",
        summary_md=f"# Microstructure impact\n\nRank IC={ic:+.3f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="candles di ai-saham",
        bring_back="Amihud Illiquidity ratio + SVR market impact habit",
    )
