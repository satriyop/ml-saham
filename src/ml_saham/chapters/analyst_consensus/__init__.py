"""Ch.20 Analyst consensus — target price revisions & consensus drift."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_analysts

META = get_meta("analyst-consensus")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Apakah target harga konsensus analis dan rasio rekomendasi Buy/Hold/Sell",
        "  memberikan sinyal harga yang valid atau hanya trailing indicator?",
        "",
        "Opsi pendekatan",
        "  1) Quantile Regression (25th, 50th, 75th percentile) target harga",
        "  2) Consensus Buy Ratio = Buy / (Buy + Hold + Sell)",
        "  3) Implied Price Target Upside % = (Target - Current) / Current",
        "",
        "Caveat",
        "  • Rekomendasi analis sering kali lambat merevisi harga (lagging)",
        "  • Bias optimisme analis pada saham capitalization besar",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_analysts dari analyst_cache.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.linear_model import Ridge
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        rows = load_analysts(conn, ctx.universe)

    if not rows:
        raise ChapterDataError(
            "analyst_cache kosong.",
            hint="ml-saham doctor",
        )

    analyzed = []
    for r in rows:
        buys = int(r.get("buy_count") or 0)
        holds = int(r.get("hold_count") or 0)
        sells = int(r.get("sell_count") or 0)
        total = buys + holds + sells
        buy_ratio = buys / total if total > 0 else 0.0

        target = float(r.get("avg_price_target") or 0.0)
        curr = float(r.get("current_price") or 0.0)
        upside = ((target - curr) / curr) if curr > 0 and target > 0 else 0.0

        analyzed.append(
            {
                "ticker": r["ticker"],
                "buys": buys,
                "holds": holds,
                "sells": sells,
                "total": total,
                "buy_ratio": buy_ratio,
                "target": target,
                "curr": curr,
                "upside": upside,
            }
        )

    if not analyzed:
        raise ChapterDataError("Tidak ada data rekomendasi analis valid.")

    # Quantiles of Price Target Upside
    upsides = [a["upside"] for a in analyzed if a["upside"] > 0]
    q25 = float(np.percentile(upsides, 25)) if upsides else 0.0
    q50 = float(np.percentile(upsides, 50)) if upsides else 0.0
    q75 = float(np.percentile(upsides, 75)) if upsides else 0.0

    # Sort by buy_ratio desc, upside desc
    analyzed.sort(key=lambda a: (a["buy_ratio"], a["upside"]), reverse=True)

    lines = [
        f"n_tickers={len(analyzed)}  source=analyst_cache",
        f"Distribution target upside %: Q25={q25:+.1%}  Median(Q50)={q50:+.1%}  Q75={q75:+.1%}",
        "",
        "Top analyst consensus Buy names:",
    ]

    for a in analyzed[:10]:
        lines.append(
            f"  {a['ticker']:<6} BuyRatio={a['buy_ratio']:.0%}  "
            f"B/H/S={a['buys']}/{a['holds']}/{a['sells']}  "
            f"Target={a['target']:,.0f}  Upside={a['upside']:+.1%}"
        )

    top_names = [
        {"ticker": a["ticker"], "buy_ratio": a["buy_ratio"], "upside": a["upside"]}
        for a in analyzed[:10]
    ]

    metrics = {
        "n_tickers": len(analyzed),
        "median_target_upside": q50,
        "q25_target_upside": q25,
        "q75_target_upside": q75,
    }
    return DemoResult(
        title="Analyst consensus · price target revisions",
        lines=lines,
        metrics=metrics,
        model="quantile_analyst_consensus",
        summary_md=f"# Analyst consensus\n\nMedian upside={q50:+.1%}. n={len(analyzed)}.\n",
        scoreboard=False,
        scoreboard_kind="none",
        top_names=top_names,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="analyst_cache di ai-saham",
        bring_back="consensus buy ratio + target price upside quantile habit",
    )
