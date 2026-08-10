"""Exact current-fit-pipeline synthetic calibration for ML-OOS-02."""

from __future__ import annotations

import pytest

import ml_saham.challenge.policy_confirmation_fit_calibration as fit_cal
from ml_saham.challenge.policy_confirmation_calibration import CalibrationMethod
from ml_saham.challenge.policy_confirmation_fit_calibration import (
    FIT_CALIBRATION_CONTRACT_ID,
    FitCalibrationScenario,
    calibrate_fit_scenario,
    format_fit_calibration_report,
    run_fit_calibration_study,
)
from ml_saham.challenge.promote import POLICY_CONFIRMATION_CONTRACTS
from ml_saham.challenge.protocols import ACCUM_PATH_V1


def _scenario(**overrides) -> FitCalibrationScenario:
    values = dict(
        scenario_id="ridge-null",
        challenger_id="ridge_reweight",
        n_sessions_total=84,
        holdout_sessions=20,
        names_per_session=20,
        feature_ar1=0.4,
        outcome_noise_sd=0.5,
        heteroskedastic_strength=0.5,
    )
    values.update(overrides)
    return FitCalibrationScenario(**values)


def _hac() -> CalibrationMethod:
    return CalibrationMethod(
        method_id="nw2",
        method_kind="newey_west_normal",
        confidence_level=0.95,
        hac_lag=2,
        n_resamples=20,
    )


def test_ridge_fit_calibration_is_deterministic_and_uses_exact_geometry():
    kwargs = dict(
        scenario=_scenario(),
        method=_hac(),
        seed=41,
        n_replications=3,
    )
    first = calibrate_fit_scenario(**kwargs)
    second = calibrate_fit_scenario(**kwargs)
    assert first == second
    assert first.contract_id == FIT_CALIBRATION_CONTRACT_ID
    assert first.n_folds_geometry == 2
    assert first.mean_folds_scored == 2.0
    assert first.mean_oos_sessions_scored == 32.0
    assert first.fit_success_rate == 1.0
    assert first.policy_grade_authorized is False


def test_ridge_path_calls_shipped_fit_function_inside_each_fold(monkeypatch):
    calls = 0
    shipped = fit_cal.score_ridge_reweight

    def recording_score(*args, **kwargs):
        nonlocal calls
        calls += 1
        return shipped(*args, **kwargs)

    monkeypatch.setattr(fit_cal, "score_ridge_reweight", recording_score)
    result = calibrate_fit_scenario(
        _scenario(),
        _hac(),
        seed=43,
        n_replications=1,
    )
    assert result.status == "MEASURED"
    assert calls == result.n_folds_geometry


def test_rotated_signal_reports_power_not_false_superiority():
    result = calibrate_fit_scenario(
        _scenario(signal_rotation=0.8, n_sessions_total=120),
        _hac(),
        seed=61,
        n_replications=5,
    )
    assert result.mean_session_ic_delta is not None
    assert result.mean_session_ic_delta > 0.0
    assert result.directional_detection_rate is not None
    assert result.false_superiority_rate is None


@pytest.mark.parametrize("challenger_id", ["elastic_net_reweight", "lgbm_reweight"])
def test_champion_fit_paths_are_measured_or_dependency_blocked(challenger_id):
    result = calibrate_fit_scenario(
        _scenario(scenario_id=challenger_id, challenger_id=challenger_id),
        _hac(),
        seed=47,
        n_replications=1,
    )
    assert result.status in {"MEASURED", "BLOCKED_DEPENDENCY"}
    if result.status == "MEASURED":
        assert result.fit_success_rate == 1.0
        assert result.mean_session_ic_delta is not None
    else:
        assert result.fit_success_rate == 0.0
        assert result.errors


def test_study_stays_measurement_only_and_registry_empty():
    study = run_fit_calibration_study(
        scenarios=(_scenario(),),
        methods=(_hac(),),
        seed=53,
        n_replications=1,
    )
    assert study.policy_grade_authorized is False
    assert POLICY_CONFIRMATION_CONTRACTS == frozenset()
    assert ACCUM_PATH_V1.policy_confirmation_contract_id == ""
    text = format_fit_calibration_report(study)
    assert "measurement only" in text.lower()
    assert "No synthetic session count" in text


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"challenger_id": "unknown"}, "unsupported"),
        ({"n_sessions_total": True}, "exact int"),
        ({"holdout_sessions": 84}, "smaller"),
        ({"names_per_session": 2}, ">= 3"),
        ({"feature_ar1": 1.0}, "<= 0.95"),
        ({"outcome_noise_sd": 0.0}, ">= 1e-12"),
        ({"signal_rotation": 1.1}, "<= 1.0"),
    ],
)
def test_fit_scenario_rejects_invalid_inputs(kwargs, match):
    with pytest.raises(ValueError, match=match):
        _scenario(**kwargs)


def test_thin_fold_region_fails_without_fake_fit_result():
    result = calibrate_fit_scenario(
        _scenario(n_sessions_total=40, holdout_sessions=20),
        _hac(),
        seed=59,
        n_replications=1,
    )
    assert result.n_folds_geometry == 0
    assert result.status == "METHOD_NOT_MEASURABLE"
    assert result.fit_success_rate == 0.0
    assert "no folds formed" in result.errors
