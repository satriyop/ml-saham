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


class DiagnosticVerdict(str, Enum):
    """Diagnostic validity track — display / promote-candidate only (never Action)."""

    KEEP_DISPLAY = "KEEP_DISPLAY"
    DEMOTE_DISPLAY = "DEMOTE_DISPLAY"
    DROP_DISPLAY = "DROP_DISPLAY"
    PROMOTE_CANDIDATE = "PROMOTE_CANDIDATE"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED_DATA = "BLOCKED_DATA"
    BLOCKED_SPEC = "BLOCKED_SPEC"


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
        if self.score_kind == "flag_penalty_adjusted":
            return tuple(
                c.key
                for c in self.components
                if c.enabled and c.key != "production_raw_score"
            )
        if self.score_kind == "classification_band":
            return ("production_raw_score",)
        if self.score_kind == "gate_block":
            return tuple(c.key for c in self.enabled_components())
        if self.score_kind == "evidence_group_weights":
            return tuple(c.key for c in self.enabled_components())
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
    # WIN requires this many valid OOS folds (single-fold edge = provisional only)
    min_folds_for_win: int = 2


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
class HealthReportResult:
    """Orchestrated control-tower health pack (engine ± champion ± factors ± diagnostics)."""

    engine_id: str
    scenario_filter: str | None
    with_champion: bool
    with_factors: bool
    with_diagnostics: bool = False
    summary_md: str = ""
    lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    index: list[dict[str, Any]] = field(default_factory=list)
    engine_payload: dict[str, Any] = field(default_factory=dict)
    champion_payload: dict[str, Any] | None = None
    factors_payload: dict[str, Any] | None = None
    diagnostics_payload: dict[str, Any] | None = None
    artifact_dir: Path | None = None
    resolve_error: str | None = None

    def exit_code(self) -> int:
        if self.resolve_error:
            return 2
        return 0


@dataclass
class PromotePacketResult:
    """Human-only promote review pack (never applies to ai-saham)."""

    policy_id: str
    mode: str  # tune | champion
    summary_md: str = ""
    lines: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    artifact_dir: Path | None = None
    error: str | None = None

    def exit_code(self) -> int:
        return 2 if self.error else 0


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


@dataclass(frozen=True)
class DiagnosticFeature:
    key: str
    aliases: tuple[str, ...] = ()
    enabled: bool = True
    note: str = ""


@dataclass(frozen=True)
class DiagnosticSpec:
    """Frozen explain-only bag (ADR-057) — not a production PolicySpec."""

    diagnostic_id: str
    version: str
    hash: str
    engine: str
    scenario: str
    protocol_id: str
    features: tuple[DiagnosticFeature, ...]
    source: str = ""
    source_ref: str = ""
    control_score: str = "accum_production"
    kind: str = "diagnostic"
    banner: str = "ADR-057: not Action authority — display / promote-candidate only"

    def enabled_features(self) -> tuple[DiagnosticFeature, ...]:
        return tuple(f for f in self.features if f.enabled)


@dataclass
class DiagnosticChallengeResult:
    """Result of diagnostic validity for one bag field (or bag-level rollup)."""

    verdict: DiagnosticVerdict
    diagnostic_id: str
    protocol_id: str
    diagnostic_hash: str
    feature: str  # bag field key, or "_bag" for aggregate
    n_rows: int
    primary_horizon: int
    coverage: float | None = None
    mean_univariate_ic: float | None = None
    mean_residual_ic: float | None = None
    mean_redundancy: float | None = None  # |corr| vs production score
    fold_agree_residual_positive: float | None = None
    horizon_metrics: dict[str, Any] = field(default_factory=dict)
    fold_metrics: list[dict[str, Any]] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    summary_md: str = ""
    notes: list[str] = field(default_factory=list)
    artifact_dir: Path | None = None

    def exit_code(self) -> int:
        if self.verdict in (
            DiagnosticVerdict.BLOCKED_DATA,
            DiagnosticVerdict.BLOCKED_SPEC,
        ):
            return 2
        return 0


@dataclass
class BatchDiagnosticResult:
    """Batch diagnostic validity over enabled bag fields (shared prep)."""

    diagnostic_id: str
    protocol_id: str
    diagnostic_hash: str
    n_rows: int
    primary_horizon: int
    results: list[DiagnosticChallengeResult] = field(default_factory=list)
    blocked: DiagnosticVerdict | None = None
    lines: list[str] = field(default_factory=list)
    summary_md: str = ""
    notes: list[str] = field(default_factory=list)
    artifact_dir: Path | None = None

    def exit_code(self) -> int:
        if self.blocked in (
            DiagnosticVerdict.BLOCKED_DATA,
            DiagnosticVerdict.BLOCKED_SPEC,
        ):
            return 2
        return 0
