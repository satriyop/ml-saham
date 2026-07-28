"""Load chapter modules by topic slug."""

from __future__ import annotations

import importlib
from types import ModuleType

_SLUG_TO_MOD = {
    "orientasi": "ml_saham.chapters.orientasi",
    "clean-prices": "ml_saham.chapters.clean_prices",
    "screen-rules": "ml_saham.chapters.screen_rules",
    "pattern-fail": "ml_saham.chapters.pattern_fail",
    "factor-score": "ml_saham.chapters.factor_score",
    "broker-flow": "ml_saham.chapters.broker_flow",
    "cluster-peers": "ml_saham.chapters.cluster_peers",
    "insider": "ml_saham.chapters.insider",
    "volume-anomaly": "ml_saham.chapters.volume_anomaly",
    "headline-tone": "ml_saham.chapters.headline_tone",
    "volatility-sizing": "ml_saham.chapters.volatility_sizing",
    "market-regime": "ml_saham.chapters.market_regime",
    "walk-forward": "ml_saham.chapters.walk_forward",
    "portfolio-small": "ml_saham.chapters.portfolio_small",
    "corp-events": "ml_saham.chapters.corp_events",
    "earnings-surprise": "ml_saham.chapters.earnings_surprise",
    "pre-open-rank": "ml_saham.chapters.pre_open_rank",
    "research-pipeline": "ml_saham.chapters.research_pipeline",
    "rl-sandbox": "ml_saham.chapters.rl_sandbox",
    "seasonality-drift": "ml_saham.chapters.seasonality_drift",
    "analyst-consensus": "ml_saham.chapters.analyst_consensus",
    "broker-accumulation": "ml_saham.chapters.broker_accumulation",
}


def load_chapter(slug: str) -> ModuleType:
    mod_name = _SLUG_TO_MOD.get(slug)
    if mod_name is None:
        raise KeyError(
            f"Belum ada modul chapter untuk topic {slug!r} "
            "(MVP + v1.1 + phase2 + optional — cek registry)."
        )
    return importlib.import_module(mod_name)


def has_chapter_module(slug: str) -> bool:
    return slug in _SLUG_TO_MOD
