"""Session-native candidate estimand for fixed ACCUM score weights."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ml_saham.challenge.policy_confirmation_session_estimand import (
    SESSION_ESTIMAND_CONTRACT_ID,
    FixedScoreSessionObservation,
    measure_accum_score_weights_session_estimand,
)


def _session(session: str) -> list[FixedScoreSessionObservation]:
    return [
        FixedScoreSessionObservation(session, "AAA", 3.0, 1.0, 0.03),
        FixedScoreSessionObservation(session, "BBB", 2.0, 2.0, 0.01),
        FixedScoreSessionObservation(session, "CCC", 1.0, 3.0, -0.02),
    ]


def test_complete_calendar_measures_paired_session_ic_delta_deterministically():
    rows = _session("2026-01-02") + _session("2026-01-05")
    kwargs = dict(
        expected_sessions=("2026-01-02", "2026-01-05"),
        minimum_names_candidate=3,
    )
    first = measure_accum_score_weights_session_estimand(rows, **kwargs)
    second = measure_accum_score_weights_session_estimand(tuple(reversed(rows)), **kwargs)

    assert first == second
    assert first.contract_id == SESSION_ESTIMAND_CONTRACT_ID
    assert first.status == "MEASURED_COMPLETE_CALENDAR"
    assert first.n_sessions_measured == 2
    assert first.mean_session_ic_delta == pytest.approx(-2.0)
    assert all(point.status == "MEASURED" for point in first.points)
    assert first.target_contract_locked is False
    assert first.effect_floor_selected is False
    assert first.policy_grade_authorized is False


def test_missing_calendar_session_blocks_mean_without_compaction():
    result = measure_accum_score_weights_session_estimand(
        _session("2026-01-02"),
        expected_sessions=("2026-01-02", "2026-01-05"),
        minimum_names_candidate=3,
    )

    assert result.status == "BLOCKED_INCOMPLETE_SESSION_ESTIMANDS"
    assert result.n_sessions_measured == 1
    assert result.mean_session_ic_delta is None
    assert result.points[1].status == "MISSING_CALENDAR_SESSION"


@pytest.mark.parametrize(
    "field,value,status",
    (
        ("production_score", None, "MISSING_NAME_VALUE"),
        ("equal_sleeves_score", float("nan"), "INVALID_NAME_VALUE"),
        ("primary_excess_return", "bad", "INVALID_NAME_VALUE"),
    ),
)
def test_incomplete_name_values_invalidate_session_without_deletion(
    field, value, status
):
    rows = _session("2026-01-02")
    rows[0] = replace(rows[0], **{field: value})
    result = measure_accum_score_weights_session_estimand(
        rows,
        expected_sessions=("2026-01-02",),
        minimum_names_candidate=2,
    )

    assert result.status == "BLOCKED_INCOMPLETE_SESSION_ESTIMANDS"
    assert result.points[0].status == status
    assert result.points[0].n_input_names == 3
    assert result.points[0].n_complete_names == 2
    assert result.mean_session_ic_delta is None


@pytest.mark.parametrize(
    "field,status",
    (
        ("production_score", "CONSTANT_PRODUCTION_SCORE"),
        ("equal_sleeves_score", "CONSTANT_CHALLENGER_SCORE"),
        ("primary_excess_return", "CONSTANT_PRIMARY_TARGET"),
    ),
)
def test_constant_rank_input_has_typed_failure(field, status):
    rows = _session("2026-01-02")
    rows = [replace(row, **{field: 1.0}) for row in rows]
    result = measure_accum_score_weights_session_estimand(
        rows,
        expected_sessions=("2026-01-02",),
        minimum_names_candidate=3,
    )

    assert result.points[0].status == status
    assert result.mean_session_ic_delta is None


def test_candidate_minimum_is_explicit_and_not_a_product_floor():
    result = measure_accum_score_weights_session_estimand(
        _session("2026-01-02")[:2],
        expected_sessions=("2026-01-02",),
        minimum_names_candidate=3,
    )

    assert result.minimum_names_candidate == 3
    assert result.points[0].status == "INSUFFICIENT_NAMES"
    assert result.effect_floor_selected is False
    with pytest.raises(ValueError, match="exact int"):
        measure_accum_score_weights_session_estimand(
            (), expected_sessions=("2026-01-02",), minimum_names_candidate=True
        )


def test_duplicate_or_out_of_calendar_rows_fail_closed():
    rows = _session("2026-01-02")
    with pytest.raises(ValueError, match="duplicate ticker/session"):
        measure_accum_score_weights_session_estimand(
            rows + [rows[0]],
            expected_sessions=("2026-01-02",),
            minimum_names_candidate=3,
        )
    with pytest.raises(ValueError, match="outside expected calendar"):
        measure_accum_score_weights_session_estimand(
            rows,
            expected_sessions=("2026-01-05",),
            minimum_names_candidate=3,
        )
    with pytest.raises(ValueError, match="strictly increasing"):
        measure_accum_score_weights_session_estimand(
            rows,
            expected_sessions=("2026-01-05", "2026-01-02"),
            minimum_names_candidate=3,
        )


def test_serialization_records_identity_and_non_authority():
    payload = measure_accum_score_weights_session_estimand(
        _session("2026-01-02"),
        expected_sessions=("2026-01-02",),
        minimum_names_candidate=3,
    ).to_dict()

    assert payload["policy_id"] == "screener.accum.score_weights"
    assert payload["protocol_id"] == "accum_path_v1"
    assert payload["baseline_id"] == "production"
    assert payload["challenger_id"] == "equal_sleeves"
    assert payload["input_identity_binding_status"] == (
        "NOT_BOUND_MEASUREMENT_INPUT"
    )
    assert payload["production_identity_verified"] is False
    assert payload["primary_horizon"] == 10
    assert payload["target_contract_locked"] is False
    assert payload["effect_floor_selected"] is False
    assert payload["policy_grade_authorized"] is False
