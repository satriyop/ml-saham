"""Systemic Factor & Parameter Sensitivity Challenge Engine for ai-saham."""

from __future__ import annotations

import inspect
from typing import Any

from ml_saham.chapters.loader import has_chapter_module, load_chapter
from ml_saham.chapters.types import ChapterContext


ENGINE_FACTORS = {
    "screener": [
        "pre-open-rank",
        "broker-accumulation",
        "bandar-detector",
        "broker-flow",
        "accum-policy",
        "accum-macro",
        "accum-deep",
        "pre-open-heuristic",
        "pre-open-direction",
        "pre-open-participation",
        "pre-open-auction",
        "pre-open-macro",
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
    ],
}

# Safe defaults for chapters that require baseline/against keyword args.
_DEFAULT_BASELINE = "equal-weight"
_DEFAULT_AGAINST = "elastic-net"

# Per-factor overrides (chapter APIs use different baseline ids).
_COMPARE_KWARGS_BY_SLUG: dict[str, dict[str, str]] = {
    "pattern-fail": {"baseline": "coinflip", "against": "lgbm"},
    "factor-score": {"baseline": "equal-weight", "against": "elastic-net"},
    "broker-network": {"baseline": "degree", "against": "pagerank"},
    "relative-strength": {"baseline": "rs", "against": "ml"},
    "financial-distress": {"baseline": "altman-z", "against": "xgboost"},
    "earnings-surprise": {"baseline": "naive_pe", "against": "lightgbm"},
    "survival-analysis": {"baseline": "kaplan-meier", "against": "ridge"},
}


def all_engine_slugs() -> list[str]:
    """Deduped factor slugs from ENGINE_FACTORS (challenge SSOT)."""
    seen: set[str] = set()
    out: list[str] = []
    for slugs in ENGINE_FACTORS.values():
        for s in slugs:
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _compare_kwargs(slug: str, run_compare) -> dict[str, Any]:
    """Build kwargs for run_compare using slug-aware baseline/against ids."""
    sig = inspect.signature(run_compare)
    params = sig.parameters
    if "baseline" not in params and "against" not in params:
        return {}
    override = _COMPARE_KWARGS_BY_SLUG.get(slug, {})
    kwargs: dict[str, Any] = {}
    if "baseline" in params:
        kwargs["baseline"] = override.get("baseline", _DEFAULT_BASELINE)
    if "against" in params:
        kwargs["against"] = override.get("against", _DEFAULT_AGAINST)
    return kwargs


def _run_factor_challenge(chapter_ctx: ChapterContext, slugs: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for slug in slugs:
        try:
            if not has_chapter_module(slug):
                results[slug] = {"error": f"chapter module not loadable: {slug}"}
                continue
            mod = load_chapter(slug)
            if not hasattr(mod, "run_compare"):
                results[slug] = {"error": "missing run_compare (challenge contract)"}
                continue

            res = mod.run_compare(chapter_ctx, **_compare_kwargs(slug, mod.run_compare))

            compare_dict = getattr(res, "compare", None)
            if isinstance(compare_dict, dict) and compare_dict:
                sota_metrics = compare_dict.get("sota_metrics") or compare_dict.get(
                    "against", res.metrics
                )
                baseline_metrics = compare_dict.get("baseline_metrics") or compare_dict.get(
                    "baseline", {}
                )
            else:
                sota_metrics = res.metrics
                baseline_metrics = {}

            results[slug] = {
                "title": res.title,
                "model": res.model,
                "sota_metrics": sota_metrics,
                "baseline_metrics": baseline_metrics,
                "summary": res.summary_md,
                "ok": True,
            }
        except Exception as e:
            results[slug] = {"error": str(e), "ok": False}
    return results


def challenge_summary(results: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested challenge results into ok/error counts."""
    flat: dict[str, Any] = {}
    for _group, payload in results.items():
        if isinstance(payload, dict) and payload and "error" not in payload and "title" not in payload:
            # group map slug -> result
            flat.update(payload)
        elif isinstance(payload, dict):
            # already flat slug map
            for k, v in payload.items():
                if isinstance(v, dict):
                    flat[k] = v
    ok = [s for s, v in flat.items() if isinstance(v, dict) and not v.get("error")]
    err = [s for s, v in flat.items() if isinstance(v, dict) and v.get("error")]
    return {
        "n_total": len(flat),
        "n_ok": len(ok),
        "n_error": len(err),
        "ok": sorted(ok),
        "errors": {s: flat[s].get("error") for s in err},
    }


def challenge_screener(chapter_ctx: ChapterContext, scenario: str | None = None) -> dict[str, Any]:
    """Challenge the pre-open and accum screener factors."""
    factors = ENGINE_FACTORS["screener"]
    if scenario == "pre-open":
        if chapter_ctx.eval_type == "direction":
            factors = ["pre-open-direction"]
        elif chapter_ctx.eval_type == "participation":
            factors = ["pre-open-participation"]
        elif chapter_ctx.eval_type == "auction":
            factors = ["pre-open-auction"]
        elif chapter_ctx.eval_type == "macro":
            factors = ["pre-open-macro"]
        else:
            factors = ["pre-open-heuristic"]
    elif scenario == "accum":
        if chapter_ctx.eval_type == "macro":
            factors = ["accum-macro"]
        elif chapter_ctx.eval_type == "deep":
            factors = ["accum-deep"]
        else:
            factors = ["accum-policy"]
    return _run_factor_challenge(chapter_ctx, factors)


def challenge_engine(chapter_ctx: ChapterContext, category: str | None = None, eval_type: str | None = None) -> dict[str, Any]:
    """Challenge the core engines: signal, risk, market context."""
    results = {}
    
    # Run Signal Engine
    if category is None or category == "signal":
        factors = ENGINE_FACTORS["signal_engine"]
        if eval_type == "ensemble":
            factors = ["meta-ensemble"]
        elif eval_type == "flow":
            factors = ["broker-flow"]
        results.update(_run_factor_challenge(chapter_ctx, factors))
        
    # Run Risk Engine
    if category is None or category == "risk":
        factors = ENGINE_FACTORS["risk_engine"]
        if eval_type == "gating":
            factors = ["special-monitoring"]
        elif eval_type == "sizing":
            factors = ["volatility-sizing"]
        results.update(_run_factor_challenge(chapter_ctx, factors))
        
    # Run Market Context
    if category is None or category == "market":
        factors = ENGINE_FACTORS["market_context"]
        if eval_type == "regime":
            factors = ["market-regime"]
        elif eval_type == "breadth":
            factors = ["sector-breadth"]
        results.update(_run_factor_challenge(chapter_ctx, factors))

    return results


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
