"""Resolve path to market SQLite database."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB = Path.home() / "dev" / "ai-saham" / "data" / "db" / "data.db"
ENV_DB = "ML_SAHAM_DB"


def resolve_db_path(cli_db: Path | str | None = None) -> Path:
    """Resolve DB path: --db > ML_SAHAM_DB > default ai-saham path."""
    if cli_db is not None:
        return Path(cli_db).expanduser().resolve()
    env = os.environ.get(ENV_DB)
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_DB.expanduser().resolve()
