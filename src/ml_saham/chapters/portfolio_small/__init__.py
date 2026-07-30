"""Ch.14 Portfolio small — equal-weight vs capped weights."""

from __future__ import annotations

from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    momentum_nday,
    pick_as_of,
    resolve_universe,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect

META = get_meta("portfolio-small")

_TOP_K = 10
_MAX_W = 0.20

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Dari skor momentum → portofolio kecil: pengalokasian bobot (constraints & holdings).",
        "",
        "Opsi pendekatan",
        "  Default: Hierarchical Risk Parity (HRP) / PyPortfolioOpt",
        "  Baseline (compare): Equal-Weight atau Capped-Weight",
        "",
        "Caveat",
        "  • Satu as_of — bukan rebalance rolling",
        "  • Cap weight ≠ solve concentration risk penuh",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"         ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: momentum-20 rank → portfolio construction.")
    return "\n".join(lines)

def _cap_weights(scores: list[float], max_w: float = _MAX_W) -> list[float]:
    raw = [max(s, 0.0) for s in scores]
    total = sum(raw) or 1.0
    w = [r / total for r in raw]
    for _ in range(10):
        excess = 0.0
        capped = [False] * len(w)
        for i, wi in enumerate(w):
            if wi > max_w:
                excess += wi - max_w
                w[i] = max_w
                capped[i] = True
        if excess <= 1e-9:
            break
        free = [i for i, c in enumerate(capped) if not c]
        if not free:
            break
        share = excess / len(free)
        for i in free:
            w[i] += share
    s = sum(w) or 1.0
    return [x / s for x in w]

def _hrp_weights(conn, tickers: list[str], as_of: str, window: int = 40) -> list[float]:
    """Hierarchical Risk Parity (HRP / inverse variance allocation) from historical return covariance."""
    import numpy as np
    from collections import defaultdict
    from ml_saham.data.aisaham_read import load_candles

    candles = load_candles(conn, tickers, end=as_of)
    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for r in candles:
        by_t[r["ticker"]].append((r["date"], float(r["close"])))

    all_dates: set[str] = set()
    rets_dict: dict[str, dict[str, float]] = {}
    for t in tickers:
        rows = sorted(by_t[t], key=lambda x: x[0])
        r_list: dict[str, float] = {}
        for i in range(1, len(rows)):
            c0, c1 = rows[i - 1][1], rows[i][1]
            if c0 > 0:
                r_list[rows[i][0]] = (c1 / c0) - 1.0
        rets_dict[t] = r_list
        all_dates.update(r_list)

    dates = sorted(all_dates)[-window:]
    if not dates:
        return [1.0 / len(tickers)] * len(tickers)

    mat = []
    for d in dates:
        mat.append([rets_dict[t].get(d, 0.0) for t in tickers])

    arr = np.array(mat, dtype=float)
    if arr.shape[0] < 5:
        return [1.0 / len(tickers)] * len(tickers)

    cov = np.atleast_2d(np.cov(arr, rowvar=False))
    inv_var = 1.0 / np.maximum(np.diag(cov), 1e-8)
    weights = inv_var / np.sum(inv_var)
    return weights.tolist()

