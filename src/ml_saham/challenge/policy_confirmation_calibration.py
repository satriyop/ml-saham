"""Outcome-independent calibration harness for ML-OOS-02 design research.

This module simulates a synthetic *session-level estimand* under the shipped
fold geometry. It measures candidate interval operating characteristics; it
does not inspect live outcomes, select policy floors, model learned-fit
capacity, register a confirmation contract, or authorize promotion.

Semantic classification: PROTOCOL_CONTRACT design research (non-authoritative).
"""

from __future__ import annotations

import hashlib
import math
import statistics
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any, Literal, Sequence

import numpy as np

from ml_saham.challenge.fold_geometry_sim import simulate_session_folds

CALIBRATION_CONTRACT_ID = "policy_confirmation_calibration.synthetic.v4"
CALIBRATION_EVIDENCE_GRADE = "MEASUREMENT_ONLY"
AUTO_BLOCK_SELECTOR_ID = "politis_white_patton.stationary_mean.v1"

ChallengerClass = Literal["fixed", "learned_linear", "learned_tree"]
MethodKind = Literal[
    "stationary_bootstrap_percentile",
    "stationary_bootstrap_percentile_auto",
    "newey_west_normal",
]


def _require_exact_int(name: str, value: object, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise ValueError(
            f"{name} must be exact int, got {type(value).__name__}={value!r}"
        )
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _require_finite_float(
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
        raise ValueError(f"{name} must be finite, got {value!r}")
    if minimum is not None and out < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {out}")
    if maximum is not None and out > maximum:
        raise ValueError(f"{name} must be <= {maximum}, got {out}")
    return out


def _require_nonempty_id(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(
            f"{name} must be a non-empty string without surrounding whitespace"
        )
    return value


def _stable_seed_part(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def _rng(seed: int, *parts: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([seed, *parts]))


@dataclass(frozen=True)
class CalibrationScenario:
    """One explicit synthetic data-generating process.

    ``true_effect`` and ``noise_sd_at_reference_width`` are synthetic estimand
    units. They are deliberately not inferred from the maintainer cohort.
    """

    scenario_id: str
    challenger_class: ChallengerClass
    n_sessions_total: int
    holdout_sessions: int
    true_effect: float
    ar1: float
    noise_sd_at_reference_width: float
    heteroskedastic_strength: float = 0.0
    regime_shift: float = 0.0
    regime_start_fraction: float = 0.7
    names_per_session: int = 45
    name_missing_rate: float = 0.0
    min_valid_names: int = 20
    search_width: int = 1
    search_correlation: float = 0.5

    def __post_init__(self) -> None:
        _require_nonempty_id("scenario_id", self.scenario_id)
        if self.challenger_class not in {"fixed", "learned_linear", "learned_tree"}:
            raise ValueError(
                "challenger_class must be fixed, learned_linear, or learned_tree"
            )
        n = _require_exact_int("n_sessions_total", self.n_sessions_total, minimum=1)
        h = _require_exact_int("holdout_sessions", self.holdout_sessions)
        if h >= n:
            raise ValueError("holdout_sessions must be smaller than n_sessions_total")
        _require_finite_float("true_effect", self.true_effect)
        _require_finite_float("ar1", self.ar1, minimum=-0.95, maximum=0.95)
        _require_finite_float(
            "noise_sd_at_reference_width",
            self.noise_sd_at_reference_width,
            minimum=1e-12,
        )
        _require_finite_float(
            "heteroskedastic_strength", self.heteroskedastic_strength, minimum=0.0
        )
        _require_finite_float("regime_shift", self.regime_shift)
        _require_finite_float(
            "regime_start_fraction",
            self.regime_start_fraction,
            minimum=0.0,
            maximum=1.0,
        )
        names = _require_exact_int(
            "names_per_session", self.names_per_session, minimum=1
        )
        min_names = _require_exact_int(
            "min_valid_names", self.min_valid_names, minimum=2
        )
        if min_names > names:
            raise ValueError("min_valid_names cannot exceed names_per_session")
        _require_finite_float(
            "name_missing_rate", self.name_missing_rate, minimum=0.0, maximum=1.0
        )
        _require_exact_int("search_width", self.search_width, minimum=1)
        _require_finite_float(
            "search_correlation",
            self.search_correlation,
            minimum=0.0,
            maximum=0.999999,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationMethod:
    method_id: str
    method_kind: MethodKind
    confidence_level: float = 0.95
    block_length: int | None = None
    hac_lag: int | None = None
    n_resamples: int = 200
    block_length_selector_id: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_id("method_id", self.method_id)
        if self.method_kind not in {
            "stationary_bootstrap_percentile",
            "stationary_bootstrap_percentile_auto",
            "newey_west_normal",
        }:
            raise ValueError(f"unsupported method_kind={self.method_kind!r}")
        _require_finite_float(
            "confidence_level", self.confidence_level, minimum=0.5, maximum=0.999999
        )
        _require_exact_int("n_resamples", self.n_resamples, minimum=20)
        if self.method_kind == "stationary_bootstrap_percentile":
            if self.block_length is None:
                raise ValueError("stationary bootstrap requires explicit block_length")
            _require_exact_int("block_length", self.block_length, minimum=1)
            if self.hac_lag is not None:
                raise ValueError("stationary bootstrap must not set hac_lag")
            if self.block_length_selector_id is not None:
                raise ValueError("explicit stationary bootstrap must not set selector")
        elif self.method_kind == "stationary_bootstrap_percentile_auto":
            if self.block_length is not None or self.hac_lag is not None:
                raise ValueError(
                    "automatic stationary bootstrap must not set block or lag"
                )
            if self.block_length_selector_id != AUTO_BLOCK_SELECTOR_ID:
                raise ValueError(
                    "automatic stationary bootstrap requires the supported selector id"
                )
        else:
            if self.hac_lag is None:
                raise ValueError("Newey-West requires explicit hac_lag")
            _require_exact_int("hac_lag", self.hac_lag)
            if self.block_length is not None:
                raise ValueError("Newey-West must not set block_length")
            if self.block_length_selector_id is not None:
                raise ValueError("Newey-West must not set block selector")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.block_length_selector_id is None:
            payload.pop("block_length_selector_id")
        return payload


@dataclass(frozen=True)
class BlockLengthSelection:
    selector_id: str
    n_input_sessions: int
    correlation_run_length: int
    maximum_correlation_lag: int
    maximum_block_length: int
    correlation_band: float | None
    first_insignificant_lag: int | None
    flat_top_lag: int | None
    raw_block_length: float | None
    selected_block_length: int | None
    status: str
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalendarSeriesAssessment:
    n_calendar_sessions: int
    n_observed_sessions: int
    n_missing_sessions: int
    n_invalid_sessions: int
    longest_missing_run: int
    observed_fraction: float | None
    status: str
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_calendar_estimand_series(
    values: Sequence[float | None],
) -> CalendarSeriesAssessment:
    """Classify a fixed calendar without deleting or imputing positions."""
    n = len(values)
    observed = 0
    missing = 0
    invalid = 0
    missing_run = 0
    longest_missing_run = 0
    for value in values:
        if value is None:
            missing += 1
            missing_run += 1
            longest_missing_run = max(longest_missing_run, missing_run)
            continue
        missing_run = 0
        if isinstance(value, bool) or not isinstance(value, Real):
            invalid += 1
            continue
        if not math.isfinite(float(value)):
            invalid += 1
            continue
        observed += 1

    observed_fraction = observed / n if n else None
    if invalid:
        status = "INVALID_NONFINITE_ESTIMAND"
        reason = "calendar estimands must be finite numeric values or explicit None"
    elif missing:
        status = "MISSING_CALENDAR_SESSION_UNSUPPORTED"
        reason = "current interval candidates do not delete or impute calendar gaps"
    elif n < 2:
        status = "INSUFFICIENT_CALENDAR_SESSIONS"
        reason = "interval candidates require at least two calendar sessions"
    else:
        status = "COMPLETE"
        reason = None
    return CalendarSeriesAssessment(
        n_calendar_sessions=n,
        n_observed_sessions=observed,
        n_missing_sessions=missing,
        n_invalid_sessions=invalid,
        longest_missing_run=longest_missing_run,
        observed_fraction=observed_fraction,
        status=status,
        reason=reason,
    )


@dataclass(frozen=True)
class CalibrationResult:
    contract_id: str
    evidence_grade: str
    scenario_id: str
    challenger_class: ChallengerClass
    method_id: str
    method_kind: MethodKind
    seed: int
    n_replications: int
    n_valid_replications: int
    n_folds_formed: int
    n_eval_sessions_geometry: int
    mean_observed_sessions: float | None
    mean_observed_fraction: float | None
    true_target_mean: float | None
    mean_selected_estimate: float | None
    mean_selection_bias: float | None
    coverage_rate: float | None
    false_superiority_rate: float | None
    false_positive_rate: float | None
    directional_detection_rate: float | None
    mean_interval_width: float | None
    mean_selected_block_length: float | None
    min_selected_block_length: int | None
    max_selected_block_length: int | None
    method_failure_counts: tuple[tuple[str, int], ...]
    fit_capacity_mode: str
    policy_grade_authorized: bool
    status: str
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationStudy:
    contract_id: str
    evidence_grade: str
    seed: int
    n_replications: int
    n_folds: int
    embargo_sessions: int
    scenarios: tuple[CalibrationScenario, ...]
    methods: tuple[CalibrationMethod, ...]
    results: tuple[CalibrationResult, ...]
    explicit_non_selections: tuple[str, ...]
    policy_grade_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "evidence_grade": self.evidence_grade,
            "seed": self.seed,
            "n_replications": self.n_replications,
            "n_folds": self.n_folds,
            "embargo_sessions": self.embargo_sessions,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "methods": [m.to_dict() for m in self.methods],
            "results": [r.to_dict() for r in self.results],
            "explicit_non_selections": list(self.explicit_non_selections),
            "policy_grade_authorized": self.policy_grade_authorized,
        }


def _evaluation_indices(
    scenario: CalibrationScenario,
    *,
    n_folds: int,
    embargo_sessions: int,
) -> tuple[tuple[int, ...], int]:
    fold_region = scenario.n_sessions_total - scenario.holdout_sessions
    folds = simulate_session_folds(
        fold_region,
        n_folds=n_folds,
        embargo_sessions=embargo_sessions,
    )
    indices = sorted(
        {
            session_i
            for fold in folds
            for session_i in range(fold.test_start_i, fold.test_end_i)
        }
    )
    return tuple(indices), len(folds)


def _scenario_means(scenario: CalibrationScenario) -> np.ndarray:
    n = scenario.n_sessions_total
    means = np.full(n, scenario.true_effect, dtype=float)
    regime_start = int(math.floor(n * scenario.regime_start_fraction))
    if scenario.regime_shift != 0.0 and regime_start < n:
        means[regime_start:] += scenario.regime_shift
    return means


def _simulate_session_estimands(
    scenario: CalibrationScenario,
    *,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return session x search-member estimands, means, and valid-name counts."""
    n = scenario.n_sessions_total
    width = scenario.search_width
    means = _scenario_means(scenario)
    valid_names = rng.binomial(
        scenario.names_per_session,
        1.0 - scenario.name_missing_rate,
        size=n,
    )
    out = np.empty((n, width), dtype=float)
    common_weight = math.sqrt(scenario.search_correlation)
    idio_weight = math.sqrt(1.0 - scenario.search_correlation)
    reference_width = 45.0

    previous = np.full(width, means[0], dtype=float)
    previous_mean = means[0]
    for session_i in range(n):
        common = float(rng.normal())
        idio = rng.normal(size=width)
        innovation = common_weight * common + idio_weight * idio
        periodic = 0.5 + 0.5 * math.sin(2.0 * math.pi * (session_i + 1) / 20.0)
        hetero_scale = 1.0 + scenario.heteroskedastic_strength * periodic
        width_scale = math.sqrt(reference_width / max(int(valid_names[session_i]), 1))
        noise_scale = scenario.noise_sd_at_reference_width * hetero_scale * width_scale
        current = (
            means[session_i]
            + scenario.ar1 * (previous - previous_mean)
            + noise_scale * innovation
        )
        out[session_i, :] = current
        previous = current
        previous_mean = means[session_i]

    out[valid_names < scenario.min_valid_names, :] = np.nan
    return out, means, valid_names


def select_stationary_bootstrap_block_length(
    values: Sequence[float],
) -> BlockLengthSelection:
    """Select a stationary-bootstrap mean block using the corrected PW rule."""
    array = np.asarray(tuple(values), dtype=float)
    n = len(array)
    kn = max(5, int(math.ceil(math.log10(n)))) if n > 0 else 5
    m_max = min(n - 1, int(math.ceil(math.sqrt(n))) + kn) if n > 0 else 0
    b_max = int(math.ceil(min(3.0 * math.sqrt(n), n / 3.0))) if n > 0 else 0

    def failed(status: str, reason: str) -> BlockLengthSelection:
        return BlockLengthSelection(
            selector_id=AUTO_BLOCK_SELECTOR_ID,
            n_input_sessions=n,
            correlation_run_length=kn,
            maximum_correlation_lag=m_max,
            maximum_block_length=b_max,
            correlation_band=None,
            first_insignificant_lag=None,
            flat_top_lag=None,
            raw_block_length=None,
            selected_block_length=None,
            status=status,
            reason=reason,
        )

    if n < 10:
        return failed("INSUFFICIENT_SESSIONS", "selector requires at least 10 sessions")
    if not np.isfinite(array).all():
        return failed(
            "NONFINITE_CALENDAR_SERIES",
            "selector does not drop missing or non-finite calendar positions",
        )
    centered = array - float(np.mean(array))
    gamma0 = float(np.dot(centered, centered) / n)
    if not math.isfinite(gamma0) or gamma0 <= 1e-15:
        return failed("DEGENERATE_VARIANCE", "selector requires positive variance")

    correlation_band = 2.0 * math.sqrt(math.log10(n) / n)
    autocovariances = np.zeros(m_max + 1, dtype=float)
    absolute_correlations = np.full(m_max + 1, float("inf"), dtype=float)
    first_insignificant: int | None = None
    for lag in range(m_max + 1):
        left = centered[lag:]
        right = centered[: n - lag]
        cross = float(np.dot(left, right))
        autocovariances[lag] = cross / n
        denominator = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
        if denominator > 1e-15:
            absolute_correlations[lag] = abs(cross) / denominator
        if lag >= kn and first_insignificant is None:
            start = lag - kn
            if bool(np.all(absolute_correlations[start:lag] < correlation_band)):
                first_insignificant = start

    flat_top_lag = (
        min(2 * max(first_insignificant, 1), m_max)
        if first_insignificant is not None
        else m_max
    )
    long_run_variance = autocovariances[0]
    g = 0.0
    for lag in range(1, flat_top_lag + 1):
        ratio = lag / flat_top_lag
        weight = 1.0 if ratio <= 0.5 else 2.0 * (1.0 - ratio)
        long_run_variance += 2.0 * weight * autocovariances[lag]
        g += 2.0 * weight * lag * autocovariances[lag]
    corrected_variance_constant = 2.0 * long_run_variance**2
    if (
        not math.isfinite(corrected_variance_constant)
        or corrected_variance_constant <= 1e-15
    ):
        return failed(
            "DEGENERATE_LONG_RUN_VARIANCE",
            "corrected stationary-bootstrap variance constant is not usable",
        )
    raw = float(((2.0 * g * g / corrected_variance_constant) * n) ** (1.0 / 3.0))
    if not math.isfinite(raw) or raw < 0.0:
        return failed("INVALID_BLOCK_LENGTH", "plug-in block length is not finite")
    selected = min(max(1, int(math.ceil(raw))), b_max)
    return BlockLengthSelection(
        selector_id=AUTO_BLOCK_SELECTOR_ID,
        n_input_sessions=n,
        correlation_run_length=kn,
        maximum_correlation_lag=m_max,
        maximum_block_length=b_max,
        correlation_band=correlation_band,
        first_insignificant_lag=first_insignificant,
        flat_top_lag=flat_top_lag,
        raw_block_length=raw,
        selected_block_length=selected,
        status="SELECTED",
        reason=None,
    )


def _stationary_bootstrap_interval(
    values: np.ndarray,
    method: CalibrationMethod,
    *,
    rng: np.random.Generator,
) -> tuple[tuple[float, float] | None, int | None, str | None]:
    n = len(values)
    if method.method_kind == "stationary_bootstrap_percentile_auto":
        selection = select_stationary_bootstrap_block_length(values)
        block_length = selection.selected_block_length
        selection_failure = None if selection.status == "SELECTED" else selection.status
    else:
        block_length = method.block_length
        selection_failure = None
    if block_length is None:
        return None, None, selection_failure
    restart_probability = min(1.0, 1.0 / float(block_length))
    means: list[float] = []
    for _ in range(method.n_resamples):
        indices = np.empty(n, dtype=int)
        indices[0] = int(rng.integers(0, n))
        for i in range(1, n):
            if float(rng.random()) < restart_probability:
                indices[i] = int(rng.integers(0, n))
            else:
                indices[i] = (indices[i - 1] + 1) % n
        means.append(float(np.mean(values[indices])))
    if len(means) < max(10, method.n_resamples // 2):
        return None, block_length, selection_failure
    alpha = 1.0 - method.confidence_level
    lower, upper = np.quantile(means, [alpha / 2.0, 1.0 - alpha / 2.0])
    return (float(lower), float(upper)), block_length, selection_failure


def _newey_west_interval(
    values: np.ndarray,
    method: CalibrationMethod,
) -> tuple[float, float] | None:
    n = len(values)
    if method.hac_lag is None:
        return None
    mean = float(np.mean(values))
    centered = values - mean

    def gamma(lag: int) -> float:
        if lag == 0:
            return float(np.dot(centered, centered) / n)
        left = centered[lag:]
        right = centered[:-lag]
        return float(np.dot(left, right) / len(left))

    gamma0 = gamma(0)
    max_lag = min(method.hac_lag, len(values) - 1)
    long_run_variance = gamma0
    for lag in range(1, max_lag + 1):
        autocovariance = gamma(lag)
        weight = 1.0 - lag / float(max_lag + 1)
        long_run_variance += 2.0 * weight * autocovariance
    if long_run_variance < -1e-12 or not math.isfinite(long_run_variance):
        return None
    standard_error = math.sqrt(max(0.0, long_run_variance) / n)
    z = statistics.NormalDist().inv_cdf(0.5 + method.confidence_level / 2.0)
    return mean - z * standard_error, mean + z * standard_error


def _interval(
    values: Sequence[float | None],
    method: CalibrationMethod,
    *,
    rng: np.random.Generator,
) -> tuple[float, float] | None:
    interval, _block_length, _failure, _assessment = _interval_with_block_length(
        values, method, rng=rng
    )
    return interval


def _interval_with_block_length(
    values: Sequence[float | None],
    method: CalibrationMethod,
    *,
    rng: np.random.Generator,
) -> tuple[
    tuple[float, float] | None,
    int | None,
    str | None,
    CalendarSeriesAssessment,
]:
    assessment = assess_calendar_estimand_series(values)
    if assessment.status != "COMPLETE":
        return None, None, assessment.status, assessment
    array = np.asarray(values, dtype=float)
    if method.method_kind in {
        "stationary_bootstrap_percentile",
        "stationary_bootstrap_percentile_auto",
    }:
        interval, block_length, failure = _stationary_bootstrap_interval(
            array, method, rng=rng
        )
        return interval, block_length, failure, assessment
    return _newey_west_interval(array, method), None, None, assessment


def candidate_interval(
    values: Sequence[float | None],
    method: CalibrationMethod,
    *,
    seed: int,
) -> tuple[float, float] | None:
    """Apply one explicit candidate interval to a session series.

    Public for other synthetic calibration slices. This remains measurement
    machinery and does not imply that the method or tuning value is adopted.
    """
    seed_i = _require_exact_int("seed", seed)
    return _interval(
        tuple(values),
        method,
        rng=_rng(seed_i, _stable_seed_part(method.method_id)),
    )


def calibrate_scenario(
    scenario: CalibrationScenario,
    method: CalibrationMethod,
    *,
    seed: int,
    n_replications: int,
    n_folds: int = 3,
    embargo_sessions: int = 20,
) -> CalibrationResult:
    """Estimate interval operating characteristics for one synthetic scenario."""
    seed_i = _require_exact_int("seed", seed)
    reps = _require_exact_int("n_replications", n_replications, minimum=1)
    folds_i = _require_exact_int("n_folds", n_folds, minimum=1)
    embargo_i = _require_exact_int("embargo_sessions", embargo_sessions)
    eval_indices, folds_formed = _evaluation_indices(
        scenario,
        n_folds=folds_i,
        embargo_sessions=embargo_i,
    )
    fit_mode = (
        "NOT_APPLICABLE_FIXED"
        if scenario.challenger_class == "fixed"
        else "FIT_CAPACITY_NOT_MODELED"
    )
    common_notes = [
        "synthetic session-estimand calibration; no live outcomes",
        "candidate interval method only; no policy threshold selected",
        "best-of-search selection is intentionally unadjusted",
        "missing sessions retain calendar positions; HAC uses finite lag pairs",
    ]
    if fit_mode == "FIT_CAPACITY_NOT_MODELED":
        common_notes.append(
            "learned-fit capacity and nested tuning require an exact-pipeline simulation"
        )
    if folds_formed == 0 or not eval_indices:
        return CalibrationResult(
            contract_id=CALIBRATION_CONTRACT_ID,
            evidence_grade=CALIBRATION_EVIDENCE_GRADE,
            scenario_id=scenario.scenario_id,
            challenger_class=scenario.challenger_class,
            method_id=method.method_id,
            method_kind=method.method_kind,
            seed=seed_i,
            n_replications=reps,
            n_valid_replications=0,
            n_folds_formed=folds_formed,
            n_eval_sessions_geometry=len(eval_indices),
            mean_observed_sessions=None,
            mean_observed_fraction=None,
            true_target_mean=None,
            mean_selected_estimate=None,
            mean_selection_bias=None,
            coverage_rate=None,
            false_superiority_rate=None,
            false_positive_rate=None,
            directional_detection_rate=None,
            mean_interval_width=None,
            mean_selected_block_length=None,
            min_selected_block_length=None,
            max_selected_block_length=None,
            method_failure_counts=(),
            fit_capacity_mode=fit_mode,
            policy_grade_authorized=False,
            status="NOT_READY_GEOMETRY",
            notes=tuple(common_notes),
        )

    scenario_part = _stable_seed_part(scenario.scenario_id)
    method_part = _stable_seed_part(method.method_id)
    eval_array = np.asarray(eval_indices, dtype=int)
    cover: list[bool] = []
    false_positive: list[bool] = []
    false_superiority: list[bool] = []
    directional: list[bool] = []
    widths: list[float] = []
    selected_block_lengths: list[int] = []
    method_failures: dict[str, int] = {}
    observed_counts: list[int] = []
    estimates: list[float] = []
    targets: list[float] = []

    for replication in range(reps):
        data_rng = _rng(seed_i, scenario_part, replication)
        values, means, _valid_names = _simulate_session_estimands(
            scenario,
            rng=data_rng,
        )
        eval_values = values[eval_array, :]
        candidate_means = np.array(
            [
                float(np.nanmean(eval_values[:, j]))
                if np.isfinite(eval_values[:, j]).any()
                else float("nan")
                for j in range(scenario.search_width)
            ]
        )
        if not np.isfinite(candidate_means).any():
            observed_counts.append(0)
            method_failures["NO_OBSERVED_CANDIDATE"] = (
                method_failures.get("NO_OBSERVED_CANDIDATE", 0) + 1
            )
            continue
        selected = int(np.nanargmax(candidate_means))
        selected_values = eval_values[:, selected]
        finite_selected = selected_values[np.isfinite(selected_values)]
        calendar_values = tuple(
            None if np.isnan(value) else float(value) for value in selected_values
        )
        interval_rng = _rng(seed_i, scenario_part, method_part, replication)
        ci, selected_block_length, method_failure, assessment = (
            _interval_with_block_length(calendar_values, method, rng=interval_rng)
        )
        observed_counts.append(assessment.n_observed_sessions)
        if method_failure is not None:
            method_failures[method_failure] = method_failures.get(method_failure, 0) + 1
        if ci is None:
            continue
        if selected_block_length is not None:
            selected_block_lengths.append(selected_block_length)
        lower, upper = ci
        target = float(np.mean(means[eval_array]))
        estimate = float(np.mean(finite_selected))
        cover.append(lower <= target <= upper)
        if abs(target) <= 1e-15:
            false_positive.append(lower > 0.0 or upper < 0.0)
            false_superiority.append(lower > 0.0)
        if target > 0.0:
            directional.append(lower > 0.0)
        elif target < 0.0:
            directional.append(upper < 0.0)
        widths.append(upper - lower)
        estimates.append(estimate)
        targets.append(target)

    valid = len(cover)
    status = "MEASURED" if valid == reps else "PARTIAL_INVALID_REPLICATIONS"
    if valid == 0:
        status = "METHOD_NOT_MEASURABLE"
    mean_target = statistics.fmean(targets) if targets else None
    mean_estimate = statistics.fmean(estimates) if estimates else None
    mean_bias = (
        statistics.fmean(e - t for e, t in zip(estimates, targets, strict=True))
        if estimates
        else None
    )
    return CalibrationResult(
        contract_id=CALIBRATION_CONTRACT_ID,
        evidence_grade=CALIBRATION_EVIDENCE_GRADE,
        scenario_id=scenario.scenario_id,
        challenger_class=scenario.challenger_class,
        method_id=method.method_id,
        method_kind=method.method_kind,
        seed=seed_i,
        n_replications=reps,
        n_valid_replications=valid,
        n_folds_formed=folds_formed,
        n_eval_sessions_geometry=len(eval_indices),
        mean_observed_sessions=(
            statistics.fmean(observed_counts) if observed_counts else None
        ),
        mean_observed_fraction=(
            statistics.fmean(observed_counts) / len(eval_indices)
            if observed_counts
            else None
        ),
        true_target_mean=mean_target,
        mean_selected_estimate=mean_estimate,
        mean_selection_bias=mean_bias,
        coverage_rate=statistics.fmean(cover) if cover else None,
        false_superiority_rate=(
            statistics.fmean(false_superiority) if false_superiority else None
        ),
        false_positive_rate=(
            statistics.fmean(false_positive) if false_positive else None
        ),
        directional_detection_rate=(
            statistics.fmean(directional) if directional else None
        ),
        mean_interval_width=statistics.fmean(widths) if widths else None,
        mean_selected_block_length=(
            statistics.fmean(selected_block_lengths) if selected_block_lengths else None
        ),
        min_selected_block_length=(
            min(selected_block_lengths) if selected_block_lengths else None
        ),
        max_selected_block_length=(
            max(selected_block_lengths) if selected_block_lengths else None
        ),
        method_failure_counts=tuple(sorted(method_failures.items())),
        fit_capacity_mode=fit_mode,
        policy_grade_authorized=False,
        status=status,
        notes=tuple(common_notes),
    )


def default_calibration_scenarios(
    *,
    session_counts: Sequence[int] = (84, 120, 180),
    holdout_sessions: int = 20,
) -> tuple[CalibrationScenario, ...]:
    """Illustrative stress grid; values are not market estimates or floors."""
    scenarios: list[CalibrationScenario] = []
    for n_sessions in session_counts:
        n = _require_exact_int("session_count", n_sessions, minimum=1)
        h = _require_exact_int("holdout_sessions", holdout_sessions)
        if h >= n:
            raise ValueError(
                "holdout_sessions must be smaller than every session_count"
            )
        suffix = f"n{n}_h{h}"
        common = dict(
            n_sessions_total=n,
            holdout_sessions=h,
            ar1=0.4,
            noise_sd_at_reference_width=0.20,
            heteroskedastic_strength=0.5,
            names_per_session=45,
            name_missing_rate=0.05,
            min_valid_names=20,
        )
        scenarios.extend(
            [
                CalibrationScenario(
                    scenario_id=f"fixed_null_dependent_{suffix}",
                    challenger_class="fixed",
                    true_effect=0.0,
                    **common,
                ),
                CalibrationScenario(
                    scenario_id=f"fixed_alt_dependent_{suffix}",
                    challenger_class="fixed",
                    true_effect=0.05,
                    **common,
                ),
                CalibrationScenario(
                    scenario_id=f"fixed_null_search5_{suffix}",
                    challenger_class="fixed",
                    true_effect=0.0,
                    search_width=5,
                    search_correlation=0.5,
                    **common,
                ),
                CalibrationScenario(
                    scenario_id=f"fixed_null_thin_missing_{suffix}",
                    challenger_class="fixed",
                    true_effect=0.0,
                    ar1=0.4,
                    noise_sd_at_reference_width=0.20,
                    heteroskedastic_strength=0.5,
                    n_sessions_total=n,
                    holdout_sessions=h,
                    names_per_session=30,
                    name_missing_rate=0.30,
                    min_valid_names=20,
                ),
                CalibrationScenario(
                    scenario_id=f"linear_alt_session_only_{suffix}",
                    challenger_class="learned_linear",
                    true_effect=0.05,
                    **common,
                ),
                CalibrationScenario(
                    scenario_id=f"tree_regime_session_only_{suffix}",
                    challenger_class="learned_tree",
                    true_effect=0.05,
                    ar1=0.6,
                    noise_sd_at_reference_width=0.30,
                    heteroskedastic_strength=0.8,
                    regime_shift=-0.10,
                    regime_start_fraction=0.65,
                    n_sessions_total=n,
                    holdout_sessions=h,
                    names_per_session=45,
                    name_missing_rate=0.10,
                    min_valid_names=20,
                ),
            ]
        )
    return tuple(scenarios)


def default_calibration_methods(
    *, n_resamples: int = 200
) -> tuple[CalibrationMethod, ...]:
    """Explicit candidate settings; neither method nor tuning value is adopted."""
    return (
        CalibrationMethod(
            method_id="stationary_bootstrap_percentile.block5.v0",
            method_kind="stationary_bootstrap_percentile",
            confidence_level=0.95,
            block_length=5,
            n_resamples=n_resamples,
        ),
        CalibrationMethod(
            method_id="newey_west_normal.lag5.v0",
            method_kind="newey_west_normal",
            confidence_level=0.95,
            hac_lag=5,
            n_resamples=n_resamples,
        ),
    )


def run_calibration_study(
    *,
    scenarios: Sequence[CalibrationScenario] | None = None,
    methods: Sequence[CalibrationMethod] | None = None,
    seed: int = 20260810,
    n_replications: int = 100,
    n_folds: int = 3,
    embargo_sessions: int = 20,
) -> CalibrationStudy:
    seed_i = _require_exact_int("seed", seed)
    reps = _require_exact_int("n_replications", n_replications, minimum=1)
    folds_i = _require_exact_int("n_folds", n_folds, minimum=1)
    embargo_i = _require_exact_int("embargo_sessions", embargo_sessions)
    scenario_items = tuple(scenarios or default_calibration_scenarios())
    method_items = tuple(methods or default_calibration_methods())
    if not scenario_items:
        raise ValueError("scenarios must be non-empty")
    if not method_items:
        raise ValueError("methods must be non-empty")
    scenario_ids = [item.scenario_id for item in scenario_items]
    method_ids = [item.method_id for item in method_items]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("scenario_id values must be unique")
    if len(set(method_ids)) != len(method_ids):
        raise ValueError("method_id values must be unique")

    results = tuple(
        calibrate_scenario(
            scenario,
            method,
            seed=seed_i,
            n_replications=reps,
            n_folds=folds_i,
            embargo_sessions=embargo_i,
        )
        for scenario in scenario_items
        for method in method_items
    )
    return CalibrationStudy(
        contract_id=CALIBRATION_CONTRACT_ID,
        evidence_grade=CALIBRATION_EVIDENCE_GRADE,
        seed=seed_i,
        n_replications=reps,
        n_folds=folds_i,
        embargo_sessions=embargo_i,
        scenarios=scenario_items,
        methods=method_items,
        results=results,
        explicit_non_selections=(
            "Synthetic effect/noise values are stress inputs, not live estimates.",
            "No candidate interval method, block length, HAC lag, or confidence level is adopted.",
            "No missing-calendar deletion, imputation, or coverage floor is adopted.",
            "No session floor or final-holdout length is selected.",
            "Best-of-search results are deliberately unadjusted and cannot confirm a policy.",
            (
                "Learned-fit capacity and nested tuning are not modeled by this "
                "session-estimand slice."
            ),
            "No policy confirmation contract is registered and Task 06 remains blocked.",
        ),
        policy_grade_authorized=False,
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def format_calibration_report(study: CalibrationStudy) -> str:
    lines = [
        "ML-OOS-02 synthetic calibration (measurement only)",
        f"contract_id={study.contract_id}",
        f"evidence_grade={study.evidence_grade}",
        f"seed={study.seed} replications={study.n_replications}",
        f"n_folds={study.n_folds} embargo_sessions={study.embargo_sessions}",
        "policy_grade_authorized=False",
        "",
        (
            "scenario | method | folds/eval | observed | block | coverage | "
            "FP+ | FP2 | power | width | bias | fit"
        ),
    ]
    for result in study.results:
        geometry = f"{result.n_folds_formed}/{result.n_eval_sessions_geometry}"
        lines.append(
            " | ".join(
                [
                    result.scenario_id,
                    result.method_id,
                    geometry,
                    _fmt(result.mean_observed_sessions),
                    _fmt(result.mean_selected_block_length),
                    _fmt(result.coverage_rate),
                    _fmt(result.false_superiority_rate),
                    _fmt(result.false_positive_rate),
                    _fmt(result.directional_detection_rate),
                    _fmt(result.mean_interval_width),
                    _fmt(result.mean_selection_bias),
                    result.fit_capacity_mode,
                ]
            )
        )
    lines.extend(["", "Explicit non-selections:"])
    lines.extend(f"- {item}" for item in study.explicit_non_selections)
    return "\n".join(lines)
