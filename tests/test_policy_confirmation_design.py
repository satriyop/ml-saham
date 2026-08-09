"""ML-OOS-02 design study machinery — measurement only, no threshold adoption."""

from __future__ import annotations

from ml_saham.challenge.policy_confirmation_design import (
    POLICY_CONFIRMATION_CONTRACT_DRAFT_ID,
    POLICY_CONFIRMATION_REQUIRED_AXES,
    build_geometry_depth_profile,
    build_ml_oos_02_design_study,
    format_design_study_report,
    group_pairs_by_session,
    holdout_geometry_candidate,
    multiplicity_search_record,
    session_rank_ics,
    sessions_per_parameter,
    summarize_session_ics,
)
from ml_saham.challenge.promote import POLICY_CONFIRMATION_CONTRACTS
from ml_saham.challenge.protocols import ACCUM_PATH_V1


def test_design_study_does_not_register_confirmation_contract():
    bundle = build_ml_oos_02_design_study()
    assert bundle.draft_contract_id == POLICY_CONFIRMATION_CONTRACT_DRAFT_ID
    assert POLICY_CONFIRMATION_CONTRACT_DRAFT_ID not in POLICY_CONFIRMATION_CONTRACTS
    assert len(POLICY_CONFIRMATION_CONTRACTS) == 0
    assert ACCUM_PATH_V1.policy_confirmation_contract_id == ""
    assert ACCUM_PATH_V1.evidence_grade == "EXPLORATORY"


def test_design_study_does_not_write_policy_session_floors_into_protocol():
    """Geometry minima stay structural; no policy_min_* on Protocol."""
    fields = ACCUM_PATH_V1.__dataclass_fields__
    assert "policy_min_train_sessions" not in fields
    assert "policy_min_test_sessions" not in fields
    assert "geometry_min_train_sessions" in fields
    bundle = build_ml_oos_02_design_study()
    assert "No policy_min_* written into Protocol" in " ".join(
        bundle.explicit_non_selections
    )


def test_required_axes_cover_study_scope():
    for axis in (
        "policy_min_train_sessions",
        "policy_min_test_sessions",
        "session_ic_method",
        "ic_uncertainty_method",
        "final_holdout_sessions",
        "multiplicity_rule",
        "challenger_class",
    ):
        assert axis in POLICY_CONFIRMATION_REQUIRED_AXES


def test_geometry_depth_profile_matches_accum_structural_minima():
    profile = build_geometry_depth_profile(
        n_folds=3,
        embargo_sessions=20,
        min_folds_for_verdict=2,
    )
    assert profile.structural_minima.geometry_min_train_sessions == 1
    assert profile.structural_minima.geometry_min_test_sessions == 7
    # First multi-fold readiness still informational
    assert profile.structural_minima.first_n_sessions_min_folds_for_verdict == 44


def test_session_rank_ics_and_summary():
    # Two sessions, clear ranking each day
    rows = [
        ("2024-01-02", 3.0, 0.02),
        ("2024-01-02", 2.0, 0.01),
        ("2024-01-02", 1.0, -0.01),
        ("2024-01-03", 1.0, 0.03),
        ("2024-01-03", 2.0, 0.00),
        ("2024-01-03", 3.0, -0.02),
    ]
    grouped = group_pairs_by_session(rows)
    points = session_rank_ics(grouped)
    assert len(points) == 2
    assert all(p.n_valid_pairs == 3 for p in points)
    assert all(p.n_input_pairs == 3 for p in points)
    assert points[0].rank_ic is not None
    summary = summarize_session_ics(
        points,
        pooled_scores=[r[1] for r in rows],
        pooled_returns=[r[2] for r in rows],
    )
    assert summary.n_sessions == 2
    assert summary.n_sessions_with_ic == 2
    assert summary.mean_session_ic is not None
    assert summary.pooled_rank_ic is not None
    assert any("no bootstrap" in n for n in summary.notes)


def test_holdout_placement_candidates():
    ok = holdout_geometry_candidate(
        120,
        n_folds=3,
        embargo_sessions=20,
        holdout_sessions_candidate=20,
    )
    assert ok.n_sessions_for_folds == 100
    assert ok.folds_formed >= 1
    assert ok.holdout_after_all_fold_tests is True

    zero = holdout_geometry_candidate(
        120, n_folds=3, embargo_sessions=20, holdout_sessions_candidate=0
    )
    assert zero.holdout_after_all_fold_tests is False


def test_multiplicity_search_record_requires_consistent_count():
    import pytest

    from ml_saham.challenge.policy_confirmation_design import MultiplicitySearchRecord

    rec = multiplicity_search_record(
        search_id="s1",
        challenger_ids=("equal_sleeves", "ridge_reweight"),
        selection_rule="pre_registered_primary",
    )
    assert rec.n_comparisons == 2
    with pytest.raises(ValueError, match="n_comparisons"):
        MultiplicitySearchRecord(
            search_id="bad",
            challenger_ids=("a", "b"),
            selection_rule="x",
            primary_metric="m",
            n_comparisons=1,
        )


def test_sessions_per_parameter_descriptive():
    assert sessions_per_parameter(20, n_fit_parameters=5) == 4.0
    assert sessions_per_parameter(10, n_fit_parameters=0) == float("inf")
    assert sessions_per_parameter(10, n_fit_parameters=-1) is None


def test_format_report_is_non_empty():
    text = format_design_study_report(build_ml_oos_02_design_study())
    assert "ML-OOS-02" in text
    assert "Open decisions" in text
    assert "Explicit non-selections" in text
