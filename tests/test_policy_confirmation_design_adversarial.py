"""Adversarial tests for ML-OOS-02 measurement primitives (fail-closed)."""

from __future__ import annotations

import pytest

from ml_saham.challenge.metrics import ic_safe
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.policy_confirmation_design import (
    MultiplicitySearchRecord,
    group_pairs_by_session,
    holdout_geometry_candidate,
    multiplicity_search_record,
    session_rank_ics,
    sessions_per_parameter,
)
from ml_saham.challenge.promote import POLICY_CONFIRMATION_CONTRACTS
from ml_saham.challenge.runner import _horizon_ics


def test_holdout_exceeding_calendar_is_not_valid_placement():
    """holdout=20 on n=10 must never report holdout_after_all_fold_tests=True."""
    bad = holdout_geometry_candidate(
        10,
        n_folds=3,
        embargo_sessions=20,
        min_folds_for_verdict=2,
        holdout_sessions_candidate=20,
    )
    assert bad.folds_formed == 0
    assert bad.holdout_after_all_fold_tests is False
    assert "exceeds calendar" in bad.notes.lower()


def test_holdout_equal_to_calendar_with_no_fold_region_invalid():
    bad = holdout_geometry_candidate(
        10,
        n_folds=3,
        embargo_sessions=1,
        min_folds_for_verdict=2,
        holdout_sessions_candidate=10,
    )
    assert bad.n_sessions_for_folds == 0
    assert bad.holdout_after_all_fold_tests is False


def test_holdout_rejects_negative_inputs():
    with pytest.raises(ValueError, match="n_sessions_total"):
        holdout_geometry_candidate(
            -1,
            n_folds=3,
            embargo_sessions=1,
            min_folds_for_verdict=2,
            holdout_sessions_candidate=0,
        )
    with pytest.raises(ValueError, match="holdout_sessions_candidate"):
        holdout_geometry_candidate(
            10,
            n_folds=3,
            embargo_sessions=1,
            min_folds_for_verdict=2,
            holdout_sessions_candidate=-5,
        )
    with pytest.raises(ValueError, match="embargo_sessions"):
        holdout_geometry_candidate(
            10,
            n_folds=3,
            embargo_sessions=-1,
            min_folds_for_verdict=2,
            holdout_sessions_candidate=0,
        )
    with pytest.raises(ValueError, match="n_folds"):
        holdout_geometry_candidate(
            10,
            n_folds=0,
            embargo_sessions=1,
            min_folds_for_verdict=2,
            holdout_sessions_candidate=0,
        )
    with pytest.raises(ValueError, match="exact int"):
        holdout_geometry_candidate(
            True,  # type: ignore[arg-type]
            n_folds=3,
            embargo_sessions=1,
            min_folds_for_verdict=2,
            holdout_sessions_candidate=0,
        )


def test_multiplicity_rejects_empty_and_duplicate_search_universe():
    with pytest.raises(ValueError, match="search_id"):
        multiplicity_search_record(
            search_id="",
            challenger_ids=("a",),
            selection_rule="pre_registered_primary",
        )
    with pytest.raises(ValueError, match="selection_rule"):
        multiplicity_search_record(
            search_id="s1",
            challenger_ids=("a",),
            selection_rule="",
        )
    with pytest.raises(ValueError, match="unique"):
        multiplicity_search_record(
            search_id="s1",
            challenger_ids=("equal_sleeves", "equal_sleeves"),
            selection_rule="pre_registered_primary",
        )
    with pytest.raises(ValueError, match="non-empty"):
        multiplicity_search_record(
            search_id="s1",
            challenger_ids=(),
            selection_rule="pre_registered_primary",
        )
    with pytest.raises(ValueError, match="challenger_ids entry"):
        multiplicity_search_record(
            search_id="s1",
            challenger_ids=(1,),  # type: ignore[arg-type]
            selection_rule="pre_registered_primary",
        )
    with pytest.raises(ValueError, match="search_id"):
        MultiplicitySearchRecord(
            search_id="",
            challenger_ids=("a",),
            selection_rule="x",
            primary_metric="m",
            n_comparisons=1,
        )


def test_session_ic_reports_valid_pairs_not_raw_input_length():
    rows = [
        ("2024-01-02", 1.0, 0.01),
        ("2024-01-02", 2.0, 0.02),
        ("2024-01-02", float("inf"), 0.03),  # dropped
        ("2024-01-02", 3.0, float("nan")),  # dropped
    ]
    points = session_rank_ics(group_pairs_by_session(rows))
    assert len(points) == 1
    p = points[0]
    assert p.n_input_pairs == 4
    assert p.n_valid_pairs == 2
    assert p.rank_ic is not None


def test_ic_safe_rejects_infinity_and_nan_pairs():
    """Shared ic_safe blast-radius: non-finite pairs must not yield a real IC."""
    # Pure infinity should not look valid.
    assert ic_safe([1.0, float("inf")], [0.1, 0.2]) is None
    assert ic_safe([float("-inf"), 2.0], [0.1, 0.2]) is None
    # Contamination invalidates the complete metric; no denominator shrink.
    assert ic_safe([1.0, 2.0, float("inf")], [0.1, 0.2, 0.3]) is None
    assert ic_safe([1.0, float("nan")], [0.1, 0.2]) is None


def test_runner_horizon_ic_cannot_bypass_min_n_after_nonfinite_input():
    rows = [
        PanelRow(
            ticker=f"T{i:02d}",
            date="2024-01-02",
            components={},
            excess={10: float(i)},
        )
        for i in range(20)
    ]
    contaminated_scores = [1.0, 2.0, *([float("inf")] * 18)]
    assert _horizon_ics(rows, contaminated_scores, (10,)) == {"10": None}


def test_holdout_separates_temporal_placement_from_minimum_fold_depth():
    thin = holdout_geometry_candidate(
        60,
        n_folds=3,
        embargo_sessions=20,
        min_folds_for_verdict=2,
        holdout_sessions_candidate=20,
    )
    assert thin.folds_formed == 1
    assert thin.holdout_after_all_fold_tests is True
    assert thin.meets_min_folds_for_verdict is False
    assert thin.candidate_geometry_ready is False
    assert "insufficient folds" in thin.notes


@pytest.mark.parametrize(
    "kwargs, match",
    [
        (
            dict(
                search_id="s",
                challenger_ids=("",),
                selection_rule="r",
                primary_metric="m",
                n_comparisons=1,
            ),
            "challenger_ids entry",
        ),
        (
            dict(
                search_id="s",
                challenger_ids=("a",),
                selection_rule="r",
                primary_metric="",
                n_comparisons=1,
            ),
            "primary_metric",
        ),
        (
            dict(
                search_id="s",
                challenger_ids=("a",),
                selection_rule="r",
                primary_metric="m",
                n_comparisons=True,
            ),
            "n_comparisons",
        ),
    ],
)
def test_direct_multiplicity_constructor_matches_factory_validation(kwargs, match):
    with pytest.raises(ValueError, match=match):
        MultiplicitySearchRecord(**kwargs)


def test_sessions_per_parameter_rejects_negative_train():
    with pytest.raises(ValueError, match="train_sessions"):
        sessions_per_parameter(-1, n_fit_parameters=5)


def test_still_no_policy_confirmation_registry():
    assert len(POLICY_CONFIRMATION_CONTRACTS) == 0
