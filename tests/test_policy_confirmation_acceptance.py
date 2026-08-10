"""Candidate ML-OOS-02 operating-characteristic law tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ml_saham.challenge.policy_confirmation_acceptance import (
    ACCEPTANCE_STUDY_ID,
    AcceptanceScenario,
    CandidateAcceptanceLaw,
    _proportion_evidence,
    default_acceptance_methods,
    default_acceptance_scenarios,
    evaluate_calibration_cell,
    format_acceptance_report,
    run_acceptance_study,
)
from ml_saham.challenge.policy_confirmation_calibration import (
    CalibrationMethod,
    CalibrationResult,
    CalibrationScenario,
)
from ml_saham.challenge.promote import POLICY_CONFIRMATION_CONTRACTS
from ml_saham.challenge.protocols import ACCUM_PATH_V1


def _scenario(*, role="null", **overrides) -> AcceptanceScenario:
    values = dict(
        scenario_id=f"test.{role}",
        challenger_class="fixed",
        n_sessions_total=120,
        holdout_sessions=20,
        true_effect=0.0 if role == "null" else 0.05,
        ar1=0.4,
        noise_sd_at_reference_width=0.2,
    )
    values.update(overrides)
    return AcceptanceScenario(
        stress_family="test",
        role=role,
        scenario=CalibrationScenario(**values),
    )


def _result(spec: AcceptanceScenario, **overrides) -> CalibrationResult:
    values = dict(
        contract_id="policy_confirmation_calibration.synthetic.v2",
        evidence_grade="MEASUREMENT_ONLY",
        scenario_id=spec.scenario.scenario_id,
        challenger_class="fixed",
        method_id="nw",
        method_kind="newey_west_normal",
        seed=1,
        n_replications=1000,
        n_valid_replications=1000,
        n_folds_formed=3,
        n_eval_sessions_geometry=75,
        mean_observed_sessions=75.0,
        mean_observed_fraction=1.0,
        true_target_mean=spec.scenario.true_effect,
        mean_selected_estimate=spec.scenario.true_effect,
        mean_selection_bias=0.0,
        coverage_rate=0.96,
        false_superiority_rate=0.04 if spec.role == "null" else None,
        false_positive_rate=0.04 if spec.role == "null" else None,
        directional_detection_rate=(
            0.90 if spec.role == "alternative" else None
        ),
        mean_interval_width=0.08,
        fit_capacity_mode="NOT_APPLICABLE_FIXED",
        policy_grade_authorized=False,
        status="MEASURED",
        notes=(),
    )
    values.update(overrides)
    return CalibrationResult(**values)


def _method() -> CalibrationMethod:
    return CalibrationMethod(
        method_id="nw",
        method_kind="newey_west_normal",
        hac_lag=3,
        n_resamples=20,
    )


def test_wilson_evidence_records_count_bounds_and_mcse():
    evidence = _proportion_evidence(0.95, 1000, confidence_level=0.95)
    assert evidence is not None
    assert evidence.successes == 950
    assert evidence.trials == 1000
    assert evidence.lower_bound < evidence.estimate < evidence.upper_bound
    assert evidence.monte_carlo_standard_error == pytest.approx(
        (0.95 * 0.05 / 1000) ** 0.5
    )


def test_candidate_cell_requires_uncertainty_bounds_not_only_point_rate():
    spec = _scenario()
    result = _result(
        spec,
        n_replications=20,
        n_valid_replications=20,
        coverage_rate=0.95,
        false_superiority_rate=0.05,
        false_positive_rate=0.05,
    )
    cell = evaluate_calibration_cell(spec, result, CandidateAcceptanceLaw())
    assert cell.status == "FAIL_CANDIDATE_CELL"
    assert any("lower bound" in reason for reason in cell.reasons)
    assert any("upper bound" in reason for reason in cell.reasons)


def test_candidate_null_and_alternative_can_pass_explicit_law():
    law = CandidateAcceptanceLaw()
    null = _scenario()
    alt = _scenario(role="alternative")
    assert evaluate_calibration_cell(null, _result(null), law).status == (
        "PASS_CANDIDATE_CELL"
    )
    assert evaluate_calibration_cell(alt, _result(alt), law).status == (
        "PASS_CANDIDATE_CELL"
    )


def test_candidate_null_uses_directional_false_superiority_not_two_sided_rate():
    spec = _scenario()
    cell = evaluate_calibration_cell(
        spec,
        _result(spec, false_superiority_rate=0.04, false_positive_rate=0.20),
        CandidateAcceptanceLaw(),
    )
    assert cell.status == "PASS_CANDIDATE_CELL"
    assert cell.false_superiority is not None
    assert cell.false_superiority.estimate == 0.04


def test_search_and_regime_probes_fail_closed_even_with_good_numbers():
    search = _scenario(role="multiplicity_probe", search_width=5)
    regime = _scenario(role="regime_probe", regime_shift=-0.1)
    law = CandidateAcceptanceLaw()
    search_cell = evaluate_calibration_cell(search, _result(search), law)
    regime_cell = evaluate_calibration_cell(regime, _result(regime), law)
    assert search_cell.status == "INELIGIBLE_MULTIPLICITY"
    assert regime_cell.status == "BLOCKED_REGIME"


def test_identity_mismatch_fails_closed():
    spec = _scenario()
    with pytest.raises(ValueError, match="identity mismatch"):
        evaluate_calibration_cell(
            spec,
            _result(spec, scenario_id="wrong"),
            CandidateAcceptanceLaw(),
        )


def test_default_grid_is_predeclared_and_capacity_scoped():
    scenarios = default_acceptance_scenarios(session_counts=(120,))
    assert len(scenarios) == 8
    assert {item.role for item in scenarios} == {
        "null",
        "alternative",
        "multiplicity_probe",
        "regime_probe",
    }
    assert all(item.scenario.challenger_class == "fixed" for item in scenarios)
    methods = default_acceptance_methods(n_resamples=20)
    assert [item.block_length for item in methods[:3]] == [3, 5, 10]
    assert [item.hac_lag for item in methods[3:]] == [3, 5, 10]


def test_study_is_deterministic_non_authoritative_and_groups_required_cells():
    scenarios = (
        _scenario(),
        _scenario(role="alternative"),
    )
    kwargs = dict(
        scenarios=scenarios,
        methods=(_method(),),
        seed=17,
        n_replications=30,
    )
    first = run_acceptance_study(**kwargs)
    second = run_acceptance_study(**kwargs)
    assert first == second
    assert first.study_id == ACCEPTANCE_STUDY_ID
    assert first.evidence_grade == "MEASUREMENT_ONLY"
    assert first.policy_grade_authorized is False
    assert first.candidates[0].required_cells == 2
    assert POLICY_CONFIRMATION_CONTRACTS == frozenset()
    assert ACCUM_PATH_V1.policy_confirmation_contract_id == ""
    text = format_acceptance_report(first)
    assert "policy_grade_authorized=False" in text
    assert "Task 06 remains blocked" in text


@pytest.mark.parametrize(
    "field, value",
    (
        ("law_version", "policy_confirmation_acceptance.candidate.test"),
        ("monte_carlo_confidence_level", 0.90),
        ("minimum_folds", 2),
        ("maximum_false_superiority_rate", 0.05),
        ("minimum_coverage", 0.90),
        ("minimum_directional_detection_rate", 0.75),
        ("minimum_valid_replication_rate", 0.95),
        ("minimum_observed_session_fraction", 0.85),
        ("maximum_monte_carlo_standard_error", 0.02),
        ("maximum_interval_width_to_effect", 1.5),
        ("regime_policy", "EXPLICIT_BREAK_BLOCKS_CONFIRMATION"),
        ("search_policy", "ONE_PREREGISTERED_CHALLENGER_ONLY"),
    ),
)
def test_law_identity_changes_with_each_material_value(field, value):
    base = CandidateAcceptanceLaw()
    if getattr(base, field) == value:
        field = "law_version"
        value = "policy_confirmation_acceptance.candidate.test"
    changed = replace(base, **{field: value})
    assert changed.law_id != base.law_id


def test_invalid_role_semantics_are_rejected():
    with pytest.raises(ValueError, match="null scenario"):
        _scenario(true_effect=0.05)
    with pytest.raises(ValueError, match="multiplicity probe"):
        _scenario(role="multiplicity_probe", search_width=1)
    with pytest.raises(ValueError, match="regime probe"):
        _scenario(role="regime_probe", regime_shift=0.0)
    with pytest.raises(ValueError, match="one challenger"):
        _scenario(search_width=2)
    with pytest.raises(ValueError, match="no regime shift"):
        _scenario(role="alternative", regime_shift=-0.1)


def test_incomplete_eligible_stress_pair_is_rejected():
    with pytest.raises(ValueError, match="paired null and alternative"):
        run_acceptance_study(
            scenarios=(_scenario(),),
            methods=(_method(),),
            n_replications=2,
        )


def test_mismatched_null_alternative_dgp_pair_is_rejected():
    with pytest.raises(ValueError, match="DGP material mismatch"):
        run_acceptance_study(
            scenarios=(
                _scenario(),
                _scenario(role="alternative", ar1=0.7),
            ),
            methods=(_method(),),
            n_replications=2,
        )


def test_invalid_replication_counts_fail_closed():
    spec = _scenario()
    with pytest.raises(ValueError, match="replication counts"):
        evaluate_calibration_cell(
            spec,
            _result(spec, n_valid_replications=1001),
            CandidateAcceptanceLaw(),
        )


def test_invalid_monte_carlo_confidence_is_rejected():
    with pytest.raises(ValueError, match="must be in"):
        CandidateAcceptanceLaw(monte_carlo_confidence_level=1.0)
