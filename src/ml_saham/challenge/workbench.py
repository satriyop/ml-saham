"""Typed application boundary shared by challenge presentation adapters.

Phase 0: configuration and product-boundary context only.
Phase 1A: read-only Control Tower (historical packs), factual cohort inventory,
and canonical Policy Catalog. No live challenge execution, no C0 readiness
inference, and no Run surface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ml_saham.artifacts import resolve_artifacts_root
from ml_saham.challenge.diagnostics.registry import list_diagnostics
from ml_saham.challenge.policies.registry import load_policy, load_policy_adapter
from ml_saham.challenge.production_policy_snapshots import REQUIRED_POLICIES
from ml_saham.challenge.runner import list_policies
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
