"""Core types for ADR-002 challenge system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ChallengeStatus(str, Enum):
    WIN = "WIN"
    LOSE = "LOSE"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED_DATA = "BLOCKED_DATA"
    BLOCKED_POLICY = "BLOCKED_POLICY"


class FactorVerdict(str, Enum):
    """Factor validity track (keep/drop) — not policy WIN/LOSE."""

    KEEP = "KEEP"
    DEMOTE = "DEMOTE"
    DROP_CANDIDATE = "DROP_CANDIDATE"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED_DATA = "BLOCKED_DATA"
    BLOCKED_POLICY = "BLOCKED_POLICY"


@dataclass(frozen=True)
class ComponentWeight:
    key: str
    weight: float
    enabled: bool
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicySnapshot:
    policy_id: str
    version: str
    hash: str
    max_score: float
    components: tuple[ComponentWeight, ...]
    source: str = ""
    source_ref: str = ""
    protocol_id: str = "accum_path_v1"
    panel_kind: str = "accum_components"
    score_kind: str = "weighted_sleeves"

    def enabled_components(self) -> tuple[ComponentWeight, ...]:
        return tuple(c for c in self.components if c.enabled and c.weight > 0)

    def weight_map(self) -> dict[str, float]:
        return {c.key: c.weight for c in self.enabled_components()}

    def feature_keys(self) -> tuple[str, ...]:
        """Feature sleeves for equal/ridge challengers (exclude primary production score)."""
        if self.score_kind == "rank_primary":
            return tuple(
                c.key
                for c in self.components
                if c.key != "official_rank_score"
            )
        if self.score_kind == "raw_score_primary":
            return tuple(
                c.key
                for c in self.components
                if c.key != "production_raw_score"
            )
        return tuple(c.key for c in self.enabled_components())


@dataclass(frozen=True)
class Protocol:
    protocol_id: str
    primary_horizon: int
    horizons_report: tuple[int, ...]
    min_n_total: int
    min_n_test: int
    n_folds: int
    embargo_sessions: int
    win_margin: float
    min_fold_agree: float  # fraction of folds challenger must win
    label: str = "excess_vs_ihsg"
    costs: str = "gross_banner"


@dataclass
class ChallengeResult:
    status: ChallengeStatus
    policy_id: str
    protocol_id: str
    baseline_id: str
    against_id: str
    policy_hash: str
    n_rows: int
    primary_horizon: int
    primary_ic_baseline: float | None = None
    primary_ic_against: float | None = None
    horizon_metrics: dict[str, Any] = field(default_factory=dict)
    fold_metrics: list[dict[str, Any]] = field(default_factory=list)
    weights: dict[str, Any] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    summary_md: str = ""
    notes: list[str] = field(default_factory=list)
    artifact_dir: Path | None = None

    def exit_code(self) -> int:
        if self.status in (ChallengeStatus.BLOCKED_DATA, ChallengeStatus.BLOCKED_POLICY):
            return 2
        return 0


@dataclass
class FactorChallengeResult:
    """Result of factor validity track (univariate + drop ablation)."""

    verdict: FactorVerdict
    policy_id: str
    protocol_id: str
    policy_hash: str
    factor: str
    n_rows: int
    primary_horizon: int
    mean_delta_ic: float | None = None  # full - drop (positive => factor helps)
    mean_univariate_ic: float | None = None
    fold_agree_positive_delta: float | None = None
    horizon_metrics: dict[str, Any] = field(default_factory=dict)
    fold_metrics: list[dict[str, Any]] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    summary_md: str = ""
    notes: list[str] = field(default_factory=list)
    artifact_dir: Path | None = None

    def exit_code(self) -> int:
        if self.verdict in (FactorVerdict.BLOCKED_DATA, FactorVerdict.BLOCKED_POLICY):
            return 2
        return 0


@dataclass
class EnginePolicyRow:
    """One policy row inside an engine portfolio rollup."""

    engine_id: str
    scenario: str
    policy_id: str
    protocol_id: str
    policy_hash: str
    status: str  # ChallengeStatus.value or "ERROR"
    n_rows: int
    primary_horizon: int | None
    primary_ic_baseline: float | None
    primary_ic_against: float | None
    against_id: str
    notes: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class EnginePortfolioResult:
    """ADR-002 engine portfolio rollup over PolicySpecs."""

    engine_id: str
    scenario_filter: str | None  # None = all
    against_id: str
    baseline_id: str
    rows: list[EnginePolicyRow] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    summary_md: str = ""
    notes: list[str] = field(default_factory=list)
    artifact_dir: Path | None = None
    resolve_error: str | None = None  # unknown engine/scenario

    def exit_code(self) -> int:
        if self.resolve_error:
            return 2
        return 0


@dataclass
class BatchFactorResult:
    """Batch factor validity over all enabled sleeves (shared prep)."""

    policy_id: str
    protocol_id: str
    policy_hash: str
    n_rows: int
    primary_horizon: int
    results: list[FactorChallengeResult] = field(default_factory=list)
    blocked: FactorVerdict | None = None  # prep-level only
    lines: list[str] = field(default_factory=list)
    summary_md: str = ""
    notes: list[str] = field(default_factory=list)
    artifact_dir: Path | None = None

    def exit_code(self) -> int:
        if self.blocked in (FactorVerdict.BLOCKED_DATA, FactorVerdict.BLOCKED_POLICY):
            return 2
        return 0
