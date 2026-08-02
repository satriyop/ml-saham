"""Typed application boundary shared by challenge presentation adapters.

Phase 0: configuration and product-boundary context only.
Phase 1A: read-only Control Tower, cohort inventory, Policy Catalog.
Phase 1B: deferred optional C0 readiness enrichment (not required for Phase 2).
Phase 2: explicit immutable policy-run requests + synchronous Result Inspector
DTO (session-scoped attempt idempotency owned by the presentation adapter).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ml_saham.artifacts import resolve_artifacts_root
from ml_saham.challenge.artifacts import (
    CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION,
    HISTORICAL_CHALLENGE_ARTIFACT_SCHEMA_VERSIONS,
)
from ml_saham.challenge.diagnostics.registry import list_diagnostics
from ml_saham.challenge.policies.registry import load_policy, load_policy_adapter
from ml_saham.challenge.production_policy_snapshots import REQUIRED_POLICIES
from ml_saham.challenge.health import build_health_report
from ml_saham.challenge.promote import build_promote_packet
from ml_saham.challenge.protocols import get_protocol
from ml_saham.challenge.runner import list_policies, run_policy_challenge
from ml_saham.challenge.types import ChallengeResult, ChallengeStatus, HealthReportResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.connection import resolve_db_path
from ml_saham.data.observation_cohort import (
    ACCUM_PURPOSE_LIKE,
    ACCUM_PURPOSES,
    PRE_OPEN_PURPOSE_LIKE,
    PRE_OPEN_PURPOSES,
    list_compatibility_cohorts,
)

# UI / presentation capability only — not a challenge verdict.
CAPABILITY_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
CAPABILITY_AVAILABLE = "AVAILABLE"
CAPABILITY_UNAVAILABLE = "UNAVAILABLE"

VERDICT_STATUSES = frozenset(
    {
        "WIN",
        "LOSE",
        "INCONCLUSIVE",
        "BLOCKED_DATA",
        "BLOCKED_POLICY",
        "KEEP",
        "DEMOTE",
        "DROP_CANDIDATE",
        "KEEP_DISPLAY",
        "DEMOTE_DISPLAY",
        "PROMOTE_CANDIDATE",
    }
)

_TRACK_BY_MODE = {
    "challenge_run": "tune",
    "challenge_factor": "factor",
    "challenge_health": "health",
    "challenge_champion": "champion",
    "challenge_diagnostic": "diagnostic",
    "challenge_engine": "tune",
    "challenge_promote_packet": "promote_packet",
}

_TRACK_BY_MANIFEST_TRACK = {
    "policy_tournament": "tune",
    "factor_validity": "factor",
    "champion": "champion",
    "diagnostic": "diagnostic",
    "diagnostic_validity": "diagnostic",
}


class PurposeFamily(str, Enum):
    ACCUM = "ACCUM"
    PRE_OPEN = "PRE_OPEN"


@dataclass(frozen=True)
class ChallengeWorkbenchConfig:
    """Immutable runtime configuration for challenge presentation adapters."""

    upstream_db_path: Path
    artifacts_root: Path


@dataclass(frozen=True)
class ChallengeWorkbenchOverview:
    """Shell context; contains no policy, metric, or verdict data."""

    product_name: str
    product_role: str
    upstream_db_path: Path
    upstream_access_mode: str
    artifacts_root: Path
    challenge_authority: str
    curriculum_authority: str
    production_changes: str


@dataclass(frozen=True)
class CapabilityField:
    """Presentation-layer capability for fields not yet owned by a projection."""

    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class PolicyCatalogRow:
    """Canonical policy inventory row (registry-backed; no cohort readiness)."""

    policy_id: str
    version: str
    protocol_id: str
    panel_kind: str
    score_kind: str
    decision_type: str
    adapter_id: str | None
    adapter_version: str | None
    supported_baselines: tuple[str, ...]
    supported_challengers: tuple[str, ...]
    support_status: str
    support_reason: str
    readiness_capability: CapabilityField


@dataclass(frozen=True)
class CohortInventoryRow:
    """Factual purpose-family cohort inventory; never implies selection authority."""

    purpose_family: str
    compatibility_id: str
    observation_count: int
    max_captured_at: str | None
    distinct_sessions: CapabilityField
    economic_date_range: CapabilityField
    readiness_capability: CapabilityField


@dataclass(frozen=True)
class CohortInventoryResult:
    """Typed cohort inventory with inventory-level status."""

    status: str
    purpose_families: tuple[str, ...]
    rows: tuple[CohortInventoryRow, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalResultRow:
    """One historical challenge pack summary for Control Tower display."""

    track: str
    status: str
    mode: str
    policy_id: str | None
    protocol_id: str | None
    baseline_id: str | None
    against_id: str | None
    factor: str | None
    diagnostic_id: str | None
    created_at: str | None
    artifact_path: str
    schema_version: int | None
    is_diagnostic_display: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControlTowerSnapshot:
    """Read-only historical result view; never executes challenges."""

    status: str
    rows: tuple[HistoricalResultRow, ...]
    by_track: Mapping[str, int] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiagnosticCatalogRow:
    """Explain-only diagnostic bag inventory (never Action authority)."""

    diagnostic_id: str
    version: str
    protocol_id: str
    engine: str
    scenario: str
    n_features: int
    authority_note: str


@dataclass(frozen=True)
class ProtocolSummary:
    """Read-only Protocol identity for the Run form (no law changes)."""

    protocol_id: str
    primary_horizon: int
    horizons_report: tuple[int, ...]
    min_n_total: int
    min_n_test: int
    n_folds: int
    embargo_sessions: int
    min_folds_for_win: int
    win_margin: float
    min_fold_agree: float
    label: str
    costs: str


@dataclass(frozen=True)
class ChallengeRunRequest:
    """Immutable submitted run request. request_id covers all material fields."""

    request_id: str
    verb: str
    policy_id: str
    baseline_id: str
    against_id: str
    compatibility_id: str
    purpose_family: str
    protocol_id: str
    write_artifact: bool
    db_path: str
    artifacts_root: str


@dataclass(frozen=True)
class ChallengeRunView:
    """Presentation DTO for one completed attempt (product state or error)."""

    request_id: str
    attempt_id: str
    kind: str  # product_result | application_error
    status: str
    policy_id: str
    protocol_id: str
    baseline_id: str
    against_id: str
    policy_hash: str
    n_rows: int
    primary_horizon: int
    primary_ic_baseline: float | None
    primary_ic_against: float | None
    horizon_metrics: dict[str, Any]
    fold_metrics: tuple[dict[str, Any], ...]
    min_folds_for_win: int | None
    n_folds_reported: int
    weights: dict[str, Any]
    lines: tuple[str, ...]
    notes: tuple[str, ...]
    summary_md: str
    observation_compatibility_id: str
    production_snapshot_id: str
    production_snapshot_digest: str
    production_policy_id: str
    production_policy_version: str
    production_semantic_engine_contract_id: str
    challenge_adapter_id: str
    challenge_adapter_version: str
    population_identity_kind: str
    population_identity_id: str
    population_identity_detail: dict[str, Any]
    artifact_dir: str | None
    elapsed_seconds: float
    human_next_step: str
    error_reference: str | None = None


@dataclass(frozen=True)
class ArtifactListItem:
    """One pack under the challenge artifact tree (list only; open validates)."""

    artifact_path: str
    mode: str
    track: str
    status: str
    policy_id: str | None
    protocol_id: str | None
    baseline_id: str | None
    against_id: str | None
    schema_version: int | None
    created_at: str | None
    openable: bool
    open_block_reason: str | None
    promotion_eligible_hint: bool
    promotion_block_reason: str | None


@dataclass(frozen=True)
class ArtifactFileEntry:
    """Existing on-disk file in a validated pack (exact bytes for download)."""

    name: str
    size_bytes: int
    media_hint: str  # json | markdown | other


@dataclass(frozen=True)
class ArtifactOpenView:
    """Validated reopen result for display (not necessarily promote-eligible)."""

    ok: bool
    artifact_path: str
    mode: str
    track: str
    status: str
    schema_version: int | None
    policy_id: str | None
    protocol_id: str | None
    baseline_id: str | None
    against_id: str | None
    primary_horizon: int | None
    n_rows: int | None
    primary_ic_baseline: float | None
    primary_ic_against: float | None
    horizon_metrics: dict[str, Any]
    fold_metrics: tuple[dict[str, Any], ...]
    observation_compatibility_id: str | None
    population_identity_kind: str | None
    population_identity_id: str | None
    production_snapshot_id: str | None
    challenge_adapter_id: str | None
    files: tuple[ArtifactFileEntry, ...]
    summary_md: str
    manifest: dict[str, Any]
    metrics: dict[str, Any]
    historical_display_only: bool
    promotion_eligible: bool
    promotion_block_reason: str | None
    notes: tuple[str, ...]
    error: str | None = None


@dataclass(frozen=True)
class ArtifactCompareAxis:
    name: str
    left: str
    right: str
    compatible: bool


@dataclass(frozen=True)
class ArtifactCompareView:
    """Side-by-side compare; deltas only when all required axes match."""

    left_path: str
    right_path: str
    compatible: bool
    axes: tuple[ArtifactCompareAxis, ...]
    left_status: str
    right_status: str
    left_ic_baseline: float | None
    right_ic_baseline: float | None
    left_ic_against: float | None
    right_ic_against: float | None
    delta_ic_against: float | None
    winner_banner: str | None  # only when compatible and statuses comparable
    notes: tuple[str, ...]


@dataclass(frozen=True)
class PromotePacketView:
    """Human review packet result (never applies to ai-saham)."""

    ok: bool
    policy_id: str
    mode: str
    lines: tuple[str, ...]
    summary_md: str
    evidence: dict[str, Any]
    artifact_dir: str | None
    error: str | None
    auto_applied: bool = False


@dataclass(frozen=True)
class LatestHealthPack:
    """Most recent challenge/health/* pack under the artifacts root."""

    found: bool
    artifact_path: str | None
    created_at: str | None
    engine_id: str | None
    with_diagnostics: bool | None
    with_factors: bool | None
    with_champion: bool | None
    n_index: int | None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class HealthRunRequest:
    """Immutable weekly health request (session attempt idempotency in UI)."""

    request_id: str
    verb: str
    engine_id: str
    scenario: str
    with_diagnostics: bool
    with_factors: bool
    with_champion: bool
    champion_model: str
    compatibility_id: str
    write_artifact: bool
    db_path: str
    artifacts_root: str


@dataclass(frozen=True)
class HealthRunView:
    """Presentation DTO for one health attempt."""

    request_id: str
    attempt_id: str
    kind: str  # product_result | application_error
    status: str
    engine_id: str
    scenario_filter: str | None
    with_diagnostics: bool
    with_factors: bool
    with_champion: bool
    lines: tuple[str, ...]
    notes: tuple[str, ...]
    summary_md: str
    index: tuple[dict[str, Any], ...]
    artifact_dir: str | None
    elapsed_seconds: float
    human_next_step: str
    resolve_error: str | None = None
    error_reference: str | None = None


class ChallengeWorkbenchService:
    """Application facade for CLI/UI challenge presentation surfaces."""

    def __init__(self, config: ChallengeWorkbenchConfig) -> None:
        self._config = config

    @property
    def config(self) -> ChallengeWorkbenchConfig:
        return self._config

    def describe(self) -> ChallengeWorkbenchOverview:
        """Return static shell context without opening or mutating either path."""
        return ChallengeWorkbenchOverview(
            product_name="ml-saham Challenge Desk",
            product_role="Offline challenge lab",
            upstream_db_path=self._config.upstream_db_path,
            upstream_access_mode="read-only",
            artifacts_root=self._config.artifacts_root,
            challenge_authority="Deterministic ml-saham challenge contracts",
            curriculum_authority="Learning only; never challenge authority",
            production_changes="Human review only; automatic promotion is disabled",
        )

    def list_policy_catalog(self) -> tuple[PolicyCatalogRow, ...]:
        """Canonical policy inventory equal to the registry behind challenge list."""
        readiness = CapabilityField(
            name="cohort_protocol_readiness",
            status=CAPABILITY_NOT_IMPLEMENTED,
            detail=(
                "C0 producer/Protocol readiness projection is not available in "
                "Phase 1A; no eligibility, fold estimate, or blocker is inferred."
            ),
        )
        rows: list[PolicyCatalogRow] = []
        for base in list_policies():
            pid = str(base["policy_id"])
            adapter_id: str | None = None
            adapter_version: str | None = None
            challengers: tuple[str, ...] = ()
            support_status = "registered"
            baselines = ("production", "static_reference")
            if pid in REQUIRED_POLICIES:
                support_reason = (
                    "Production-facing policy; verified snapshot required at run"
                )
            else:
                support_reason = "Present in ml-saham challenge policy registry"
            try:
                try:
                    adapter = load_policy_adapter(pid)
                    adapter_id = adapter.adapter_id
                    adapter_version = adapter.adapter_version
                    challengers = tuple(adapter.supported_challengers)
                    if pid in REQUIRED_POLICIES:
                        support_reason = (
                            f"Verified-snapshot policy via adapter "
                            f"{adapter.adapter_id}@{adapter.adapter_version}"
                        )
                    else:
                        support_reason = (
                            f"Adapter {adapter.adapter_id}@{adapter.adapter_version}"
                        )
                except KeyError:
                    pol = load_policy(pid)
                    support_reason = (
                        f"Local execution fixture ({pol.source or 'fixture'})"
                    )
            except Exception as exc:  # noqa: BLE001 — surface as support note
                support_status = "error"
                support_reason = f"Catalog row error: {type(exc).__name__}: {exc}"

            decision_type = _decision_type(
                panel_kind=str(base.get("panel_kind") or ""),
                score_kind=str(base.get("score_kind") or ""),
                policy_id=pid,
            )
            rows.append(
                PolicyCatalogRow(
                    policy_id=pid,
                    version=str(base.get("version") or "v1"),
                    protocol_id=str(base.get("protocol") or ""),
                    panel_kind=str(base.get("panel_kind") or ""),
                    score_kind=str(base.get("score_kind") or ""),
                    decision_type=decision_type,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    supported_baselines=baselines,
                    supported_challengers=challengers,
                    support_status=support_status,
                    support_reason=support_reason,
                    readiness_capability=readiness,
                )
            )
        return tuple(rows)

    def list_diagnostic_catalog(self) -> tuple[DiagnosticCatalogRow, ...]:
        """Explain-only diagnostic bags — never Action / ENTER authority."""
        note = (
            "Diagnostic display / PROMOTE_CANDIDATE only — never Action authority "
            "(ADR-057)."
        )
        out: list[DiagnosticCatalogRow] = []
        for row in list_diagnostics():
            out.append(
                DiagnosticCatalogRow(
                    diagnostic_id=str(row["diagnostic_id"]),
                    version=str(row.get("version") or ""),
                    protocol_id=str(row.get("protocol") or ""),
                    engine=str(row.get("engine") or ""),
                    scenario=str(row.get("scenario") or ""),
                    n_features=int(row.get("n_features") or 0),
                    authority_note=note,
                )
            )
        return tuple(out)

    def list_cohort_inventory(
        self,
        *,
        purpose_families: tuple[str, ...] | None = None,
    ) -> CohortInventoryResult:
        """List purpose-family compatibility IDs with factual counts only.

        Never auto-selects largest/latest/only cohort. Distinct sessions and
        economic date range remain NOT_IMPLEMENTED until a typed projection ships.
        """
        families = purpose_families or (
            PurposeFamily.ACCUM.value,
            PurposeFamily.PRE_OPEN.value,
        )
        sessions_cap = CapabilityField(
            name="distinct_economic_sessions",
            status=CAPABILITY_NOT_IMPLEMENTED,
            detail=(
                "Distinct economic session count is not yet exposed by the "
                "typed cohort inventory boundary."
            ),
        )
        date_cap = CapabilityField(
            name="economic_date_range",
            status=CAPABILITY_NOT_IMPLEMENTED,
            detail=(
                "Economic min/max date range is not yet exposed by the typed "
                "cohort inventory boundary."
            ),
        )
        readiness = CapabilityField(
            name="cohort_protocol_readiness",
            status=CAPABILITY_NOT_IMPLEMENTED,
            detail=(
                "C0 producer/Protocol readiness is not available in Phase 1A."
            ),
        )

        db_path = self._config.upstream_db_path
        if not db_path.is_file():
            return CohortInventoryResult(
                status=CAPABILITY_UNAVAILABLE,
                purpose_families=tuple(families),
                rows=(),
                notes=(f"Upstream DB not found (read-only path): {db_path}",),
            )

        rows: list[CohortInventoryRow] = []
        notes: list[str] = []
        try:
            with connect(db_path) as conn:
                for family in families:
                    if family == PurposeFamily.ACCUM.value:
                        cohorts = list_compatibility_cohorts(
                            conn,
                            purposes=ACCUM_PURPOSES,
                            purpose_like=ACCUM_PURPOSE_LIKE,
                        )
                    elif family == PurposeFamily.PRE_OPEN.value:
                        cohorts = list_compatibility_cohorts(
                            conn,
                            purposes=PRE_OPEN_PURPOSES,
                            purpose_like=PRE_OPEN_PURPOSE_LIKE,
                        )
                    else:
                        notes.append(f"Unknown purpose family skipped: {family}")
                        continue
                    for cid, n_rows, max_cap in cohorts:
                        rows.append(
                            CohortInventoryRow(
                                purpose_family=family,
                                compatibility_id=cid if cid else "(untagged)",
                                observation_count=int(n_rows),
                                max_captured_at=max_cap,
                                distinct_sessions=sessions_cap,
                                economic_date_range=date_cap,
                                readiness_capability=readiness,
                            )
                        )
        except FileNotFoundError as exc:
            return CohortInventoryResult(
                status=CAPABILITY_UNAVAILABLE,
                purpose_families=tuple(families),
                rows=(),
                notes=(str(exc),),
            )
        except Exception as exc:  # noqa: BLE001 — typed unavailable, not empty-zero
            return CohortInventoryResult(
                status="ERROR",
                purpose_families=tuple(families),
                rows=(),
                notes=(f"{type(exc).__name__}: {exc}",),
            )

        status = CAPABILITY_AVAILABLE if rows else CAPABILITY_UNAVAILABLE
        if not rows and not notes:
            notes.append("No purpose-family compatibility cohorts found")
        return CohortInventoryResult(
            status=status,
            purpose_families=tuple(families),
            rows=tuple(rows),
            notes=tuple(notes),
        )

    def control_tower_snapshot(
        self,
        *,
        limit: int = 100,
    ) -> ControlTowerSnapshot:
        """Scan validated historical challenge manifests under artifacts root.

        Phase 1A is read-only: never runs health/engine/factor/challenge. Empty
        artifact tree is a normal unavailable state, not a product verdict.
        """
        root = self._config.artifacts_root / "challenge"
        if not root.is_dir():
            return ControlTowerSnapshot(
                status=CAPABILITY_UNAVAILABLE,
                rows=(),
                by_track={},
                notes=(f"No challenge artifact tree at {root}",),
            )

        rows: list[HistoricalResultRow] = []
        notes: list[str] = []
        for manifest_path in sorted(
            root.rglob("manifest.json"),
            key=lambda p: p.stat().st_mtime if p.is_file() else 0.0,
            reverse=True,
        ):
            if len(rows) >= limit:
                notes.append(f"Truncated to {limit} most recent packs")
                break
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                notes.append(f"Unreadable manifest {manifest_path}: {exc}")
                continue
            if not isinstance(payload, dict):
                notes.append(f"Non-object manifest skipped: {manifest_path}")
                continue
            row = _historical_row_from_manifest(payload, manifest_path)
            if row is None:
                notes.append(f"Unsupported or incomplete manifest: {manifest_path}")
                continue
            # Health packs expand index into multiple tower rows when present.
            if row.mode == "challenge_health":
                expanded = _expand_health_index(manifest_path.parent, row)
                if expanded:
                    for item in expanded:
                        if len(rows) >= limit:
                            break
                        rows.append(item)
                    continue
            rows.append(row)

        by_track: dict[str, int] = {}
        for r in rows:
            by_track[r.track] = by_track.get(r.track, 0) + 1

        status = CAPABILITY_AVAILABLE if rows else CAPABILITY_UNAVAILABLE
        if not rows and not notes:
            notes.append("No readable historical challenge packs found")
        return ControlTowerSnapshot(
            status=status,
            rows=tuple(rows),
            by_track=dict(by_track),
            notes=tuple(notes),
        )

    # --- Phase 2: explicit policy run + result projection -----------------

    def describe_protocol(self, protocol_id: str) -> ProtocolSummary | None:
        """Return a read-only Protocol summary, or None if unknown."""
        try:
            p = get_protocol(protocol_id)
        except KeyError:
            return None
        return ProtocolSummary(
            protocol_id=p.protocol_id,
            primary_horizon=p.primary_horizon,
            horizons_report=tuple(p.horizons_report),
            min_n_total=p.min_n_total,
            min_n_test=p.min_n_test,
            n_folds=p.n_folds,
            embargo_sessions=p.embargo_sessions,
            min_folds_for_win=p.min_folds_for_win,
            win_margin=p.win_margin,
            min_fold_agree=p.min_fold_agree,
            label=p.label,
            costs=p.costs,
        )

    def build_policy_run_request(
        self,
        *,
        policy_id: str,
        baseline_id: str,
        against_id: str,
        compatibility_id: str,
        purpose_family: str = "",
        write_artifact: bool = True,
    ) -> ChallengeRunRequest:
        """Build an immutable request; stamps request_id over material fields.

        Does not execute. Callers must not treat this as an eligibility grant.
        """
        pid = str(policy_id).strip()
        baseline = str(baseline_id).strip()
        against = str(against_id).strip()
        cid = str(compatibility_id).strip()
        family = str(purpose_family).strip()
        if not pid:
            raise ValueError("policy_id is required")
        if baseline not in {"production", "static_reference"}:
            raise ValueError(
                "baseline_id must be explicit 'production' or 'static_reference'"
            )
        if not against:
            raise ValueError("against_id is required")
        if not cid or cid.startswith("—"):
            raise ValueError(
                "compatibility_id must be an exact explicit selection "
                "(no largest/latest/only default)"
            )
        # Display label for null/blank cohort ids from inventory.
        if cid == "(untagged)":
            cid = ""

        catalog = {r.policy_id: r for r in self.list_policy_catalog()}
        row = catalog.get(pid)
        if row is None:
            raise ValueError(f"policy_id {pid!r} is not in the registry catalog")
        protocol_id = row.protocol_id
        if row.supported_challengers and against not in row.supported_challengers:
            raise ValueError(
                f"against_id {against!r} is not in supported_challengers "
                f"for {pid}: {list(row.supported_challengers)}"
            )

        material = {
            "verb": "policy_run",
            "policy_id": pid,
            "baseline_id": baseline,
            "against_id": against,
            "compatibility_id": cid,
            "purpose_family": family,
            "protocol_id": protocol_id,
            "write_artifact": bool(write_artifact),
            "db_path": str(self._config.upstream_db_path),
            "artifacts_root": str(self._config.artifacts_root),
        }
        request_id = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        return ChallengeRunRequest(
            request_id=request_id,
            verb="policy_run",
            policy_id=pid,
            baseline_id=baseline,
            against_id=against,
            compatibility_id=cid,
            purpose_family=family,
            protocol_id=protocol_id,
            write_artifact=bool(write_artifact),
            db_path=str(self._config.upstream_db_path),
            artifacts_root=str(self._config.artifacts_root),
        )

    @staticmethod
    def new_attempt_id() -> str:
        """Opaque attempt id for one deliberate execution (Run / Run again)."""
        return uuid.uuid4().hex[:16]

    def execute_policy_run(
        self,
        request: ChallengeRunRequest,
        *,
        attempt_id: str,
        executed_keys: set[str] | None = None,
    ) -> ChallengeRunView:
        """Run one policy tournament synchronously via existing orchestration.

        Idempotency: if ``executed_keys`` contains ``request_id:attempt_id``,
        returns a non-executing application_error view without calling the
        runner again. Session-scoped only until Phase 4 durable jobs.
        """
        if not attempt_id or not str(attempt_id).strip():
            raise ValueError("attempt_id is required")
        key = f"{request.request_id}:{attempt_id}"
        if executed_keys is not None and key in executed_keys:
            return ChallengeRunView(
                request_id=request.request_id,
                attempt_id=attempt_id,
                kind="application_error",
                status="DUPLICATE_ATTEMPT",
                policy_id=request.policy_id,
                protocol_id=request.protocol_id,
                baseline_id=request.baseline_id,
                against_id=request.against_id,
                policy_hash="",
                n_rows=0,
                primary_horizon=0,
                primary_ic_baseline=None,
                primary_ic_against=None,
                horizon_metrics={},
                fold_metrics=(),
                min_folds_for_win=None,
                n_folds_reported=0,
                weights={},
                lines=(
                    "DUPLICATE_ATTEMPT:",
                    "  - This request_id+attempt_id was already executed; "
                    "use Run again for a new attempt_id.",
                ),
                notes=("duplicate Streamlit/session attempt suppressed",),
                summary_md="# DUPLICATE_ATTEMPT\n\nNo re-execution.\n",
                observation_compatibility_id=request.compatibility_id,
                production_snapshot_id="",
                production_snapshot_digest="",
                production_policy_id="",
                production_policy_version="",
                production_semantic_engine_contract_id="",
                challenge_adapter_id="",
                challenge_adapter_version="",
                population_identity_kind="",
                population_identity_id="",
                population_identity_detail={},
                artifact_dir=None,
                elapsed_seconds=0.0,
                human_next_step="Click Run again to mint a new attempt_id.",
                error_reference=f"dup:{key}",
            )

        t0 = time.perf_counter()
        try:
            result = run_policy_challenge(
                Path(request.db_path),
                request.policy_id,
                against=request.against_id,
                baseline=request.baseline_id,
                protocol_id=request.protocol_id or None,
                write_artifact=request.write_artifact,
                artifacts_dir=Path(request.artifacts_root),
                compatibility_id=request.compatibility_id,
            )
            view = _view_from_challenge_result(
                result,
                request_id=request.request_id,
                attempt_id=attempt_id,
                elapsed_seconds=time.perf_counter() - t0,
            )
        except Exception as exc:  # noqa: BLE001 — preserve category; not a verdict
            elapsed = time.perf_counter() - t0
            ref = f"err:{uuid.uuid4().hex[:12]}"
            view = ChallengeRunView(
                request_id=request.request_id,
                attempt_id=attempt_id,
                kind="application_error",
                status="APPLICATION_ERROR",
                policy_id=request.policy_id,
                protocol_id=request.protocol_id,
                baseline_id=request.baseline_id,
                against_id=request.against_id,
                policy_hash="",
                n_rows=0,
                primary_horizon=0,
                primary_ic_baseline=None,
                primary_ic_against=None,
                horizon_metrics={},
                fold_metrics=(),
                min_folds_for_win=None,
                n_folds_reported=0,
                weights={},
                lines=(
                    "APPLICATION_ERROR:",
                    f"  - {type(exc).__name__}: {exc}",
                    f"  - reference={ref}",
                ),
                notes=(f"{type(exc).__name__}: {exc}",),
                summary_md=(
                    f"# APPLICATION_ERROR\n\nReference `{ref}`\n\n"
                    f"{type(exc).__name__}: {exc}\n"
                ),
                observation_compatibility_id=request.compatibility_id,
                production_snapshot_id="",
                production_snapshot_digest="",
                production_policy_id="",
                production_policy_version="",
                production_semantic_engine_contract_id="",
                challenge_adapter_id="",
                challenge_adapter_version="",
                population_identity_kind="",
                population_identity_id="",
                population_identity_detail={},
                artifact_dir=None,
                elapsed_seconds=elapsed,
                human_next_step=(
                    "Inspect server logs with the error reference; fix the "
                    "contract/environment; do not treat this as BLOCKED_DATA."
                ),
                error_reference=ref,
            )
        if executed_keys is not None:
            executed_keys.add(key)
        return view

    # --- Phase 3: artifact history, compare, promote handoff -------------

    def list_challenge_artifacts(
        self,
        *,
        limit: int = 100,
    ) -> tuple[ArtifactListItem, ...]:
        """Service-owned inventory of challenge packs (not UI glob authority)."""
        root = self._config.artifacts_root / "challenge"
        if not root.is_dir():
            return ()
        items: list[ArtifactListItem] = []
        for manifest_path in sorted(
            root.rglob("manifest.json"),
            key=lambda p: p.stat().st_mtime if p.is_file() else 0.0,
            reverse=True,
        ):
            if len(items) >= limit:
                break
            pack = manifest_path.parent
            # Skip nested non-pack noise under health expansions if needed
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                items.append(
                    ArtifactListItem(
                        artifact_path=str(pack),
                        mode="unknown",
                        track="other",
                        status="UNREADABLE",
                        policy_id=None,
                        protocol_id=None,
                        baseline_id=None,
                        against_id=None,
                        schema_version=None,
                        created_at=None,
                        openable=False,
                        open_block_reason="manifest unreadable",
                        promotion_eligible_hint=False,
                        promotion_block_reason="manifest unreadable",
                    )
                )
                continue
            if not isinstance(manifest, dict):
                continue
            item = _list_item_from_manifest(pack, manifest)
            items.append(item)
        return tuple(items)

    def open_challenge_artifact(self, artifact_path: str | Path) -> ArtifactOpenView:
        """Validate and open a pack for display; never upgrades historical schemas."""
        pack = Path(artifact_path)
        if not pack.is_dir():
            return _open_error(str(pack), f"not a directory: {pack}")
        manifest_p = pack / "manifest.json"
        if not manifest_p.is_file():
            return _open_error(str(pack), "manifest.json missing")
        try:
            manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return _open_error(str(pack), f"cannot read manifest: {exc}")
        if not isinstance(manifest, dict):
            return _open_error(str(pack), "manifest root must be object")

        metrics: dict[str, Any] = {}
        metrics_p = pack / "metrics.json"
        if metrics_p.is_file():
            try:
                raw_m = json.loads(metrics_p.read_text(encoding="utf-8"))
                if isinstance(raw_m, dict):
                    metrics = raw_m
            except (OSError, json.JSONDecodeError):
                metrics = {}

        summary_md = ""
        summary_p = pack / "summary.md"
        if summary_p.is_file():
            try:
                summary_md = summary_p.read_text(encoding="utf-8")
            except OSError:
                summary_md = ""

        schema_raw = manifest.get("schema_version")
        schema_version: int | None
        try:
            schema_version = int(schema_raw) if schema_raw is not None else None
        except (TypeError, ValueError):
            schema_version = None

        notes: list[str] = []
        historical = (
            schema_version in HISTORICAL_CHALLENGE_ARTIFACT_SCHEMA_VERSIONS
            if schema_version is not None
            else True
        )
        if historical:
            notes.append(
                f"schema_version={schema_version} is historical/display-only "
                f"(promote requires {CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION})"
            )

        promotion_eligible = False
        promotion_block: str | None = None
        if historical:
            promotion_block = "historical schema — not promote-reopen eligible"
        elif schema_version != CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION:
            promotion_block = (
                f"schema_version={schema_version} not promote-eligible "
                f"(need {CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION})"
            )
        elif not manifest.get("baseline_id"):
            promotion_block = "missing baseline_id"
        elif str(manifest.get("baseline_id")) != "production":
            promotion_block = (
                f"baseline_id={manifest.get('baseline_id')!r} is not production"
            )
        else:
            # Live verify via promote loader (read-only DB).
            try:
                with connect(self._config.upstream_db_path) as conn:
                    from ml_saham.challenge.promote import load_evidence_artifact

                    _ev, err = load_evidence_artifact(pack, conn=conn)
                    if err is not None:
                        promotion_block = err
                    else:
                        promotion_eligible = True
                        notes.append("promote-reopen gate passed (read-only verify)")
            except FileNotFoundError as exc:
                promotion_block = f"cannot verify against upstream DB: {exc}"
            except Exception as exc:  # noqa: BLE001
                promotion_block = f"promote verify error: {type(exc).__name__}: {exc}"

        mode = str(manifest.get("mode") or "")
        track_hint = str(manifest.get("track") or "")
        track = (
            _TRACK_BY_MANIFEST_TRACK.get(track_hint)
            or _TRACK_BY_MODE.get(mode)
            or "other"
        )
        status = str(
            manifest.get("status")
            or metrics.get("status")
            or manifest.get("verdict")
            or "UNKNOWN"
        )
        files = _pack_files(pack)
        folds = metrics.get("fold_metrics") or []
        if not isinstance(folds, list):
            folds = []

        return ArtifactOpenView(
            ok=True,
            artifact_path=str(pack),
            mode=mode or track_hint or "unknown",
            track=track,
            status=status,
            schema_version=schema_version,
            policy_id=_opt_str(manifest.get("policy_id")),
            protocol_id=_opt_str(manifest.get("protocol_id")),
            baseline_id=_opt_str(manifest.get("baseline_id")),
            against_id=_opt_str(manifest.get("against_id")),
            primary_horizon=_opt_int(manifest.get("primary_horizon")),
            n_rows=_opt_int(manifest.get("n_rows")),
            primary_ic_baseline=_opt_float(metrics.get("primary_ic_baseline")),
            primary_ic_against=_opt_float(metrics.get("primary_ic_against")),
            horizon_metrics=dict(metrics.get("horizon_metrics") or {})
            if isinstance(metrics.get("horizon_metrics"), dict)
            else {},
            fold_metrics=tuple(dict(f) for f in folds if isinstance(f, dict)),
            observation_compatibility_id=_opt_str(
                manifest.get("observation_compatibility_id")
            ),
            population_identity_kind=_opt_str(manifest.get("population_identity_kind")),
            population_identity_id=_opt_str(manifest.get("population_identity_id")),
            production_snapshot_id=_opt_str(manifest.get("production_snapshot_id")),
            challenge_adapter_id=_opt_str(manifest.get("challenge_adapter_id")),
            files=files,
            summary_md=summary_md,
            manifest=dict(manifest),
            metrics=dict(metrics),
            historical_display_only=historical,
            promotion_eligible=promotion_eligible,
            promotion_block_reason=promotion_block,
            notes=tuple(notes),
            error=None,
        )

    def read_artifact_file_bytes(
        self,
        artifact_path: str | Path,
        filename: str,
    ) -> tuple[bytes | None, str | None]:
        """Return exact bytes of an existing pack file after open validation."""
        opened = self.open_challenge_artifact(artifact_path)
        if not opened.ok:
            return None, opened.error or "open failed"
        allowed = {f.name for f in opened.files}
        name = Path(filename).name  # no path traversal
        if name not in allowed:
            return None, f"file not in validated pack members: {name}"
        path = Path(opened.artifact_path) / name
        try:
            return path.read_bytes(), None
        except OSError as exc:
            return None, f"cannot read {name}: {exc}"

    def compare_challenge_artifacts(
        self,
        left_path: str | Path,
        right_path: str | Path,
    ) -> ArtifactCompareView:
        """Compare two packs; computed deltas only when compatibility axes match."""
        left = self.open_challenge_artifact(left_path)
        right = self.open_challenge_artifact(right_path)
        notes: list[str] = []
        if not left.ok or not right.ok:
            return ArtifactCompareView(
                left_path=str(left_path),
                right_path=str(right_path),
                compatible=False,
                axes=(),
                left_status=left.status if left.ok else "OPEN_FAILED",
                right_status=right.status if right.ok else "OPEN_FAILED",
                left_ic_baseline=None,
                right_ic_baseline=None,
                left_ic_against=None,
                right_ic_against=None,
                delta_ic_against=None,
                winner_banner=None,
                notes=(
                    left.error or "",
                    right.error or "",
                    "Both packs must open successfully before compare.",
                ),
            )

        axes = (
            _axis("policy_id", left.policy_id, right.policy_id),
            _axis("protocol_id", left.protocol_id, right.protocol_id),
            _axis(
                "primary_horizon",
                str(left.primary_horizon),
                str(right.primary_horizon),
            ),
            _axis(
                "population_identity_kind",
                left.population_identity_kind,
                right.population_identity_kind,
            ),
            _axis(
                "population_or_compat_id",
                left.population_identity_id or left.observation_compatibility_id,
                right.population_identity_id or right.observation_compatibility_id,
            ),
            _axis("mode", left.mode, right.mode),
            _axis("track", left.track, right.track),
        )
        compatible = all(a.compatible for a in axes)
        if not compatible:
            notes.append(
                "Incompatible axes — inspect separately; no delta or winner banner."
            )
            return ArtifactCompareView(
                left_path=left.artifact_path,
                right_path=right.artifact_path,
                compatible=False,
                axes=axes,
                left_status=left.status,
                right_status=right.status,
                left_ic_baseline=left.primary_ic_baseline,
                right_ic_baseline=right.primary_ic_baseline,
                left_ic_against=left.primary_ic_against,
                right_ic_against=right.primary_ic_against,
                delta_ic_against=None,
                winner_banner=None,
                notes=tuple(notes),
            )

        delta: float | None = None
        if (
            left.primary_ic_against is not None
            and right.primary_ic_against is not None
        ):
            delta = right.primary_ic_against - left.primary_ic_against

        winner: str | None = None
        # Status ranking only when both are win/lose/inconclusive product states.
        rank = {"WIN": 3, "LOSE": 1, "INCONCLUSIVE": 2}
        if left.status in rank and right.status in rank:
            if rank[right.status] > rank[left.status]:
                winner = f"Right status rank higher: {right.status} vs {left.status}"
            elif rank[left.status] > rank[right.status]:
                winner = f"Left status rank higher: {left.status} vs {right.status}"
            elif (
                left.primary_ic_against is not None
                and right.primary_ic_against is not None
            ):
                if right.primary_ic_against > left.primary_ic_against:
                    winner = "Right higher primary IC(against) under compatible axes"
                elif left.primary_ic_against > right.primary_ic_against:
                    winner = "Left higher primary IC(against) under compatible axes"
                else:
                    winner = "Tied primary IC(against)"
            notes.append(
                "Winner banner is descriptive only — not promotion authority."
            )
        else:
            notes.append(
                "Statuses not in WIN/LOSE/INCONCLUSIVE set — no winner banner."
            )

        return ArtifactCompareView(
            left_path=left.artifact_path,
            right_path=right.artifact_path,
            compatible=True,
            axes=axes,
            left_status=left.status,
            right_status=right.status,
            left_ic_baseline=left.primary_ic_baseline,
            right_ic_baseline=right.primary_ic_baseline,
            left_ic_against=left.primary_ic_against,
            right_ic_against=right.primary_ic_against,
            delta_ic_against=delta,
            winner_banner=winner,
            notes=tuple(notes),
        )

    def create_promote_packet(
        self,
        artifact_path: str | Path,
        *,
        write_artifact: bool = True,
    ) -> PromotePacketView:
        """Invoke existing promote-packet path; never edits ai-saham."""
        result = build_promote_packet(
            from_artifact=Path(artifact_path),
            write_artifact=write_artifact,
            artifacts_dir=self._config.artifacts_root,
            db_path=self._config.upstream_db_path,
        )
        return PromotePacketView(
            ok=result.error is None,
            policy_id=result.policy_id or "",
            mode=result.mode or "",
            lines=tuple(result.lines or []),
            summary_md=result.summary_md or "",
            evidence=dict(result.evidence or {}),
            artifact_dir=str(result.artifact_dir) if result.artifact_dir else None,
            error=result.error,
            auto_applied=False,
        )

    # --- Weekly ritual: last health pack + optional health run ------------

    def latest_health_pack(self) -> LatestHealthPack:
        """Return the newest ``challenge/health/<ts>`` pack, if any."""
        root = self._config.artifacts_root / "challenge" / "health"
        if not root.is_dir():
            return LatestHealthPack(
                found=False,
                artifact_path=None,
                created_at=None,
                engine_id=None,
                with_diagnostics=None,
                with_factors=None,
                with_champion=None,
                n_index=None,
                notes=(f"No health tree at {root}",),
            )
        candidates = [
            p
            for p in root.iterdir()
            if p.is_dir() and (p / "manifest.json").is_file()
        ]
        if not candidates:
            return LatestHealthPack(
                found=False,
                artifact_path=None,
                created_at=None,
                engine_id=None,
                with_diagnostics=None,
                with_factors=None,
                with_champion=None,
                n_index=None,
                notes=("Health directory exists but no packs with manifest.json",),
            )
        latest = max(
            candidates,
            key=lambda p: p.stat().st_mtime if p.is_dir() else 0.0,
        )
        try:
            manifest = json.loads((latest / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return LatestHealthPack(
                found=True,
                artifact_path=str(latest),
                created_at=None,
                engine_id=None,
                with_diagnostics=None,
                with_factors=None,
                with_champion=None,
                n_index=None,
                notes=(f"latest pack unreadable: {exc}",),
            )
        if not isinstance(manifest, dict):
            return LatestHealthPack(
                found=True,
                artifact_path=str(latest),
                created_at=None,
                engine_id=None,
                with_diagnostics=None,
                with_factors=None,
                with_champion=None,
                n_index=None,
                notes=("manifest root is not an object",),
            )
        return LatestHealthPack(
            found=True,
            artifact_path=str(latest),
            created_at=_opt_str(manifest.get("created_at")),
            engine_id=_opt_str(manifest.get("engine_id")),
            with_diagnostics=bool(manifest.get("with_diagnostics"))
            if "with_diagnostics" in manifest
            else None,
            with_factors=bool(manifest.get("with_factors"))
            if "with_factors" in manifest
            else None,
            with_champion=bool(manifest.get("with_champion"))
            if "with_champion" in manifest
            else None,
            n_index=_opt_int(manifest.get("n_index")),
            notes=(),
        )

    def build_health_run_request(
        self,
        *,
        compatibility_id: str,
        scenario: str = "",
        with_diagnostics: bool = True,
        with_factors: bool = False,
        with_champion: bool = False,
        champion_model: str = "lgbm_reweight",
        engine_id: str = "screener",
        write_artifact: bool = True,
    ) -> HealthRunRequest:
        """Immutable health request. Does not execute."""
        cid = str(compatibility_id).strip()
        if not cid or cid.startswith("—"):
            raise ValueError(
                "compatibility_id must be an exact explicit selection "
                "(no largest/latest/only default)"
            )
        if cid == "(untagged)":
            cid = ""
        sc = str(scenario).strip()
        model = str(champion_model).strip() or "lgbm_reweight"
        eng = str(engine_id).strip() or "screener"
        material = {
            "verb": "health_run",
            "engine_id": eng,
            "scenario": sc,
            "with_diagnostics": bool(with_diagnostics),
            "with_factors": bool(with_factors),
            "with_champion": bool(with_champion),
            "champion_model": model,
            "compatibility_id": cid,
            "write_artifact": bool(write_artifact),
            "db_path": str(self._config.upstream_db_path),
            "artifacts_root": str(self._config.artifacts_root),
        }
        request_id = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        return HealthRunRequest(
            request_id=request_id,
            verb="health_run",
            engine_id=eng,
            scenario=sc,
            with_diagnostics=bool(with_diagnostics),
            with_factors=bool(with_factors),
            with_champion=bool(with_champion),
            champion_model=model,
            compatibility_id=cid,
            write_artifact=bool(write_artifact),
            db_path=str(self._config.upstream_db_path),
            artifacts_root=str(self._config.artifacts_root),
        )

    def execute_health_run(
        self,
        request: HealthRunRequest,
        *,
        attempt_id: str,
        executed_keys: set[str] | None = None,
    ) -> HealthRunView:
        """Run weekly health via ``build_health_report`` (synchronous)."""
        if not attempt_id or not str(attempt_id).strip():
            raise ValueError("attempt_id is required")
        key = f"{request.request_id}:{attempt_id}"
        if executed_keys is not None and key in executed_keys:
            return HealthRunView(
                request_id=request.request_id,
                attempt_id=attempt_id,
                kind="application_error",
                status="DUPLICATE_ATTEMPT",
                engine_id=request.engine_id,
                scenario_filter=request.scenario or None,
                with_diagnostics=request.with_diagnostics,
                with_factors=request.with_factors,
                with_champion=request.with_champion,
                lines=(
                    "DUPLICATE_ATTEMPT:",
                    "  - This health request_id+attempt_id was already executed.",
                ),
                notes=("duplicate attempt suppressed",),
                summary_md="# DUPLICATE_ATTEMPT\n",
                index=(),
                artifact_dir=None,
                elapsed_seconds=0.0,
                human_next_step="Use Run health again for a new attempt_id.",
                error_reference=f"dup:{key}",
            )

        t0 = time.perf_counter()
        try:
            result = build_health_report(
                Path(request.db_path),
                engine_id=request.engine_id,
                scenario=request.scenario or None,
                with_champion=request.with_champion,
                with_factors=request.with_factors,
                with_diagnostics=request.with_diagnostics,
                champion_model=request.champion_model,
                write_artifact=request.write_artifact,
                artifacts_dir=Path(request.artifacts_root),
                compatibility_id=request.compatibility_id or None,
            )
            view = _view_from_health_result(
                result,
                request_id=request.request_id,
                attempt_id=attempt_id,
                elapsed_seconds=time.perf_counter() - t0,
            )
        except Exception as exc:  # noqa: BLE001
            ref = f"err:{uuid.uuid4().hex[:12]}"
            view = HealthRunView(
                request_id=request.request_id,
                attempt_id=attempt_id,
                kind="application_error",
                status="APPLICATION_ERROR",
                engine_id=request.engine_id,
                scenario_filter=request.scenario or None,
                with_diagnostics=request.with_diagnostics,
                with_factors=request.with_factors,
                with_champion=request.with_champion,
                lines=(
                    "APPLICATION_ERROR:",
                    f"  - {type(exc).__name__}: {exc}",
                    f"  - reference={ref}",
                ),
                notes=(f"{type(exc).__name__}: {exc}",),
                summary_md=f"# APPLICATION_ERROR\n\n`{ref}`\n",
                index=(),
                artifact_dir=None,
                elapsed_seconds=time.perf_counter() - t0,
                human_next_step="Inspect logs with the error reference.",
                error_reference=ref,
            )
        if executed_keys is not None:
            executed_keys.add(key)
        return view


def build_challenge_workbench(
    *,
    db_path: Path | str | None = None,
    artifacts_root: Path | None = None,
) -> ChallengeWorkbenchService:
    """Build the presentation facade without requiring paths to exist."""
    config = ChallengeWorkbenchConfig(
        upstream_db_path=resolve_db_path(db_path),
        artifacts_root=resolve_artifacts_root(artifacts_root),
    )
    return ChallengeWorkbenchService(config)


def _decision_type(*, panel_kind: str, score_kind: str, policy_id: str) -> str:
    if policy_id.startswith("risk."):
        return "gate"
    if policy_id.startswith("signal."):
        return "score"
    if "factor" in score_kind or panel_kind == "accum_components":
        return "rank"
    if "hard_filter" in policy_id or "filter" in score_kind:
        return "filter"
    return score_kind or panel_kind or "policy"


def _historical_row_from_manifest(
    payload: Mapping[str, Any],
    manifest_path: Path,
) -> HistoricalResultRow | None:
    mode = str(payload.get("mode") or "")
    track_hint = str(payload.get("track") or "")
    track = (
        _TRACK_BY_MANIFEST_TRACK.get(track_hint)
        or _TRACK_BY_MODE.get(mode)
        or "other"
    )
    status = payload.get("status")
    if status is None:
        status = payload.get("verdict")
    status_s = str(status or "UNKNOWN")
    is_diag = track == "diagnostic" or "diagnostic" in mode
    schema_raw = payload.get("schema_version")
    schema_version: int | None
    try:
        schema_version = int(schema_raw) if schema_raw is not None else None
    except (TypeError, ValueError):
        schema_version = None

    return HistoricalResultRow(
        track=track,
        status=status_s,
        mode=mode or track_hint or "unknown",
        policy_id=_opt_str(payload.get("policy_id")),
        protocol_id=_opt_str(payload.get("protocol_id")),
        baseline_id=_opt_str(payload.get("baseline_id")),
        against_id=_opt_str(payload.get("against_id")),
        factor=_opt_str(payload.get("factor")),
        diagnostic_id=_opt_str(payload.get("diagnostic_id")),
        created_at=_opt_str(payload.get("created_at")),
        artifact_path=str(manifest_path.parent),
        schema_version=schema_version,
        is_diagnostic_display=is_diag,
        notes=(),
    )


def _expand_health_index(
    pack_dir: Path,
    health_row: HistoricalResultRow,
) -> list[HistoricalResultRow]:
    index_path = pack_dir / "index.json"
    if not index_path.is_file():
        return []
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(index, list):
        return []
    out: list[HistoricalResultRow] = []
    for item in index:
        if not isinstance(item, dict):
            continue
        section = str(item.get("section") or "engine")
        if section.startswith("diagnostic"):
            track = "diagnostic"
            is_diag = True
        elif section == "champion":
            track = "champion"
            is_diag = False
        elif section == "factor" or section == "factors":
            track = "factor"
            is_diag = False
        else:
            track = "tune"
            is_diag = False
        status = str(item.get("status") or item.get("verdict") or "UNKNOWN")
        out.append(
            HistoricalResultRow(
                track=track,
                status=status,
                mode="challenge_health_index",
                policy_id=_opt_str(item.get("policy_id")),
                protocol_id=health_row.protocol_id,
                baseline_id=_opt_str(item.get("baseline_id")),
                against_id=_opt_str(item.get("against_id")),
                factor=_opt_str(item.get("factor")),
                diagnostic_id=_opt_str(item.get("diagnostic_id")),
                created_at=health_row.created_at,
                artifact_path=str(pack_dir),
                schema_version=health_row.schema_version,
                is_diagnostic_display=is_diag,
                notes=(f"health_section={section}",),
            )
        )
    return out


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _list_item_from_manifest(pack: Path, manifest: dict[str, Any]) -> ArtifactListItem:
    mode = str(manifest.get("mode") or "")
    track_hint = str(manifest.get("track") or "")
    track = (
        _TRACK_BY_MANIFEST_TRACK.get(track_hint)
        or _TRACK_BY_MODE.get(mode)
        or "other"
    )
    schema_raw = manifest.get("schema_version")
    try:
        schema_version = int(schema_raw) if schema_raw is not None else None
    except (TypeError, ValueError):
        schema_version = None
    status = str(manifest.get("status") or manifest.get("verdict") or "UNKNOWN")
    historical = (
        schema_version in HISTORICAL_CHALLENGE_ARTIFACT_SCHEMA_VERSIONS
        if schema_version is not None
        else True
    )
    promo_ok = False
    promo_block: str | None
    if historical:
        promo_block = "historical/display-only schema"
    elif schema_version != CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION:
        promo_block = "schema not promote-evidence v4"
    elif not manifest.get("baseline_id"):
        promo_block = "missing baseline_id"
    elif str(manifest.get("baseline_id")) != "production":
        promo_block = "baseline is not production"
    elif not (pack / "pack_binding.json").is_file():
        promo_block = "missing pack_binding.json (not sealed v4 pack)"
    elif not manifest.get("production_snapshot_id"):
        promo_block = "missing production snapshot identity fields"
    else:
        # Hint only — full promote-reopen verify still runs on open/promote.
        promo_ok = True
        promo_block = "hint: sealed shape present; re-verify on promote"

    return ArtifactListItem(
        artifact_path=str(pack),
        mode=mode or track_hint or "unknown",
        track=track,
        status=status,
        policy_id=_opt_str(manifest.get("policy_id")),
        protocol_id=_opt_str(manifest.get("protocol_id")),
        baseline_id=_opt_str(manifest.get("baseline_id")),
        against_id=_opt_str(manifest.get("against_id")),
        schema_version=schema_version,
        created_at=_opt_str(manifest.get("created_at")),
        openable=True,
        open_block_reason=None,
        promotion_eligible_hint=bool(promo_ok),
        promotion_block_reason=promo_block,
    )


def _pack_files(pack: Path) -> tuple[ArtifactFileEntry, ...]:
    names = (
        "manifest.json",
        "metrics.json",
        "weights.json",
        "summary.md",
        "pack_binding.json",
        "PROMOTE.md",
        "evidence.json",
        "index.json",
        "engine.json",
        "champion.json",
        "factors.json",
        "diagnostics.json",
    )
    out: list[ArtifactFileEntry] = []
    for name in names:
        path = pack / name
        if not path.is_file():
            continue
        if name.endswith(".md"):
            hint = "markdown"
        elif name.endswith(".json"):
            hint = "json"
        else:
            hint = "other"
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        out.append(ArtifactFileEntry(name=name, size_bytes=size, media_hint=hint))
    return tuple(out)


def _open_error(path: str, error: str) -> ArtifactOpenView:
    return ArtifactOpenView(
        ok=False,
        artifact_path=path,
        mode="",
        track="other",
        status="OPEN_FAILED",
        schema_version=None,
        policy_id=None,
        protocol_id=None,
        baseline_id=None,
        against_id=None,
        primary_horizon=None,
        n_rows=None,
        primary_ic_baseline=None,
        primary_ic_against=None,
        horizon_metrics={},
        fold_metrics=(),
        observation_compatibility_id=None,
        population_identity_kind=None,
        population_identity_id=None,
        production_snapshot_id=None,
        challenge_adapter_id=None,
        files=(),
        summary_md="",
        manifest={},
        metrics={},
        historical_display_only=True,
        promotion_eligible=False,
        promotion_block_reason=error,
        notes=(error,),
        error=error,
    )


def _axis(name: str, left: Any, right: Any) -> ArtifactCompareAxis:
    ls = "" if left is None else str(left)
    rs = "" if right is None else str(right)
    # Empty vs empty is compatible (both missing).
    return ArtifactCompareAxis(
        name=name,
        left=ls,
        right=rs,
        compatible=ls == rs,
    )


def _view_from_health_result(
    result: HealthReportResult,
    *,
    request_id: str,
    attempt_id: str,
    elapsed_seconds: float,
) -> HealthRunView:
    if result.resolve_error:
        status = "BLOCKED_POLICY"
        if "not found" in (result.resolve_error or "").lower():
            status = "BLOCKED_DATA"
    else:
        # Roll up index statuses: any BLOCKED_* dominates; else mixed/ok.
        statuses = {
            str(row.get("status") or "")
            for row in (result.index or [])
            if isinstance(row, dict)
        }
        if any(s.startswith("BLOCKED") for s in statuses):
            status = "BLOCKED_MIXED" if len(statuses) > 1 else next(
                (s for s in statuses if s.startswith("BLOCKED")), "BLOCKED_POLICY"
            )
        elif not statuses:
            status = "EMPTY_INDEX"
        else:
            status = "HEALTH_COMPLETE"

    next_step = (
        "Open the health pack in Artifact History / Control Tower. "
        "Diagnostics never set Action. Dig signal/risk only when retuning. "
        "Never auto-promote."
    )
    return HealthRunView(
        request_id=request_id,
        attempt_id=attempt_id,
        kind="product_result",
        status=status,
        engine_id=result.engine_id,
        scenario_filter=result.scenario_filter,
        with_diagnostics=result.with_diagnostics,
        with_factors=result.with_factors,
        with_champion=result.with_champion,
        lines=tuple(result.lines or []),
        notes=tuple(result.notes or []),
        summary_md=result.summary_md or "",
        index=tuple(dict(r) for r in (result.index or []) if isinstance(r, dict)),
        artifact_dir=str(result.artifact_dir) if result.artifact_dir else None,
        elapsed_seconds=elapsed_seconds,
        human_next_step=next_step,
        resolve_error=result.resolve_error,
        error_reference=None,
    )


def _view_from_challenge_result(
    result: ChallengeResult,
    *,
    request_id: str,
    attempt_id: str,
    elapsed_seconds: float,
) -> ChallengeRunView:
    status = (
        result.status.value
        if isinstance(result.status, ChallengeStatus)
        else str(result.status)
    )
    folds = tuple(dict(f) for f in (result.fold_metrics or []))
    protocol_summary_min_folds: int | None = None
    try:
        protocol_summary_min_folds = get_protocol(result.protocol_id).min_folds_for_win
    except KeyError:
        protocol_summary_min_folds = None

    if status in {ChallengeStatus.WIN.value, ChallengeStatus.LOSE.value}:
        next_step = (
            "Human review only. A WIN does not auto-promote ai-saham; "
            "use promote-packet / memo workflows outside auto-apply."
        )
    elif status in {
        ChallengeStatus.BLOCKED_DATA.value,
        ChallengeStatus.BLOCKED_POLICY.value,
    }:
        next_step = (
            "Product completed in a blocked state. Fix the stated identity/data "
            "block; do not soft-succeed or auto-select a replacement cohort."
        )
    elif status == ChallengeStatus.INCONCLUSIVE.value:
        next_step = (
            "Inconclusive under protocol (e.g. fold depth / margin). Not a WIN; "
            "not promotion-eligible as confirmatory."
        )
    else:
        next_step = "Review notes and identities; no automatic production change."

    return ChallengeRunView(
        request_id=request_id,
        attempt_id=attempt_id,
        kind="product_result",
        status=status,
        policy_id=result.policy_id,
        protocol_id=result.protocol_id,
        baseline_id=result.baseline_id,
        against_id=result.against_id,
        policy_hash=result.policy_hash,
        n_rows=result.n_rows,
        primary_horizon=result.primary_horizon,
        primary_ic_baseline=result.primary_ic_baseline,
        primary_ic_against=result.primary_ic_against,
        horizon_metrics=dict(result.horizon_metrics or {}),
        fold_metrics=folds,
        min_folds_for_win=protocol_summary_min_folds,
        n_folds_reported=len(folds),
        weights=dict(result.weights or {}),
        lines=tuple(result.lines or []),
        notes=tuple(result.notes or []),
        summary_md=result.summary_md or "",
        observation_compatibility_id=result.observation_compatibility_id or "",
        production_snapshot_id=result.production_snapshot_id or "",
        production_snapshot_digest=result.production_snapshot_digest or "",
        production_policy_id=result.production_policy_id or "",
        production_policy_version=result.production_policy_version or "",
        production_semantic_engine_contract_id=(
            result.production_semantic_engine_contract_id or ""
        ),
        challenge_adapter_id=result.challenge_adapter_id or "",
        challenge_adapter_version=result.challenge_adapter_version or "",
        population_identity_kind=result.population_identity_kind or "",
        population_identity_id=result.population_identity_id or "",
        population_identity_detail=dict(result.population_identity_detail or {}),
        artifact_dir=str(result.artifact_dir) if result.artifact_dir else None,
        elapsed_seconds=elapsed_seconds,
        human_next_step=next_step,
        error_reference=None,
    )
