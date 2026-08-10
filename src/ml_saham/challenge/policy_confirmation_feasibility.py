"""Read-only cohort feasibility audit for ML-OOS-02.

This module measures whether an explicit ACCUM compatibility cohort can form
the current Protocol's post-embargo folds.  It deliberately does not inspect
IC, choose statistical thresholds, register a confirmation contract, or grant
promotion eligibility.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from ml_saham.challenge.metrics import time_purged_folds
from ml_saham.challenge.panel import load_observation_rows
from ml_saham.challenge.policy_confirmation_design import (
    HoldoutGeometryCandidate,
    holdout_geometry_candidate,
)
from ml_saham.challenge.runner import prepare_accum_panel
from ml_saham.data.aisaham_read import connect, table_exists
from ml_saham.data.observation_cohort import (
    ACCUM_PURPOSE_LIKE,
    ACCUM_PURPOSES,
    list_compatibility_cohorts,
)

FEASIBILITY_AUDIT_CONTRACT_ID = "policy_confirmation_feasibility.accum.v1"
DEFAULT_POLICY_ID = "screener.accum.score_weights"
DEFAULT_HOLDOUT_CANDIDATES = (5, 10, 20, 40)

_TRIPWIRE_TABLES = (
    "learning_observations",
    "learning_outcome_labels",
    "learning_policy_snapshots",
    "candles",
)


def _require_nonempty_str(name: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be exact str, got {type(value).__name__}")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty without surrounding whitespace")
    return value


def _require_holdout_candidates(values: Sequence[int]) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("holdout_candidates must be a sequence of exact ints")
    out = tuple(values)
    if not out:
        raise ValueError("holdout_candidates must be non-empty")
    for value in out:
        if type(value) is not int or value < 0:
            raise ValueError(
                "holdout_candidates must contain exact non-negative ints, "
                f"got {type(value).__name__}={value!r}"
            )
    if len(set(out)) != len(out):
        raise ValueError("holdout_candidates must be unique")
    return out


@dataclass(frozen=True)
class ReadOnlyDBFingerprint:
    """Relevant upstream state before/after an audit."""

    resolved_path: str
    file_size: int
    file_mtime_ns: int
    file_inode: int
    page_count: int
    freelist_count: int
    schema_version: int
    table_counts: tuple[tuple[str, int | None], ...]
    connection_contract: str = "sqlite_uri_mode_ro"


def capture_read_only_db_fingerprint(db_path: Path | str) -> ReadOnlyDBFingerprint:
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"DB not found: {path}")
    stat = path.stat()
    with connect(path) as conn:
        table_counts = tuple(
            (
                table,
                int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                if table_exists(conn, table)
                else None,
            )
            for table in _TRIPWIRE_TABLES
        )
        return ReadOnlyDBFingerprint(
            resolved_path=str(path),
            file_size=int(stat.st_size),
            file_mtime_ns=int(stat.st_mtime_ns),
            file_inode=int(stat.st_ino),
            page_count=int(conn.execute("PRAGMA page_count").fetchone()[0]),
            freelist_count=int(conn.execute("PRAGMA freelist_count").fetchone()[0]),
            schema_version=int(conn.execute("PRAGMA schema_version").fetchone()[0]),
            table_counts=table_counts,
        )


@dataclass(frozen=True)
class FoldFeasibilityEvidence:
    fold_index: int
    n_train_rows: int
    n_test_rows: int
    n_train_sessions: int
    n_test_sessions: int
    embargo_sessions_actual: int
    train_date_max: str | None
    test_date_min: str | None
    test_date_max: str | None


@dataclass(frozen=True)
class CohortFeasibilityEvidence:
    compatibility_id: str
    cohort_observation_rows: int
    cohort_max_captured_at: str | None
    policy_id: str
    protocol_id: str | None
    challenge_blocked_status: str | None
    status: str
    raw_extractable_rows: int
    raw_unextractable_rows: int
    unique_ticker_sessions: int
    duplicate_ticker_sessions: int
    raw_sessions: int
    raw_date_min: str | None
    raw_date_max: str | None
    raw_tickers: int
    raw_names_per_session_min: int | None
    raw_names_per_session_median: float | None
    raw_names_per_session_max: int | None
    raw_nonfinite_components: int
    primary_eligible_rows: int
    primary_label_excluded_rows: int
    primary_eligible_sessions: int
    primary_date_min: str | None
    primary_date_max: str | None
    horizon_eligible_rows: tuple[tuple[int, int], ...]
    min_folds_for_verdict: int | None
    folds_formed: int
    folds: tuple[FoldFeasibilityEvidence, ...]
    holdout_candidates: tuple[HoldoutGeometryCandidate, ...]
    fixed_challenger_feasibility: str
    learned_challenger_feasibility: str
    outcomes_inspected: bool
    policy_grade_authorized: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CohortFeasibilityAudit:
    contract_id: str
    policy_id: str
    before: ReadOnlyDBFingerprint
    after: ReadOnlyDBFingerprint
    db_unchanged: bool
    discovered_accum_cohorts: int
    untagged_observation_rows: int
    cohorts: tuple[CohortFeasibilityEvidence, ...]
    outcomes_inspected: bool
    policy_grade_authorized: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _range(values: Sequence[str]) -> tuple[str | None, str | None]:
    return (min(values), max(values)) if values else (None, None)


def _audit_one_cohort(
    db_path: Path,
    *,
    cohort: tuple[str, int, str | None],
    policy_id: str,
    holdout_candidates: tuple[int, ...],
) -> CohortFeasibilityEvidence:
    compatibility_id, observation_rows, max_captured_at = cohort
    _require_nonempty_str("compatibility_id", compatibility_id)
    prep = prepare_accum_panel(
        db_path,
        policy_id,
        preferred_compatibility_id=compatibility_id,
    )

    notes = list(prep.notes)
    if prep.selected_compatibility_id != compatibility_id:
        raise RuntimeError(
            "cohort identity mismatch: requested "
            f"{compatibility_id!r}, selected {prep.selected_compatibility_id!r}"
        )

    raw: list[tuple[str, str, dict[str, float], str]] = []
    if prep.policy is not None:
        with connect(db_path) as conn:
            raw, raw_notes = load_observation_rows(
                conn,
                prep.policy,
                compatibility_id=compatibility_id,
            )
        notes.extend(raw_notes)

    by_key: dict[tuple[str, str], tuple[dict[str, float], str]] = {}
    for ticker, session, components, captured_at in raw:
        by_key[(ticker, session)] = (components, captured_at)
    if len(raw) > int(observation_rows):
        raise RuntimeError(
            "canonical observation extraction exceeded cohort row count "
            f"({len(raw)} > {observation_rows})"
        )
    raw_sessions = sorted({session for _ticker, session in by_key})
    raw_date_min, raw_date_max = _range(raw_sessions)
    raw_by_session = Counter(session for _ticker, session in by_key)
    raw_names = sorted(raw_by_session.values())
    raw_nonfinite = sum(
        not math.isfinite(float(value))
        for components, _captured_at in by_key.values()
        for value in components.values()
    )
    raw_unextractable = max(0, int(observation_rows) - len(raw))

    protocol = prep.protocol
    panel_rows = list(prep.rows)
    if len(panel_rows) > len(by_key):
        raise RuntimeError(
            "primary panel exceeded unique ticker-session population "
            f"({len(panel_rows)} > {len(by_key)})"
        )
    primary_sessions = sorted({row.date for row in panel_rows})
    primary_date_min, primary_date_max = _range(primary_sessions)
    folds = time_purged_folds(panel_rows, protocol) if protocol is not None else []
    fold_evidence = tuple(
        FoldFeasibilityEvidence(
            fold_index=index,
            n_train_rows=len(fold.train_idx),
            n_test_rows=len(fold.test_idx),
            n_train_sessions=fold.n_train_sessions,
            n_test_sessions=fold.n_test_sessions,
            embargo_sessions_actual=fold.embargo_sessions_actual,
            train_date_max=fold.train_date_max,
            test_date_min=fold.test_date_min,
            test_date_max=fold.test_date_max,
        )
        for index, fold in enumerate(folds)
    )
    holdouts = (
        tuple(
            holdout_geometry_candidate(
                len(primary_sessions),
                n_folds=protocol.n_folds,
                embargo_sessions=protocol.embargo_sessions,
                min_folds_for_verdict=protocol.min_folds_for_verdict,
                holdout_sessions_candidate=value,
            )
            for value in holdout_candidates
        )
        if protocol is not None
        else ()
    )
    horizon_counts = (
        tuple(
            (horizon, sum(horizon in row.excess for row in panel_rows))
            for horizon in protocol.horizons_report
        )
        if protocol is not None
        else ()
    )

    blocked = prep.blocked.value if prep.blocked is not None else None
    min_folds = protocol.min_folds_for_verdict if protocol is not None else None
    if blocked is not None:
        status = blocked
        fixed = blocked
        learned = blocked
    elif raw_unextractable or raw_nonfinite:
        status = "BLOCKED_CONTRACT"
        fixed = "BLOCKED_CONTRACT"
        learned = "BLOCKED_CONTRACT"
    elif min_folds is None or len(folds) < min_folds:
        status = "NOT_READY_GEOMETRY"
        fixed = "NOT_READY_GEOMETRY"
        learned = "NOT_READY_GEOMETRY"
    else:
        status = "GEOMETRY_READY_METHOD_OPEN"
        fixed = "GEOMETRY_READY_POLICY_METHOD_OPEN"
        learned = "GEOMETRY_READY_LEARNED_FLOORS_OPEN"

    return CohortFeasibilityEvidence(
        compatibility_id=compatibility_id,
        cohort_observation_rows=int(observation_rows),
        cohort_max_captured_at=max_captured_at,
        policy_id=policy_id,
        protocol_id=protocol.protocol_id if protocol is not None else None,
        challenge_blocked_status=blocked,
        status=status,
        raw_extractable_rows=len(raw),
        raw_unextractable_rows=raw_unextractable,
        unique_ticker_sessions=len(by_key),
        duplicate_ticker_sessions=len(raw) - len(by_key),
        raw_sessions=len(raw_sessions),
        raw_date_min=raw_date_min,
        raw_date_max=raw_date_max,
        raw_tickers=len({ticker for ticker, _session in by_key}),
        raw_names_per_session_min=min(raw_names) if raw_names else None,
        raw_names_per_session_median=(
            float(statistics.median(raw_names)) if raw_names else None
        ),
        raw_names_per_session_max=max(raw_names) if raw_names else None,
        raw_nonfinite_components=raw_nonfinite,
        primary_eligible_rows=len(panel_rows),
        primary_label_excluded_rows=len(by_key) - len(panel_rows),
        primary_eligible_sessions=len(primary_sessions),
        primary_date_min=primary_date_min,
        primary_date_max=primary_date_max,
        horizon_eligible_rows=horizon_counts,
        min_folds_for_verdict=min_folds,
        folds_formed=len(folds),
        folds=fold_evidence,
        holdout_candidates=holdouts,
        fixed_challenger_feasibility=fixed,
        learned_challenger_feasibility=learned,
        outcomes_inspected=False,
        policy_grade_authorized=False,
        notes=tuple(notes),
    )


def audit_accum_cohort_feasibility(
    db_path: Path | str,
    *,
    policy_id: str = DEFAULT_POLICY_ID,
    compatibility_ids: Sequence[str] | None = None,
    holdout_candidates: Sequence[int] = DEFAULT_HOLDOUT_CANDIDATES,
) -> CohortFeasibilityAudit:
    """Audit explicit ACCUM cohorts independently under the current Protocol.

    When ``compatibility_ids`` is omitted, every discovered non-empty ACCUM
    cohort is audited separately.  Nothing is auto-selected or pooled.
    """
    policy = _require_nonempty_str("policy_id", policy_id)
    holdouts = _require_holdout_candidates(holdout_candidates)
    path = Path(db_path).expanduser().resolve()
    before = capture_read_only_db_fingerprint(path)

    with connect(path) as conn:
        discovered = list_compatibility_cohorts(
            conn,
            purposes=ACCUM_PURPOSES,
            purpose_like=ACCUM_PURPOSE_LIKE,
        )
    by_id = {cohort[0]: cohort for cohort in discovered}
    untagged_rows = sum(cohort[1] for cohort in discovered if not cohort[0])

    if compatibility_ids is None:
        selected_ids = tuple(cohort[0] for cohort in discovered if cohort[0])
    else:
        if isinstance(compatibility_ids, (str, bytes)):
            raise ValueError("compatibility_ids must be a sequence, not a string")
        selected_ids = tuple(
            _require_nonempty_str("compatibility_id", value)
            for value in compatibility_ids
        )
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError("compatibility_ids must be unique")
    if not selected_ids:
        raise ValueError("no explicit non-empty ACCUM compatibility cohorts available")
    missing = [value for value in selected_ids if value not in by_id]
    if missing:
        raise ValueError(f"ACCUM compatibility cohort(s) not found: {missing!r}")

    evidence = tuple(
        _audit_one_cohort(
            path,
            cohort=by_id[compatibility_id],
            policy_id=policy,
            holdout_candidates=holdouts,
        )
        for compatibility_id in selected_ids
    )
    after = capture_read_only_db_fingerprint(path)
    if before != after:
        raise RuntimeError(
            "upstream DB changed during feasibility audit; refusing mixed-state report"
        )
    return CohortFeasibilityAudit(
        contract_id=FEASIBILITY_AUDIT_CONTRACT_ID,
        policy_id=policy,
        before=before,
        after=after,
        db_unchanged=True,
        discovered_accum_cohorts=len(discovered),
        untagged_observation_rows=untagged_rows,
        cohorts=evidence,
        outcomes_inspected=False,
        policy_grade_authorized=False,
        notes=(
            "Each compatibility cohort is audited independently; no pooling.",
            "Geometry readiness is not a policy-grade train/test session floor.",
            "No IC, uncertainty threshold, holdout length, or multiplicity rule was selected.",
        ),
    )


def format_feasibility_report(audit: CohortFeasibilityAudit) -> str:
    lines = [
        "ML-OOS-02 live cohort feasibility (read-only, non-authoritative)",
        f"contract_id={audit.contract_id}",
        f"policy_id={audit.policy_id}",
        f"db={audit.before.resolved_path}",
        f"db_unchanged={audit.db_unchanged}",
        "outcomes_inspected=False policy_grade_authorized=False",
    ]
    for cohort in audit.cohorts:
        lines.extend(
            [
                "",
                f"== cohort {cohort.compatibility_id} ==",
                f"status={cohort.status}",
                (
                    "observations="
                    f"{cohort.cohort_observation_rows} "
                    f"raw_extractable={cohort.raw_extractable_rows} "
                    f"unique_ticker_sessions={cohort.unique_ticker_sessions}"
                ),
                (
                    f"raw_sessions={cohort.raw_sessions} "
                    f"range={cohort.raw_date_min}..{cohort.raw_date_max} "
                    f"tickers={cohort.raw_tickers}"
                ),
                (
                    f"primary_eligible_rows={cohort.primary_eligible_rows} "
                    f"primary_eligible_sessions={cohort.primary_eligible_sessions} "
                    f"range={cohort.primary_date_min}..{cohort.primary_date_max}"
                ),
                (
                    f"folds_formed={cohort.folds_formed} "
                    f"min_folds_for_verdict={cohort.min_folds_for_verdict}"
                ),
                f"fixed={cohort.fixed_challenger_feasibility}",
                f"learned={cohort.learned_challenger_feasibility}",
            ]
        )
        for holdout in cohort.holdout_candidates:
            lines.append(
                f"holdout={holdout.holdout_sessions_candidate} "
                f"folds={holdout.folds_formed} "
                f"geometry_ready={holdout.candidate_geometry_ready}"
            )
    lines.extend(["", "No policy confirmation contract was registered."])
    return "\n".join(lines)
