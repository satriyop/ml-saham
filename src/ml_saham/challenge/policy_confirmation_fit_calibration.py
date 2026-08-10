"""Exact current-fit-pipeline synthetic calibration for ML-OOS-02.

Synthetic panels exercise the shipped ridge, elastic-net, and LightGBM
fit/predict functions inside ``accum_path_v1`` purged folds. The reference score
is the known data-generating ranking, so a lower confidence bound above zero is
a false superiority claim under this null.

This uses a local execution fixture, not a verified production snapshot. It is
measurement-only and cannot select floors or authorize promotion.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal, Sequence

import numpy as np

from ml_saham.challenge.champion import score_champion
from ml_saham.challenge.metrics import ic_safe, time_purged_folds
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.policy_confirmation_calibration import (
    CALIBRATION_EVIDENCE_GRADE,
    CalibrationMethod,
    candidate_interval,
    default_calibration_methods,
)
from ml_saham.challenge.protocols import ACCUM_PATH_V1
from ml_saham.challenge.scorers import score_production, score_ridge_reweight

FIT_CALIBRATION_CONTRACT_ID = "policy_confirmation_fit_calibration.synthetic.v1"
SUPPORTED_FIT_CHALLENGERS = frozenset(
    {"ridge_reweight", "elastic_net_reweight", "lgbm_reweight"}
)

FitChallenger = Literal[
    "ridge_reweight", "elastic_net_reweight", "lgbm_reweight"
]


def _require_exact_int(name: str, value: object, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise ValueError(
            f"{name} must be exact int, got {type(value).__name__}={value!r}"
        )
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _finite_float(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric, got {type(value).__name__}")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and out < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {out}")
    if maximum is not None and out > maximum:
        raise ValueError(f"{name} must be <= {maximum}, got {out}")
    return out


def _stable_part(value: str) -> int:
    return int.from_bytes(
        hashlib.sha256(value.encode("utf-8")).digest()[:4],
        "big",
        signed=False,
    )


@dataclass(frozen=True)
class FitCalibrationScenario:
    scenario_id: str
    challenger_id: FitChallenger
    n_sessions_total: int
    holdout_sessions: int = 20
    names_per_session: int = 45
    feature_ar1: float = 0.4
    outcome_noise_sd: float = 0.5
    heteroskedastic_strength: float = 0.5
    signal_rotation: float = 0.0

    def __post_init__(self) -> None:
        if type(self.scenario_id) is not str or not self.scenario_id:
            raise ValueError("scenario_id must be non-empty")
        if self.scenario_id != self.scenario_id.strip():
            raise ValueError("scenario_id must not have surrounding whitespace")
        if self.challenger_id not in SUPPORTED_FIT_CHALLENGERS:
            raise ValueError(f"unsupported challenger_id={self.challenger_id!r}")
        n = _require_exact_int("n_sessions_total", self.n_sessions_total, minimum=1)
        h = _require_exact_int("holdout_sessions", self.holdout_sessions)
        if h >= n:
            raise ValueError("holdout_sessions must be smaller than n_sessions_total")
        _require_exact_int("names_per_session", self.names_per_session, minimum=3)
        _finite_float("feature_ar1", self.feature_ar1, minimum=-0.95, maximum=0.95)
        _finite_float("outcome_noise_sd", self.outcome_noise_sd, minimum=1e-12)
        _finite_float(
            "heteroskedastic_strength", self.heteroskedastic_strength, minimum=0.0
        )
        _finite_float(
            "signal_rotation", self.signal_rotation, minimum=0.0, maximum=1.0
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FitCalibrationResult:
    contract_id: str
    evidence_grade: str
    scenario_id: str
    challenger_id: str
    method_id: str
    seed: int
    n_replications: int
    n_valid_replications: int
    n_folds_geometry: int
    mean_folds_scored: float | None
    mean_oos_sessions_scored: float | None
    fit_success_rate: float
    mean_session_ic_delta: float | None
    probability_mean_delta_positive: float | None
    false_superiority_rate: float | None
    directional_detection_rate: float | None
    mean_interval_width: float | None
    policy_grade_authorized: bool
    status: str
    errors: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FitCalibrationStudy:
    contract_id: str
    evidence_grade: str
    seed: int
    n_replications: int
    scenarios: tuple[FitCalibrationScenario, ...]
    methods: tuple[CalibrationMethod, ...]
    results: tuple[FitCalibrationResult, ...]
    explicit_non_selections: tuple[str, ...]
    policy_grade_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "evidence_grade": self.evidence_grade,
            "seed": self.seed,
            "n_replications": self.n_replications,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "methods": [method.to_dict() for method in self.methods],
            "results": [result.to_dict() for result in self.results],
            "explicit_non_selections": list(self.explicit_non_selections),
            "policy_grade_authorized": self.policy_grade_authorized,
        }


def _synthetic_policy_and_weights():
    fixture = load_policy("screener.accum.score_weights")
    keys = tuple(fixture.feature_keys())
    raw_weights = np.asarray([fixture.weight_map()[key] for key in keys], dtype=float)
    norm = float(np.linalg.norm(raw_weights))
    if not keys or norm <= 0.0:
        raise RuntimeError("synthetic reference policy fixture has no usable weights")
    policy = replace(
        fixture,
        production_snapshot_id="synthetic-reference-not-production",
        production_snapshot_digest="synthetic-reference-not-production",
        observation_compatibility_id="synthetic-no-cohort",
    )
    return policy, keys, raw_weights / norm


def _synthetic_panel(
    scenario: FitCalibrationScenario,
    *,
    seed: int,
) -> list[PanelRow]:
    policy, keys, reference_beta = _synthetic_policy_and_weights()
    del policy
    rotated_beta = reference_beta[::-1].copy()
    outcome_beta = (
        (1.0 - scenario.signal_rotation) * reference_beta
        + scenario.signal_rotation * rotated_beta
    )
    outcome_beta /= float(np.linalg.norm(outcome_beta))
    rng = np.random.default_rng(
        np.random.SeedSequence([seed, _stable_part(scenario.scenario_id)])
    )
    n_sessions = scenario.n_sessions_total
    n_names = scenario.names_per_session
    n_features = len(keys)
    previous = np.zeros((n_names, n_features), dtype=float)
    innovation_scale = math.sqrt(1.0 - scenario.feature_ar1**2)
    rows: list[PanelRow] = []
    for session_i in range(n_sessions):
        features = (
            scenario.feature_ar1 * previous
            + innovation_scale * rng.normal(size=(n_names, n_features))
        )
        periodic = 0.5 + 0.5 * math.sin(2.0 * math.pi * (session_i + 1) / 20.0)
        noise_scale = scenario.outcome_noise_sd * (
            1.0 + scenario.heteroskedastic_strength * periodic
        )
        reference_score = features @ reference_beta
        outcomes = features @ outcome_beta + noise_scale * rng.normal(size=n_names)
        session = f"S{session_i:04d}"
        for name_i in range(n_names):
            components = {
                key: float(features[name_i, key_i])
                for key_i, key in enumerate(keys)
            }
            components["production_observed_score"] = float(
                reference_score[name_i]
            )
            rows.append(
                PanelRow(
                    ticker=f"T{name_i:04d}",
                    date=session,
                    components=components,
                    excess={10: float(outcomes[name_i])},
                )
            )
        previous = features
    return rows


def _challenger_scores(
    scenario: FitCalibrationScenario,
    train: Sequence[PanelRow],
    test: Sequence[PanelRow],
):
    policy, _keys, _beta = _synthetic_policy_and_weights()
    if scenario.challenger_id == "ridge_reweight":
        scores, _coefs = score_ridge_reweight(
            train,
            test,
            policy,
            primary_horizon=ACCUM_PATH_V1.primary_horizon,
        )
        return scores, None
    scores, _meta, error = score_champion(
        scenario.challenger_id,
        train,
        test,
        policy,
        primary_horizon=ACCUM_PATH_V1.primary_horizon,
    )
    return scores, error


def _session_ic_deltas(
    rows: Sequence[PanelRow],
    indices: Sequence[int],
    baseline_scores: Sequence[float],
    challenger_scores: Sequence[float],
) -> list[float]:
    by_session: dict[str, list[int]] = {}
    for local_i, row_i in enumerate(indices):
        by_session.setdefault(rows[row_i].date, []).append(local_i)
    deltas: list[float] = []
    for session in sorted(by_session):
        local = by_session[session]
        outcomes = [rows[indices[i]].excess[10] for i in local]
        baseline = ic_safe([baseline_scores[i] for i in local], outcomes)
        challenger = ic_safe([challenger_scores[i] for i in local], outcomes)
        if baseline is not None and challenger is not None:
            deltas.append(challenger - baseline)
    return deltas


def _one_replication(
    scenario: FitCalibrationScenario,
    *,
    seed: int,
) -> tuple[list[float] | None, int, str | None]:
    rows = _synthetic_panel(scenario, seed=seed)
    fold_end = scenario.n_sessions_total - scenario.holdout_sessions
    fold_rows = [row for row in rows if int(row.date[1:]) < fold_end]
    folds = time_purged_folds(fold_rows, ACCUM_PATH_V1)
    policy, _keys, _beta = _synthetic_policy_and_weights()
    all_deltas: list[float] = []
    folds_scored = 0
    for fold in folds:
        train = [fold_rows[i] for i in fold.train_idx]
        test = [fold_rows[i] for i in fold.test_idx]
        challenger, error = _challenger_scores(scenario, train, test)
        if error is not None or challenger is None:
            return None, folds_scored, error or "challenger returned no scores"
        baseline = score_production(test, policy)
        deltas = _session_ic_deltas(
            fold_rows,
            fold.test_idx,
            baseline,
            challenger,
        )
        if not deltas:
            return None, folds_scored, "no defined session IC deltas"
        all_deltas.extend(deltas)
        folds_scored += 1
    if not folds:
        return None, 0, "no folds formed"
    return all_deltas, folds_scored, None


def calibrate_fit_scenario(
    scenario: FitCalibrationScenario,
    method: CalibrationMethod,
    *,
    seed: int,
    n_replications: int,
) -> FitCalibrationResult:
    seed_i = _require_exact_int("seed", seed)
    reps = _require_exact_int("n_replications", n_replications, minimum=1)
    geometry_rows = _synthetic_panel(scenario, seed=seed_i)
    fold_end = scenario.n_sessions_total - scenario.holdout_sessions
    fold_rows = [row for row in geometry_rows if int(row.date[1:]) < fold_end]
    n_folds_geometry = len(time_purged_folds(fold_rows, ACCUM_PATH_V1))

    deltas_by_rep: list[list[float]] = []
    folds_scored: list[int] = []
    false_superiority: list[bool] = []
    directional_detection: list[bool] = []
    interval_widths: list[float] = []
    errors: list[str] = []
    for replication in range(reps):
        replication_seed = int(
            np.random.SeedSequence(
                [seed_i, _stable_part(scenario.scenario_id), replication]
            ).generate_state(1)[0]
        )
        deltas, scored, error = _one_replication(
            scenario,
            seed=replication_seed,
        )
        if error is not None or deltas is None:
            errors.append(error or "unknown fit failure")
            continue
        ci_seed = int(
            np.random.SeedSequence(
                [replication_seed, _stable_part(method.method_id)]
            ).generate_state(1)[0]
        )
        ci = candidate_interval(deltas, method, seed=ci_seed)
        if ci is None:
            errors.append("candidate interval not measurable")
            continue
        lower, upper = ci
        deltas_by_rep.append(deltas)
        folds_scored.append(scored)
        if scenario.signal_rotation == 0.0:
            false_superiority.append(lower > 0.0)
        else:
            directional_detection.append(lower > 0.0)
        interval_widths.append(upper - lower)

    valid = len(deltas_by_rep)
    all_rep_means = [statistics.fmean(values) for values in deltas_by_rep]
    unique_errors = tuple(sorted(set(errors)))
    if valid == reps:
        status = "MEASURED"
    elif valid == 0 and any("requires" in error for error in unique_errors):
        status = "BLOCKED_DEPENDENCY"
    elif valid == 0:
        status = "METHOD_NOT_MEASURABLE"
    else:
        status = "PARTIAL_FIT_FAILURES"
    return FitCalibrationResult(
        contract_id=FIT_CALIBRATION_CONTRACT_ID,
        evidence_grade=CALIBRATION_EVIDENCE_GRADE,
        scenario_id=scenario.scenario_id,
        challenger_id=scenario.challenger_id,
        method_id=method.method_id,
        seed=seed_i,
        n_replications=reps,
        n_valid_replications=valid,
        n_folds_geometry=n_folds_geometry,
        mean_folds_scored=statistics.fmean(folds_scored) if folds_scored else None,
        mean_oos_sessions_scored=(
            statistics.fmean(len(values) for values in deltas_by_rep)
            if deltas_by_rep
            else None
        ),
        fit_success_rate=valid / reps,
        mean_session_ic_delta=(
            statistics.fmean(all_rep_means) if all_rep_means else None
        ),
        probability_mean_delta_positive=(
            statistics.fmean(value > 0.0 for value in all_rep_means)
            if all_rep_means
            else None
        ),
        false_superiority_rate=(
            statistics.fmean(false_superiority) if false_superiority else None
        ),
        directional_detection_rate=(
            statistics.fmean(directional_detection)
            if directional_detection
            else None
        ),
        mean_interval_width=(
            statistics.fmean(interval_widths) if interval_widths else None
        ),
        policy_grade_authorized=False,
        status=status,
        errors=unique_errors,
        notes=(
            "synthetic reference score is the known outcome-ranking signal",
            "local execution fixture is not a verified production snapshot",
            "shipped fixed fit/predict parameters are exercised inside each outer fold",
            "no hyperparameter search or nested tuning is simulated",
            (
                "lower interval bound above zero is a false superiority claim under the reference null"
                if scenario.signal_rotation == 0.0
                else "lower interval bound above zero is directional detection under the rotated alternative"
            ),
        ),
    )


def default_fit_calibration_scenarios(
    *, session_counts: Sequence[int] = (84, 120, 180), holdout_sessions: int = 20
) -> tuple[FitCalibrationScenario, ...]:
    scenarios: list[FitCalibrationScenario] = []
    for n_sessions in session_counts:
        for challenger_id in sorted(SUPPORTED_FIT_CHALLENGERS):
            scenarios.extend(
                [
                    FitCalibrationScenario(
                        scenario_id=f"reference_null.{challenger_id}.n{n_sessions}.h{holdout_sessions}",
                        challenger_id=challenger_id,
                        n_sessions_total=n_sessions,
                        holdout_sessions=holdout_sessions,
                    ),
                    FitCalibrationScenario(
                        scenario_id=f"rotated_alt.{challenger_id}.n{n_sessions}.h{holdout_sessions}",
                        challenger_id=challenger_id,
                        n_sessions_total=n_sessions,
                        holdout_sessions=holdout_sessions,
                        signal_rotation=0.60,
                    ),
                ]
            )
    return tuple(scenarios)


def run_fit_calibration_study(
    *,
    scenarios: Sequence[FitCalibrationScenario] | None = None,
    methods: Sequence[CalibrationMethod] | None = None,
    seed: int = 20260810,
    n_replications: int = 30,
) -> FitCalibrationStudy:
    seed_i = _require_exact_int("seed", seed)
    reps = _require_exact_int("n_replications", n_replications, minimum=1)
    scenario_items = tuple(scenarios or default_fit_calibration_scenarios())
    method_items = tuple(methods or default_calibration_methods(n_resamples=100))
    if not scenario_items or not method_items:
        raise ValueError("scenarios and methods must be non-empty")
    if len({item.scenario_id for item in scenario_items}) != len(scenario_items):
        raise ValueError("scenario_id values must be unique")
    if len({item.method_id for item in method_items}) != len(method_items):
        raise ValueError("method_id values must be unique")
    results = tuple(
        calibrate_fit_scenario(
            scenario,
            method,
            seed=seed_i,
            n_replications=reps,
        )
        for scenario in scenario_items
        for method in method_items
    )
    return FitCalibrationStudy(
        contract_id=FIT_CALIBRATION_CONTRACT_ID,
        evidence_grade=CALIBRATION_EVIDENCE_GRADE,
        seed=seed_i,
        n_replications=reps,
        scenarios=scenario_items,
        methods=method_items,
        results=results,
        explicit_non_selections=(
            "No synthetic session count is selected as a learned-model floor.",
            "No candidate interval method or tuning value is adopted.",
            "The local fixture is not production identity or promotion evidence.",
            "Current fixed model parameters are measured; future tuning still requires nested calibration.",
            "No confirmation contract is registered and Task 06 remains blocked.",
        ),
        policy_grade_authorized=False,
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def format_fit_calibration_report(study: FitCalibrationStudy) -> str:
    lines = [
        "ML-OOS-02 exact fit-pipeline synthetic calibration (measurement only)",
        f"contract_id={study.contract_id}",
        f"seed={study.seed} replications={study.n_replications}",
        "policy_grade_authorized=False",
        "",
        "scenario | method | fit | folds | oos_sessions | mean_delta | P(delta>0) | FP | power | status",
    ]
    for result in study.results:
        lines.append(
            " | ".join(
                [
                    result.scenario_id,
                    result.method_id,
                    _fmt(result.fit_success_rate),
                    _fmt(result.mean_folds_scored),
                    _fmt(result.mean_oos_sessions_scored),
                    _fmt(result.mean_session_ic_delta),
                    _fmt(result.probability_mean_delta_positive),
                    _fmt(result.false_superiority_rate),
                    _fmt(result.directional_detection_rate),
                    result.status,
                ]
            )
        )
    lines.extend(["", "Explicit non-selections:"])
    lines.extend(f"- {item}" for item in study.explicit_non_selections)
    return "\n".join(lines)
