"""Lightweight progress tracking under ~/.ml-saham/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROGRESS_DIR = Path.home() / ".ml-saham"
PROGRESS_FILE = PROGRESS_DIR / "progress.json"


def _empty() -> dict[str, Any]:
    return {"schema_version": 1, "topics": {}}


def load_progress() -> dict[str, Any]:
    if not PROGRESS_FILE.exists():
        return _empty()
    try:
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    data.setdefault("schema_version", 1)
    data.setdefault("topics", {})
    return data


def save_progress(data: dict[str, Any]) -> None:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def mark(topic: str, action: str) -> None:
    """Mark topic action: explore | demo | deepdive."""
    data = load_progress()
    topics: dict[str, Any] = data.setdefault("topics", {})
    entry = topics.setdefault(topic, {})
    entry[action] = True
    save_progress(data)


def topic_flags(topic: str) -> dict[str, bool]:
    data = load_progress()
    entry = data.get("topics", {}).get(topic, {})
    return {
        "explore": bool(entry.get("explore")),
        "demo": bool(entry.get("demo")),
        "deepdive": bool(entry.get("deepdive")),
    }
