"""Ch.44 Pre-open Macro (All Features) Audit."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.chapters.pre_open_base import fetch_and_evaluate_pre_open

META = get_meta("pre-open-macro")


def explore_text(*, verbose: bool = False) -> str:
    return f"Explore {META.title}"


def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan run_compare.")


def run_compare(ctx: ChapterContext) -> DemoResult:
    features = [
        "iep_gap_pct", "bid_offer_imbalance", "book_pressure",
        "delta_iev", "delta_iev_ratio", "iev_intensity", "iev",
        "spread_pct", "atr", "unusual_volume", "bid_gap_pct", "fvwap_discount_pct",
        "opening_broker_backing_score", "opening_broker_buy_streak"
    ]
    
    res = fetch_and_evaluate_pre_open(ctx.db_path, features, "Macro (Full)")
    
    lines = [
        f"date={res['latest_date']}  n_samples={res['n_samples']}",
        "Perbandingan Modul Macro (Full Pre-Open) Default vs Baseline",
        "",
        f"Baseline Rank IC : {res['baseline_ic']:+.3f}",
        f"Default Rank IC     : {res['against_ic']:+.3f}",
        "",
        "=== Top Fitur Penggerak Cuan (XGBoost) ==="
    ]
    
    md_lines = [
        "# Modul Macro (Full) Compare\n",
        "- **Baseline Rank IC:** " + f"{res['baseline_ic']:+.3f}",
        "- **Default Rank IC:** " + f"{res['against_ic']:+.3f}\n",
        "### Analisis Bobot Pengaruh Keseluruhan",
    ]

    feat_imp = sorted(zip(res["features"], res["importances"]), key=lambda x: x[1], reverse=True)
    for name, imp in feat_imp:
        if imp > 0.1:
            lines.append(f"  {name:<30} : {imp:5.1f}%")
            md_lines.append(f"- **{name}**: {imp:5.1f}%")

    return DemoResult(
        title="Pre-Open \u00b7 Macro Audit",
        lines=lines,
        metrics={"n_samples": res["n_samples"], "baseline_ic": float(res["baseline_ic"]), "against_ic": float(res["against_ic"])},
        model="xgboost_macro",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )

def deepdive_text() -> str:
    return deepdive_stub(topic=META.slug, related="screener / pre-open", bring_back="Pre-Open")
