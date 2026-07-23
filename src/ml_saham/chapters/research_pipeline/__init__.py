"""Ch.17 Research pipeline — mini end-to-end + artifacts."""

from __future__ import annotations

import json

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    momentum_nday,
    pick_as_of,
    resolve_universe,
    zscore,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.eval.metrics import metrics_bundle, rank_ic

META = get_meta("research-pipeline")

FEATURES = ["momentum_20d", "value_neg_pe", "quality_roe"]


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Riset ujung-ke-ujung: fitur → skor → metrik → artifact tersimpan.",
        "",
        "Opsi pendekatan",
        "  1) Definisikan feature_list.json",
        "  2) Hitung momentum (+ stub value/quality)",
        "  3) Stack metrics + summary_md untuk review manusia",
        "",
        "Caveat",
        "  • Mini pipeline — bukan production DAG",
        "  • Artifact habit: simpan feature list + top names",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nOutput: feature_list.json di extra_files.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=40)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        mom = momentum_nday(conn, uni, as_of=as_of, window=20)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    tickers = sorted(set(mom) & set(fwd))
    if len(tickers) < 10:
        raise ChapterDataError(f"Panel pipeline terlalu kecil (n={len(tickers)}).")

    mom_vals = [mom[t] for t in tickers]
    scores = [float(z or 0) for z in zscore(mom_vals)]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)
    bundle = metrics_bundle(
        scores,
        rets,
        benchmark_return=bench,
        date_range=(as_of, as_of),
        n_tickers=len(tickers),
    )

    order = sorted(range(len(tickers)), key=lambda i: scores[i], reverse=True)
    top = [
        {"ticker": tickers[i], "score": scores[i], "mom20": mom[tickers[i]], "fwd": rets[i]}
        for i in order[:10]
    ]

    feature_doc = {
        "chapter": META.slug,
        "as_of": as_of,
        "features": FEATURES,
        "primary_signal": "momentum_20d_zscore",
        "horizon_days": 5,
        "notes": "Mini pipeline demo — extend with value/quality from fundies.",
    }

    lines = [
        f"as_of={as_of}  n={len(tickers)}  horizon=5d",
        f"Pipeline step 1: features={', '.join(FEATURES)}",
        f"Pipeline step 2: momentum z-score rank IC={ic:+.3f}",
        f"Pipeline step 3: metrics_bundle n={bundle.get('n', len(tickers))}",
        "",
        "Stacked summary:",
        f"  rank_ic={ic:+.3f}  mean_fwd={bundle.get('mean_return', 0):+.2%}",
    ]
    if bench is not None:
        lines.append(f"  IHSG fwd={bench:+.2%}")
    lines.append("")
    lines.append("Artifact habit: feature_list.json written to extra_files.")
    lines.append("Top momentum pipeline names:")
    for t in top[:6]:
        lines.append(
            f"  {t['ticker']:<6} score={t['score']:+.2f}  "
            f"mom={t['mom20']:+.2%}  fwd={t['fwd']:+.2%}"
        )

    metrics = {**bundle, "as_of": as_of, "rank_ic": ic, "features": FEATURES}
    return DemoResult(
        title="Research pipeline · mini E2E",
        lines=lines,
        metrics=metrics,
        model="momentum_pipeline",
        summary_md=(
            f"# Research pipeline\n\nas_of={as_of}. IC={ic:.3f}. "
            f"Features: {', '.join(FEATURES)}.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={
            "feature_list.json": json.dumps(feature_doc, indent=2) + "\n",
        },
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="full research DAG / artifact store ai-saham",
        bring_back="feature_list.json + stacked metrics review habit",
    )
