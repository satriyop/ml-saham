"""Ch.13 Portfolio small — equal-weight vs capped weights."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
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
        "  Dari skor momentum → portofolio kecil: equal-weight vs cap per nama.",
        "",
        "Opsi pendekatan",
        "  1) Top-k equal-weight",
        "  2) Score-proportional dengan cap max 20% per ticker",
        "  3) Bandingkan mean forward return vs IHSG",
        "",
        "Caveat",
        "  • Satu as_of — bukan rebalance rolling",
        "  • Cap weight ≠ solve concentration risk penuh",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
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
    rets = maybe_haircut([fwd[t] for t in ranked], with_costs=ctx.with_costs)
    scores = [mom[t] for t in ranked]

    eq_w = 1.0 / len(ranked)
    eq_ret = sum(rets) / len(rets)
    cap_w = _cap_weights(scores, max_w=_MAX_W)
    cap_ret = sum(w * r for w, r in zip(cap_w, rets, strict=True))

    lines = [
        f"as_of={as_of}  top_k={_TOP_K}  horizon=5d",
        f"Equal-weight mean fwd:     {eq_ret:+.2%}",
        f"Capped-weight mean fwd:    {cap_ret:+.2%}  (max {_MAX_W:.0%}/name)",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d:               {bench:+.2%}")
    lines.append("")
    lines.append("Top momentum names (capped weights):")
    for t, w, r in zip(ranked, cap_w, rets, strict=True):
        lines.append(f"  {t:<6} w={w:.1%}  mom20={mom[t]:+.2%}  fwd={r:+.2%}")

    top = [
        {"ticker": t, "weight": w, "mom20": mom[t], "fwd": r}
        for t, w, r in zip(ranked, cap_w, rets, strict=True)
    ]
    metrics = {
        "as_of": as_of,
        "n": len(ranked),
        "mean_fwd_equal": eq_ret,
        "mean_fwd_capped": cap_ret,
        "benchmark_return": bench,
    }
    csv = ["ticker,weight,mom20,fwd"] + [
        f"{t['ticker']},{t['weight']:.6f},{t['mom20']:.6f},{t['fwd']:.6f}" for t in top
    ]
    return DemoResult(
        title="Portfolio small · equal vs capped",
        lines=lines,
        metrics=metrics,
        model="momentum_topk",
        summary_md=(
            f"# Portfolio small\n\nas_of={as_of}. "
            f"EQ={eq_ret:+.2%}, capped={cap_ret:+.2%}.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"portfolio.csv": "\n".join(csv) + "\n"},
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="portfolio construction / rebalance hooks ai-saham",
        bring_back="top-k + weight cap habit vs concentration",
    )
