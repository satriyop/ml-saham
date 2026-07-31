"""Load live-shaped golden JSON for challenge payload contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_GOLDEN_DIR = Path(__file__).resolve().parent


def golden_path(name: str) -> Path:
    p = _GOLDEN_DIR / name
    if not p.is_file():
        raise FileNotFoundError(f"missing golden fixture: {p}")
    return p


def load_golden(name: str) -> Any:
    return json.loads(golden_path(name).read_text(encoding="utf-8"))
