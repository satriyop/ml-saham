"""Shared chapter runtime types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ChapterContext:
    db_path: Path
    universe: list[str]
    as_of: str | None = None
    with_costs: bool = False
    verbose: bool = False
    scenario: str | None = None
    eval_type: str | None = None


@dataclass
class DemoResult:
    title: str
    lines: list[str]
    metrics: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    summary_md: str = ""
    scoreboard: bool = True  # False for Ch.3 failure-lab style
    scoreboard_kind: str = "long_only"  # long_only | open_session | none
    top_names: list[dict[str, Any]] = field(default_factory=list)
    extra_files: dict[str, str] = field(default_factory=dict)


@dataclass
class CompareResult:
    title: str
    lines: list[str]
    metrics: dict[str, Any] = field(default_factory=dict)
    compare: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    summary_md: str = ""
    scoreboard: bool = True
    winner: str | None = None  # optional label for baseline vs against outcomes
    winner_reason: str | None = None
