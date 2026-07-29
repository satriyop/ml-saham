"""Ch.41 Pre-open Direction Audit."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.chapters.pre_open_base import fetch_and_evaluate_pre_open

META = get_meta("pre-open-direction")


def explore_text(*, verbose: bool = False) -> str:
    return f"Explore {META.title}"


def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan run_compare.")


def run_compare(ctx: ChapterContext) -> DemoResult:
    features = [
        "iep_gap_pct", 
        "bid_offer_imbalance", 
        "book_pressure"
    ]
    
    res = fetch_and_evaluate_pre_open(ctx.db_path, features, "Direction")
    
    lines = [
        f"date={res['latest_date']}  n_samples={res['n_samples']}",
        "Perbandingan Modul Arah (Direction) Default vs Baseline",
        "",
        f"Baseline Rank IC : {res['baseline_ic']:+.3f}",
        f"Default Rank IC     : {res['against_ic']:+.3f}",
        "",
        "=== Analisis Bobot Pengaruh (XGBoost) ==="
    ]
    
    md_lines = [
        "# Modul Arah (Direction) Compare\n",
        "- **Baseline Rank IC:** " + f"{res['baseline_ic']:+.3f}",
        "- **Default Rank IC:** " + f"{res['against_ic']:+.3f}\n",
        "### Analisis Bobot Pengaruh",
    ]

    feat_imp = sorted(zip(res["features"], res["importances"]), key=lambda x: x[1], reverse=True)
    for name, imp in feat_imp:
        lines.append(f"  {name:<24} : {imp:5.1f}%")
        md_lines.append(f"- **{name}**: {imp:5.1f}%")

    return DemoResult(
        title="Pre-Open \u00b7 Direction Audit",
        lines=lines,
        metrics={"n_samples": res["n_samples"], "baseline_ic": float(res["baseline_ic"]), "against_ic": float(res["against_ic"])},
        model="xgboost_direction",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )

def deepdive_text() -> str:
    return deepdive_stub(topic=META.slug, related="screener / pre-open", bring_back="Pre-Open")
