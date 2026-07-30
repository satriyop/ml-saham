"""Lightweight progress tracking under ~/.ml-saham (or ML_SAHAM_HOME)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ENV_HOME = "ML_SAHAM_HOME"


def progress_dir() -> Path:
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".ml-saham"


def progress_file() -> Path:
    return progress_dir() / "progress.json"


# Back-compat aliases (resolved at import — prefer progress_dir()/progress_file())
PROGRESS_DIR = Path.home() / ".ml-saham"
PROGRESS_FILE = PROGRESS_DIR / "progress.json"


def _empty() -> dict[str, Any]:
    return {"schema_version": 1, "topics": {}}


def load_progress() -> dict[str, Any]:
    path = progress_file()
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    data.setdefault("schema_version", 1)
    data.setdefault("topics", {})
    return data


def save_progress(data: dict[str, Any]) -> None:
    d = progress_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "progress.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def mark(topic: str, action: str) -> None:
    """Mark topic action: explore | demo."""
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
    }
