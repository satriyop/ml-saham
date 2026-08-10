"""Session-native estimand candidate for fixed ACCUM score-weight comparison.

This module measures one paired rank-IC difference per explicit calendar
session for ``equal_sleeves`` versus ``production``.  It is design research:
it does not choose minimum-name or effect floors, change the shipped verdict,
register a confirmation contract, or authorize promotion.

Semantic classification: PROTOCOL_CONTRACT design research (non-authoritative).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any, Literal, Sequence

from ml_saham.challenge.metrics import ic_safe

SESSION_ESTIMAND_CONTRACT_ID = (
    "policy_confirmation_session_estimand.accum_score_weights.equal_sleeves.candidate.v1"
)
SESSION_ESTIMAND_EVIDENCE_GRADE = "MEASUREMENT_ONLY"
SESSION_ESTIMAND_POLICY_ID = "screener.accum.score_weights"
SESSION_ESTIMAND_PROTOCOL_ID = "accum_path_v1"
SESSION_ESTIMAND_BASELINE_ID = "production"
SESSION_ESTIMAND_CHALLENGER_ID = "equal_sleeves"
SESSION_ESTIMAND_PRIMARY_HORIZON = 10

SessionStatus = Literal[
    "MEASURED",
    "MISSING_CALENDAR_SESSION",
    "INSUFFICIENT_NAMES",
    "MISSING_NAME_VALUE",
    "INVALID_NAME_VALUE",
    "CONSTANT_PRODUCTION_SCORE",
    "CONSTANT_CHALLENGER_SCORE",
    "CONSTANT_PRIMARY_TARGET",
    "UNDEFINED_RANK_IC",
]


def _identity(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed string")
    return value


def _exact_int(name: str, value: object, *, minimum: int) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be exact int")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


@dataclass(frozen=True)
class FixedScoreSessionObservation:
    session: str
    ticker: str
    production_score: object
    equal_sleeves_score: object
    primary_excess_return: object

    def __post_init__(self) -> None:
        _identity("session", self.session)
        _identity("ticker", self.ticker)


@dataclass(frozen=True)
class FixedScoreSessionEstimandPoint:
    session: str
    n_input_names: int
    n_complete_names: int
    n_missing_name_values: int
    n_invalid_name_values: int
    production_rank_ic: float | None
    equal_sleeves_rank_ic: float | None
    challenger_minus_production_rank_ic: float | None
    status: SessionStatus
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FixedScoreSessionEstimandStudy:
    contract_id: str
    evidence_grade: str
    policy_id: str
    protocol_id: str
    baseline_id: str
    challenger_id: str
    input_identity_binding_status: str
    production_identity_verified: bool
    primary_horizon: int
    estimand: str
    expected_sessions: tuple[str, ...]
    minimum_names_candidate: int
    points: tuple[FixedScoreSessionEstimandPoint, ...]
    n_sessions_expected: int
    n_sessions_measured: int
    mean_session_ic_delta: float | None
    status: str
    target_contract_locked: bool
    effect_floor_selected: bool
    policy_grade_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["points"] = [point.to_dict() for point in self.points]
        return payload


def _invalid_point(
    session: str,
    *,
    status: SessionStatus,
    reason: str,
    n_input: int,
    n_complete: int = 0,
    n_missing: int = 0,
    n_invalid: int = 0,
) -> FixedScoreSessionEstimandPoint:
    return FixedScoreSessionEstimandPoint(
        session=session,
        n_input_names=n_input,
        n_complete_names=n_complete,
        n_missing_name_values=n_missing,
        n_invalid_name_values=n_invalid,
        production_rank_ic=None,
        equal_sleeves_rank_ic=None,
        challenger_minus_production_rank_ic=None,
        status=status,
        reason=reason,
    )


def _measure_session(
    session: str,
    observations: Sequence[FixedScoreSessionObservation],
    *,
    minimum_names_candidate: int,
) -> FixedScoreSessionEstimandPoint:
    if not observations:
        return _invalid_point(
            session,
            status="MISSING_CALENDAR_SESSION",
            reason="expected calendar session has no observations",
            n_input=0,
        )
    production: list[float] = []
    challenger: list[float] = []
    targets: list[float] = []
    n_missing = 0
    n_invalid = 0
    for item in observations:
        values = (
            item.production_score,
            item.equal_sleeves_score,
            item.primary_excess_return,
        )
        if any(value is None for value in values):
            n_missing += 1
            continue
        converted = tuple(_finite(value) for value in values)
        if any(value is None for value in converted):
            n_invalid += 1
            continue
        production.append(converted[0])  # type: ignore[arg-type]
        challenger.append(converted[1])  # type: ignore[arg-type]
        targets.append(converted[2])  # type: ignore[arg-type]

    n_complete = len(production)
    if n_missing:
        return _invalid_point(
            session,
            status="MISSING_NAME_VALUE",
            reason="missing name-level values are not deleted or imputed",
            n_input=len(observations),
            n_complete=n_complete,
            n_missing=n_missing,
            n_invalid=n_invalid,
        )
    if n_invalid:
        return _invalid_point(
            session,
            status="INVALID_NAME_VALUE",
            reason="non-numeric or non-finite name-level values invalidate the session",
            n_input=len(observations),
            n_complete=n_complete,
            n_invalid=n_invalid,
        )
    if len(observations) < minimum_names_candidate:
        return _invalid_point(
            session,
            status="INSUFFICIENT_NAMES",
            reason="input names below the explicit research candidate minimum",
            n_input=len(observations),
            n_complete=n_complete,
        )
    if max(production) - min(production) < 1e-12:
        return _invalid_point(
            session,
            status="CONSTANT_PRODUCTION_SCORE",
            reason="production score rank is undefined",
            n_input=len(observations),
            n_complete=n_complete,
        )
    if max(challenger) - min(challenger) < 1e-12:
        return _invalid_point(
            session,
            status="CONSTANT_CHALLENGER_SCORE",
            reason="challenger score rank is undefined",
            n_input=len(observations),
            n_complete=n_complete,
        )
    if max(targets) - min(targets) < 1e-12:
        return _invalid_point(
            session,
            status="CONSTANT_PRIMARY_TARGET",
            reason="primary target rank is undefined",
            n_input=len(observations),
            n_complete=n_complete,
        )

    production_ic = ic_safe(production, targets)
    challenger_ic = ic_safe(challenger, targets)
    if production_ic is None or challenger_ic is None:
        return _invalid_point(
            session,
            status="UNDEFINED_RANK_IC",
            reason="shipped rank-IC metric rejected an otherwise complete session",
            n_input=len(observations),
            n_complete=n_complete,
        )
    return FixedScoreSessionEstimandPoint(
        session=session,
        n_input_names=len(observations),
        n_complete_names=n_complete,
        n_missing_name_values=0,
        n_invalid_name_values=0,
        production_rank_ic=production_ic,
        equal_sleeves_rank_ic=challenger_ic,
        challenger_minus_production_rank_ic=challenger_ic - production_ic,
        status="MEASURED",
        reason=None,
    )


def measure_accum_score_weights_session_estimand(
    observations: Sequence[FixedScoreSessionObservation],
    *,
    expected_sessions: Sequence[str],
    minimum_names_candidate: int,
) -> FixedScoreSessionEstimandStudy:
    """Measure the paired candidate estimand on an explicit complete calendar.

    ``minimum_names_candidate`` is required and is recorded as a research input;
    this function deliberately provides no default and adopts no product floor.
    """
    minimum_names = _exact_int(
        "minimum_names_candidate", minimum_names_candidate, minimum=2
    )
    calendar = tuple(_identity("expected_session", item) for item in expected_sessions)
    if not calendar:
        raise ValueError("expected_sessions must be non-empty")
    if len(set(calendar)) != len(calendar):
        raise ValueError("expected_sessions must be unique")
    if calendar != tuple(sorted(calendar)):
        raise ValueError("expected_sessions must be strictly increasing")

    grouped: dict[str, list[FixedScoreSessionObservation]] = {
        session: [] for session in calendar
    }
    seen_keys: set[tuple[str, str]] = set()
    for observation in observations:
        if observation.session not in grouped:
            raise ValueError(
                f"observation session {observation.session!r} is outside expected calendar"
            )
        key = (observation.session, observation.ticker)
        if key in seen_keys:
            raise ValueError(f"duplicate ticker/session observation: {key!r}")
        seen_keys.add(key)
        grouped[observation.session].append(observation)

    points = tuple(
        _measure_session(
            session,
            tuple(sorted(grouped[session], key=lambda item: item.ticker)),
            minimum_names_candidate=minimum_names,
        )
        for session in calendar
    )
    measured = tuple(
        point.challenger_minus_production_rank_ic
        for point in points
        if point.status == "MEASURED"
        and point.challenger_minus_production_rank_ic is not None
    )
    complete = len(measured) == len(calendar)
    return FixedScoreSessionEstimandStudy(
        contract_id=SESSION_ESTIMAND_CONTRACT_ID,
        evidence_grade=SESSION_ESTIMAND_EVIDENCE_GRADE,
        policy_id=SESSION_ESTIMAND_POLICY_ID,
        protocol_id=SESSION_ESTIMAND_PROTOCOL_ID,
        baseline_id=SESSION_ESTIMAND_BASELINE_ID,
        challenger_id=SESSION_ESTIMAND_CHALLENGER_ID,
        input_identity_binding_status="NOT_BOUND_MEASUREMENT_INPUT",
        production_identity_verified=False,
        primary_horizon=SESSION_ESTIMAND_PRIMARY_HORIZON,
        estimand=(
            "unweighted_mean_by_calendar_session_of_"
            "rank_ic_equal_sleeves_minus_rank_ic_production"
        ),
        expected_sessions=calendar,
        minimum_names_candidate=minimum_names,
        points=points,
        n_sessions_expected=len(calendar),
        n_sessions_measured=len(measured),
        mean_session_ic_delta=(statistics.fmean(measured) if complete else None),
        status=(
            "MEASURED_COMPLETE_CALENDAR"
            if complete
            else "BLOCKED_INCOMPLETE_SESSION_ESTIMANDS"
        ),
        target_contract_locked=False,
        effect_floor_selected=False,
        policy_grade_authorized=False,
    )
