"""Ch.43 Pre-open Auction Quality Audit."""

from __future__ import annotations

from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.chapters.pre_open_base import fetch_and_evaluate_pre_open

META = get_meta("pre-open-auction")

def explore_text(*, verbose: bool = False) -> str:
    return f"Explore {META.title}"

def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan run_compare.")

def run_compare(ctx: ChapterContext) -> DemoResult:
    features = [
        "spread_pct", 
        "atr", 
        "unusual_volume",
        "bid_gap_pct",
        "fvwap_discount_pct"
    ]
    
    res = fetch_and_evaluate_pre_open(ctx.db_path, features, "Auction Quality")
    
    lines = [
        f"date={res['latest_date']}  n_samples={res['n_samples']}",
        "Perbandingan Modul Auction Quality Default vs Baseline",
        "",
        f"Baseline Rank IC : {res['baseline_ic']:+.3f}",
        f"Default Rank IC     : {res['against_ic']:+.3f}",
        "",
        "=== Analisis Bobot Pengaruh (XGBoost) ==="
    ]
    
    md_lines = [
        "# Modul Auction Quality Compare\n",
        "- **Baseline Rank IC:** " + f"{res['baseline_ic']:+.3f}",
        "- **Default Rank IC:** " + f"{res['against_ic']:+.3f}\n",
        "### Analisis Bobot Pengaruh",
    ]

    feat_imp = sorted(zip(res["features"], res["importances"]), key=lambda x: x[1], reverse=True)
    for name, imp in feat_imp:
        lines.append(f"  {name:<24} : {imp:5.1f}%")
        md_lines.append(f"- **{name}**: {imp:5.1f}%")

    return DemoResult(
        title="Pre-Open \u00b7 Auction Quality Audit",
        lines=lines,
        metrics={"n_samples": res["n_samples"], "baseline_ic": float(res["baseline_ic"]), "against_ic": float(res["against_ic"])},
        model="xgboost_auction",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )
