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
}


def load_chapter(slug: str) -> ModuleType:
    mod_name = _SLUG_TO_MOD.get(slug)
    if mod_name is None:
        raise KeyError(f"Belum ada modul chapter untuk topic {slug!r} (Phase 3 MVP saja).")
    return importlib.import_module(mod_name)


def has_chapter_module(slug: str) -> bool:
    return slug in _SLUG_TO_MOD