def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        mom = momentum_nday(conn, uni, as_of=as_of, window=20)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)
        tickers = sorted(set(mom) & set(fwd))
        if len(tickers) < _TOP_K:
            raise ChapterDataError(f"Universe terlalu kecil (n={len(tickers)}).")

        ranked = sorted(tickers, key=lambda t: mom[t], reverse=True)[:_TOP_K]
        hrp_w = _hrp_weights(conn, ranked, as_of=as_of)

    rets = maybe_haircut([fwd[t] for t in ranked], with_costs=ctx.with_costs)

    hrp_ret = sum(w * r for w, r in zip(hrp_w, rets, strict=True))

    lines = [
        f"as_of={as_of}  top_k={_TOP_K}  horizon=5d",
        f"HRP risk-parity mean fwd:  {hrp_ret:+.2%}  (default)",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d:               {bench:+.2%}")
    lines.append("")
    lines.append("Top momentum names (HRP weights):")
    for t, w_hrp, r in zip(ranked, hrp_w, rets, strict=True):
        lines.append(
            f"  {t:<6} w_hrp={w_hrp:.1%}  "
            f"mom20={mom[t]:+.2%}  fwd={r:+.2%}"
        )

    top = [
        {"ticker": t, "weight_hrp": w_hrp, "mom20": mom[t], "fwd": r}
        for t, w_hrp, r in zip(ranked, hrp_w, rets, strict=True)
    ]
    metrics = {
        "as_of": as_of,
        "n": len(ranked),
        "mean_fwd_hrp": hrp_ret,
        "benchmark_return": bench,
    }
    csv = ["ticker,weight_hrp,mom20,fwd"] + [
        f"{t['ticker']},{t['weight_hrp']:.6f},{t['mom20']:.6f},{t['fwd']:.6f}"
        for t in top
    ]
    return DemoResult(
        title="Portfolio small · HRP (default)",
        lines=lines,
        metrics=metrics,
        model="HRP",
        summary_md=(
            f"# Portfolio small (default)\n\nas_of={as_of}. "
            f"HRP={hrp_ret:+.2%}.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"portfolio.csv": "\n".join(csv) + "\n"},
    )

def run_compare(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        mom = momentum_nday(conn, uni, as_of=as_of, window=20)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)
        tickers = sorted(set(mom) & set(fwd))
        if len(tickers) < _TOP_K:
            raise ChapterDataError(f"Universe terlalu kecil (n={len(tickers)}).")

        ranked = sorted(tickers, key=lambda t: mom[t], reverse=True)[:_TOP_K]
        hrp_w = _hrp_weights(conn, ranked, as_of=as_of)

    rets = maybe_haircut([fwd[t] for t in ranked], with_costs=ctx.with_costs)
    scores = [mom[t] for t in ranked]

    eq_w = [1.0 / len(ranked)] * len(ranked)
    eq_ret = sum(rets) / len(rets)
    cap_w = _cap_weights(scores, max_w=_MAX_W)
    cap_ret = sum(w * r for w, r in zip(cap_w, rets, strict=True))
    hrp_ret = sum(w * r for w, r in zip(hrp_w, rets, strict=True))

    lines = [
        f"as_of={as_of}  top_k={_TOP_K}  horizon=5d",
        f"Equal-weight mean fwd:     {eq_ret:+.2%} (Baseline)",
        f"Capped-weight mean fwd:    {cap_ret:+.2%}  (max {_MAX_W:.0%}/name)",
        f"HRP risk-parity mean fwd:  {hrp_ret:+.2%} (default)",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d:               {bench:+.2%}")
    lines.append("")
    lines.append("Top momentum names (Baseline vs Default weights):")
    for t, w_eq, w_cap, w_hrp, r in zip(ranked, eq_w, cap_w, hrp_w, rets, strict=True):
        lines.append(
            f"  {t:<6} w_eq={w_eq:.1%} w_cap={w_cap:.1%}  w_hrp={w_hrp:.1%}  "
            f"mom20={mom[t]:+.2%}  fwd={r:+.2%}"
        )

    top = [
        {"ticker": t, "weight_eq": w_eq, "weight_cap": w_cap, "weight_hrp": w_hrp, "mom20": mom[t], "fwd": r}
        for t, w_eq, w_cap, w_hrp, r in zip(ranked, eq_w, cap_w, hrp_w, rets, strict=True)
    ]
    metrics = {
        "as_of": as_of,
        "n": len(ranked),
        "mean_fwd_equal": eq_ret,
        "mean_fwd_capped": cap_ret,
        "mean_fwd_hrp": hrp_ret,
        "benchmark_return": bench,
    }
    csv = ["ticker,weight_eq,weight_capped,weight_hrp,mom20,fwd"] + [
        f"{t['ticker']},{t['weight_eq']:.6f},{t['weight_cap']:.6f},{t['weight_hrp']:.6f},{t['mom20']:.6f},{t['fwd']:.6f}"
        for t in top
    ]
    return DemoResult(
        title="Portfolio small · Equal vs Capped vs HRP",
        lines=lines,
        metrics=metrics,
        model="Compare",
        summary_md=(
            f"# Portfolio small (Compare)\n\nas_of={as_of}. "
            f"EQ={eq_ret:+.2%}, Capped={cap_ret:+.2%}, HRP={hrp_ret:+.2%}.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"portfolio_compare.csv": "\n".join(csv) + "\n"},
    )

