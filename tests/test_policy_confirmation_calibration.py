"""ML-OOS-02 synthetic calibration harness (non-authoritative)."""

from __future__ import annotations

import numpy as np
import pytest

from ml_saham.challenge.policy_confirmation_calibration import (
    AUTO_BLOCK_SELECTOR_ID,
    CALIBRATION_CONTRACT_ID,
    CalibrationMethod,
    CalibrationScenario,
    calibrate_scenario,
    format_calibration_report,
    run_calibration_study,
    select_stationary_bootstrap_block_length,
)
from ml_saham.challenge.promote import POLICY_CONFIRMATION_CONTRACTS
from ml_saham.challenge.protocols import ACCUM_PATH_V1


def _scenario(**overrides) -> CalibrationScenario:
    values = dict(
        scenario_id="fixed-null",
        challenger_class="fixed",
        n_sessions_total=100,
        holdout_sessions=20,
        true_effect=0.0,
        ar1=0.4,
        noise_sd_at_reference_width=0.2,
        heteroskedastic_strength=0.5,
        names_per_session=45,
        name_missing_rate=0.05,
        min_valid_names=20,
    )
    values.update(overrides)
    return CalibrationScenario(**values)


def _bootstrap(**overrides) -> CalibrationMethod:
    values = dict(
        method_id="sb5",
        method_kind="stationary_bootstrap_percentile",
        confidence_level=0.95,
        block_length=5,
        n_resamples=30,
    )
    values.update(overrides)
    return CalibrationMethod(**values)


def _hac(**overrides) -> CalibrationMethod:
    values = dict(
        method_id="nw5",
        method_kind="newey_west_normal",
        confidence_level=0.95,
        hac_lag=5,
        n_resamples=30,
    )
    values.update(overrides)
    return CalibrationMethod(**values)


def _auto_bootstrap(**overrides) -> CalibrationMethod:
    values = dict(
        method_id="sb-auto",
        method_kind="stationary_bootstrap_percentile_auto",
        confidence_level=0.95,
        n_resamples=30,
        block_length_selector_id=AUTO_BLOCK_SELECTOR_ID,
    )
    values.update(overrides)
    return CalibrationMethod(**values)


def test_calibration_is_deterministic_and_non_authoritative():
    kwargs = dict(
        scenario=_scenario(),
        method=_bootstrap(),
        seed=7,
        n_replications=12,
    )
    first = calibrate_scenario(**kwargs)
    second = calibrate_scenario(**kwargs)
    assert first == second
    assert first.contract_id == CALIBRATION_CONTRACT_ID
    assert first.evidence_grade == "MEASUREMENT_ONLY"
    assert first.policy_grade_authorized is False
    assert POLICY_CONFIRMATION_CONTRACTS == frozenset()
    assert ACCUM_PATH_V1.policy_confirmation_contract_id == ""


def test_calibration_uses_exact_fold_region_and_excludes_holdout():
    result = calibrate_scenario(
        _scenario(n_sessions_total=100, holdout_sessions=20),
        _hac(),
        seed=11,
        n_replications=5,
    )
    assert result.n_folds_formed == 2
    assert result.n_eval_sessions_geometry == 40
    assert result.n_valid_replications == 5
    assert result.status == "MEASURED"


def test_null_separates_directional_false_superiority_from_two_sided_rejection():
    result = calibrate_scenario(
        _scenario(),
        _hac(),
        seed=13,
        n_replications=80,
    )
    assert result.false_superiority_rate is not None
    assert result.false_positive_rate is not None
    assert result.false_superiority_rate <= result.false_positive_rate


def test_geometry_failure_is_typed_not_fake_measurement():
    result = calibrate_scenario(
        _scenario(n_sessions_total=40, holdout_sessions=20),
        _hac(),
        seed=11,
        n_replications=5,
    )
    assert result.status == "NOT_READY_GEOMETRY"
    assert result.n_folds_formed == 0
    assert result.coverage_rate is None


def test_best_of_search_bias_is_measured_and_not_corrected():
    single = calibrate_scenario(
        _scenario(search_width=1),
        _hac(),
        seed=19,
        n_replications=80,
    )
    searched = calibrate_scenario(
        _scenario(scenario_id="search5", search_width=5),
        _hac(),
        seed=19,
        n_replications=80,
    )
    assert single.mean_selection_bias is not None
    assert searched.mean_selection_bias is not None
    assert searched.mean_selection_bias > single.mean_selection_bias
    assert any("unadjusted" in note for note in searched.notes)


def test_missing_name_width_is_reported_in_session_denominator():
    result = calibrate_scenario(
        _scenario(
            names_per_session=20,
            min_valid_names=18,
            name_missing_rate=0.25,
        ),
        _bootstrap(),
        seed=23,
        n_replications=20,
    )
    assert result.mean_observed_fraction is not None
    assert 0.0 < result.mean_observed_fraction < 1.0
    assert result.mean_observed_sessions is not None
    assert result.mean_observed_sessions < result.n_eval_sessions_geometry


def test_automatic_selector_is_deterministic_and_records_used_blocks():
    result = calibrate_scenario(
        _scenario(name_missing_rate=0.0),
        _auto_bootstrap(),
        seed=27,
        n_replications=8,
    )
    assert result.status == "MEASURED"
    assert result.mean_selected_block_length is not None
    assert result.min_selected_block_length is not None
    assert result.max_selected_block_length is not None
    assert result.block_selection_failure_counts == ()
    assert (
        result.min_selected_block_length
        <= result.mean_selected_block_length
        <= result.max_selected_block_length
    )


