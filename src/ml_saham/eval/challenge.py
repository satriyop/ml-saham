"""Systemic Factor & Parameter Sensitivity Challenge Engine for ai-saham."""

from __future__ import annotations

from typing import Any

from ml_saham.chapters.loader import load_chapter
from ml_saham.chapters.types import ChapterContext


ENGINE_FACTORS = {
    "screener": [
        "pre-open-rank",
        "broker-accumulation",
        "bandar-detector",
        "broker-flow",
        "accum-policy",
        "pre-open-heuristic",
    ],
    "signal_engine": [
        "meta-ensemble",
        "factor-score",
        "relative-strength",
        "ichimoku-cloud",
        "pattern-fail",
        "earnings-surprise",
        "financial-quality",
        "forward-valuation",
        "analyst-consensus",
        "seasonality-drift",
    ],
    "risk_engine": [
        "volatility-sizing",
        "portfolio-small",
        "special-monitoring",
        "financial-distress",
    ],
    "market_context": [
        "market-regime",
        "sector-breadth",
        "nowcasting",
        "microstructure-impact",
    ],
    "other_aspects": [
        "cluster-peers",
        "broker-network",
        "volume-anomaly",
        "walk-forward",
        "research-pipeline",
        "rl-sandbox",
        "corp-events",
        "survival-analysis",
    ]
}


def _run_factor_challenge(chapter_ctx: ChapterContext, slugs: list[str]) -> dict[str, Any]:
    import inspect
    results = {}
    for slug in slugs:
        try:
            mod = load_chapter(slug)
            if not hasattr(mod, "run_compare"):
                continue
            
            sig = inspect.signature(mod.run_compare)
            kwargs = {}
            if "baseline" in sig.parameters:
                kwargs["baseline"] = "baseline"
            if "against" in sig.parameters:
                kwargs["against"] = "sota"
            
            res = mod.run_compare(chapter_ctx, **kwargs)
            
            # Safely extract metrics from compare dict or fallback to res.metrics
            compare_dict = getattr(res, "compare", None)
            sota_metrics = compare_dict.get("sota_metrics", res.metrics) if compare_dict else res.metrics
            baseline_metrics = compare_dict.get("baseline_metrics", {}) if compare_dict else {}
            
            results[slug] = {
                "model": res.model,
                "sota_metrics": sota_metrics,
                "baseline_metrics": baseline_metrics,
            }
        except Exception as e:
            results[slug] = {"error": str(e)}
    return results


def challenge_screener(chapter_ctx: ChapterContext) -> dict[str, Any]:
    """Challenge the pre-open and accum screener factors."""
    return _run_factor_challenge(chapter_ctx, ENGINE_FACTORS["screener"])


def challenge_engine(chapter_ctx: ChapterContext) -> dict[str, Any]:
    """Challenge the core engines: signal, risk, market context."""
    return {
        "signal_engine": _run_factor_challenge(chapter_ctx, ENGINE_FACTORS["signal_engine"]),
        "risk_engine": _run_factor_challenge(chapter_ctx, ENGINE_FACTORS["risk_engine"]),
        "market_context": _run_factor_challenge(chapter_ctx, ENGINE_FACTORS["market_context"]),
    }


def challenge_other(chapter_ctx: ChapterContext) -> dict[str, Any]:
    """Challenge other aspects (setup families, phase discovery, etc)."""
    return _run_factor_challenge(chapter_ctx, ENGINE_FACTORS["other_aspects"])


def run_full_challenge(chapter_ctx: ChapterContext) -> dict[str, Any]:
    """Run full challenge audit across all factors."""
    return {
        "screener": challenge_screener(chapter_ctx),
        "engine": challenge_engine(chapter_ctx),
        "other_aspects": challenge_other(chapter_ctx),
    }