def test_automatic_selector_fails_closed_on_gaps_short_and_constant_series():
    missing = select_stationary_bootstrap_block_length([1.0, float("nan")] * 10)
    short = select_stationary_bootstrap_block_length(range(9))
    constant = select_stationary_bootstrap_block_length([1.0] * 20)
    assert missing.status == "NONFINITE_CALENDAR_SERIES"
    assert short.status == "INSUFFICIENT_SESSIONS"
    assert constant.status == "DEGENERATE_VARIANCE"
    assert missing.selected_block_length is None


def test_automatic_calibration_preserves_selector_failure_counts():
    result = calibrate_scenario(
        _scenario(
            names_per_session=20,
            min_valid_names=20,
            name_missing_rate=0.05,
        ),
        _auto_bootstrap(),
        seed=29,
        n_replications=8,
    )
    assert result.status == "METHOD_NOT_MEASURABLE"
    assert result.block_selection_failure_counts == (("NONFINITE_CALENDAR_SERIES", 8),)


def test_automatic_method_identity_is_serialized_without_changing_explicit_payload():
    explicit_payload = _bootstrap().to_dict()
    automatic_payload = _auto_bootstrap().to_dict()
    assert "block_length_selector_id" not in explicit_payload
    assert automatic_payload["block_length_selector_id"] == AUTO_BLOCK_SELECTOR_ID
    assert automatic_payload["block_length"] is None


def test_automatic_selector_uses_longer_block_for_persistent_golden_series():
    independent = np.random.default_rng(123).normal(size=240)
    persistent = []
    value = 0.0
    for innovation in independent:
        value = 0.85 * value + innovation
        persistent.append(value)
    iid_selection = select_stationary_bootstrap_block_length(independent)
    persistent_selection = select_stationary_bootstrap_block_length(persistent)
    assert iid_selection.status == "SELECTED"
    assert persistent_selection.status == "SELECTED"
    assert iid_selection.selected_block_length is not None
    assert persistent_selection.selected_block_length is not None
    assert iid_selection.raw_block_length == pytest.approx(1.5144375858535348)
    assert persistent_selection.raw_block_length == pytest.approx(9.585941217865432)
    assert (
        persistent_selection.selected_block_length > iid_selection.selected_block_length
    )


@pytest.mark.parametrize("challenger_class", ["learned_linear", "learned_tree"])
def test_learned_class_never_claims_fit_capacity_calibration(challenger_class):
    result = calibrate_scenario(
        _scenario(challenger_class=challenger_class),
        _hac(),
        seed=29,
        n_replications=5,
    )
    assert result.fit_capacity_mode == "FIT_CAPACITY_NOT_MODELED"
    assert any("exact-pipeline" in note for note in result.notes)


def test_study_rejects_duplicate_identity_and_formats_nonselections():
    scenario = _scenario()
    with pytest.raises(ValueError, match="scenario_id values must be unique"):
        run_calibration_study(
            scenarios=(scenario, scenario),
            methods=(_hac(),),
            n_replications=2,
        )
    study = run_calibration_study(
        scenarios=(scenario,),
        methods=(_hac(),),
        n_replications=2,
        seed=31,
    )
    text = format_calibration_report(study)
    assert "measurement only" in text.lower()
    assert "No session floor" in text
    assert study.policy_grade_authorized is False


def test_scenario_and_method_rng_streams_do_not_depend_on_execution_order():
    scenarios = (
        _scenario(scenario_id="a"),
        _scenario(scenario_id="b", true_effect=0.05),
    )
    methods = (_bootstrap(), _hac())
    first = run_calibration_study(
        scenarios=scenarios,
        methods=methods,
        n_replications=5,
        seed=37,
    )
    reversed_order = run_calibration_study(
        scenarios=tuple(reversed(scenarios)),
        methods=tuple(reversed(methods)),
        n_replications=5,
        seed=37,
    )
    first_by_key = {(r.scenario_id, r.method_id): r for r in first.results}
    second_by_key = {(r.scenario_id, r.method_id): r for r in reversed_order.results}
    assert first_by_key == second_by_key


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"n_sessions_total": True}, "exact int"),
        ({"holdout_sessions": 100}, "smaller"),
        ({"ar1": 1.0}, "<= 0.95"),
        ({"noise_sd_at_reference_width": 0.0}, ">= 1e-12"),
        ({"min_valid_names": 46}, "cannot exceed"),
        ({"name_missing_rate": 1.1}, "<= 1.0"),
        ({"search_width": 0}, ">= 1"),
    ],
)
def test_scenario_rejects_ambiguous_or_invalid_inputs(kwargs, match):
    with pytest.raises(ValueError, match=match):
        _scenario(**kwargs)


def test_method_requires_explicit_tuning_parameter():
    with pytest.raises(ValueError, match="block_length"):
        CalibrationMethod(
            method_id="bad",
            method_kind="stationary_bootstrap_percentile",
            n_resamples=20,
        )
    with pytest.raises(ValueError, match="hac_lag"):
        CalibrationMethod(
            method_id="bad",
            method_kind="newey_west_normal",
            n_resamples=20,
        )
    with pytest.raises(ValueError, match="selector id"):
        CalibrationMethod(
            method_id="bad-auto",
            method_kind="stationary_bootstrap_percentile_auto",
            n_resamples=20,
        )
