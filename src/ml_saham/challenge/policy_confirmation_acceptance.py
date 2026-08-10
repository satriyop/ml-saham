"""Candidate operating-characteristic law for ML-OOS-02 design research.

The law in this module is deliberately non-authoritative.  It evaluates
synthetic calibration cells with Monte Carlo uncertainty and refuses to treat
unadjusted search or an explicit regime break as confirmatory evidence.  It
does not register a confirmation contract, select a production floor, inspect
live outcomes, or authorize promotion.

Semantic classification: PROTOCOL_CONTRACT design research (non-authoritative).
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass
from typing import Any, Literal, Sequence

from ml_saham.challenge.policy_confirmation_calibration import (
    AUTO_BLOCK_SELECTOR_ID,
    CALIBRATION_EVIDENCE_GRADE,
    CalibrationMethod,
    CalibrationResult,
    CalibrationScenario,
    calibrate_scenario,
)

ACCEPTANCE_STUDY_ID = "policy_confirmation_acceptance.synthetic.v3"

ScenarioRole = Literal[
    "null",
    "alternative",
    "multiplicity_probe",
    "regime_probe",
]


def _exact_int(name: str, value: object, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be exact int")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _finite(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and out < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and out > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return out


def _identity(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed string")
    return value


@dataclass(frozen=True)
class CandidateAcceptanceLaw:
    """Explicit research tolerances; not a registered policy contract."""

    law_version: str = "policy_confirmation_acceptance.candidate.v1"
    monte_carlo_confidence_level: float = 0.95
    minimum_coverage: float = 0.925
    maximum_false_superiority_rate: float = 0.075
    minimum_directional_detection_rate: float = 0.80
    minimum_valid_replication_rate: float = 0.99
    minimum_observed_session_fraction: float = 0.90
    maximum_monte_carlo_standard_error: float = 0.025
    maximum_interval_width_to_effect: float = 2.0
    minimum_folds: int = 3
    search_policy: str = "ONE_PREREGISTERED_CHALLENGER_ONLY"
    regime_policy: str = "EXPLICIT_BREAK_BLOCKS_CONFIRMATION"

    def __post_init__(self) -> None:
        _identity("law_version", self.law_version)
        for name in (
            "monte_carlo_confidence_level",
            "minimum_coverage",
            "maximum_false_superiority_rate",
            "minimum_directional_detection_rate",
            "minimum_valid_replication_rate",
            "minimum_observed_session_fraction",
            "maximum_monte_carlo_standard_error",
        ):
            _finite(name, getattr(self, name), minimum=0.0, maximum=1.0)
        if not 0.5 <= self.monte_carlo_confidence_level < 1.0:
            raise ValueError("monte_carlo_confidence_level must be in [0.5, 1.0)")
        _finite(
            "maximum_interval_width_to_effect",
            self.maximum_interval_width_to_effect,
            minimum=0.0,
        )
        _exact_int("minimum_folds", self.minimum_folds, minimum=1)
        if self.search_policy != "ONE_PREREGISTERED_CHALLENGER_ONLY":
            raise ValueError("unsupported search_policy")
        if self.regime_policy != "EXPLICIT_BREAK_BLOCKS_CONFIRMATION":
            raise ValueError("unsupported regime_policy")

    def _material_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def law_id(self) -> str:
        canonical = json.dumps(
            self._material_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return f"{self.law_version}:sha256:{hashlib.sha256(canonical).hexdigest()}"

    def to_dict(self) -> dict[str, Any]:
        return {"law_id": self.law_id, **self._material_dict()}


@dataclass(frozen=True)
class AcceptanceScenario:
    stress_family: str
    role: ScenarioRole
    scenario: CalibrationScenario

    def __post_init__(self) -> None:
        _identity("stress_family", self.stress_family)
        if self.role not in {
            "null",
            "alternative",
            "multiplicity_probe",
            "regime_probe",
        }:
            raise ValueError(f"unsupported role={self.role!r}")
        if self.role == "null" and (
            self.scenario.true_effect != 0.0 or self.scenario.regime_shift != 0.0
        ):
            raise ValueError("null scenario must have zero effect and regime shift")
        if self.role == "alternative" and self.scenario.true_effect <= 0.0:
            raise ValueError("alternative scenario must have positive true_effect")
        if self.role in {"null", "alternative"} and (
            self.scenario.search_width != 1 or self.scenario.regime_shift != 0.0
        ):
            raise ValueError(
                "eligible null/alternative requires one challenger and no regime shift"
            )
        if self.role == "multiplicity_probe" and self.scenario.search_width <= 1:
            raise ValueError("multiplicity probe requires search_width > 1")
        if self.role == "multiplicity_probe" and self.scenario.regime_shift != 0.0:
            raise ValueError(
                "multiplicity probe must isolate search without regime shift"
            )
        if self.role == "regime_probe" and self.scenario.regime_shift == 0.0:
            raise ValueError("regime probe requires a non-zero regime_shift")
        if self.role == "regime_probe" and self.scenario.search_width != 1:
            raise ValueError("regime probe must isolate one preregistered challenger")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stress_family": self.stress_family,
            "role": self.role,
            "scenario": self.scenario.to_dict(),
        }


@dataclass(frozen=True)
class ProportionEvidence:
    estimate: float
    successes: int
    trials: int
    monte_carlo_standard_error: float
    lower_bound: float
    upper_bound: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AcceptanceCellResult:
    study_id: str
    evidence_grade: str
    law_id: str
    scenario_id: str
    stress_family: str
    role: ScenarioRole
    challenger_class: str
    method_id: str
    n_sessions_total: int
    holdout_sessions: int
    n_folds_formed: int
    coverage: ProportionEvidence | None
    false_superiority: ProportionEvidence | None
    directional_detection: ProportionEvidence | None
    valid_replication_rate: float
    mean_observed_session_fraction: float | None
    interval_width_to_effect: float | None
    mean_selected_block_length: float | None
    min_selected_block_length: int | None
    max_selected_block_length: int | None
    method_failure_counts: tuple[tuple[str, int], ...]
    status: str
    reasons: tuple[str, ...]
    policy_grade_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


@dataclass(frozen=True)
class AcceptanceCandidateResult:
    method_id: str
    challenger_class: str
    n_sessions_total: int
    holdout_sessions: int
    required_cells: int
    passed_cells: int
    status: str
    failed_scenarios: tuple[str, ...]
    policy_grade_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AcceptanceStudy:
    study_id: str
    evidence_grade: str
    seed: int
    n_replications: int
    n_folds: int
    embargo_sessions: int
    law: CandidateAcceptanceLaw
    scenarios: tuple[AcceptanceScenario, ...]
    methods: tuple[CalibrationMethod, ...]
    cells: tuple[AcceptanceCellResult, ...]
    candidates: tuple[AcceptanceCandidateResult, ...]
    explicit_non_selections: tuple[str, ...]
    policy_grade_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "evidence_grade": self.evidence_grade,
            "seed": self.seed,
            "n_replications": self.n_replications,
            "n_folds": self.n_folds,
            "embargo_sessions": self.embargo_sessions,
            "law": self.law.to_dict(),
            "scenarios": [item.to_dict() for item in self.scenarios],
            "methods": [item.to_dict() for item in self.methods],
            "cells": [item.to_dict() for item in self.cells],
            "candidates": [item.to_dict() for item in self.candidates],
            "explicit_non_selections": list(self.explicit_non_selections),
            "policy_grade_authorized": self.policy_grade_authorized,
        }


def _proportion_evidence(
    rate: float | None,
    trials: int,
    *,
    confidence_level: float,
) -> ProportionEvidence | None:
    if rate is None or trials <= 0:
        return None
    value = _finite("rate", rate, minimum=0.0, maximum=1.0)
    successes_float = value * trials
    successes = int(round(successes_float))
    if not math.isclose(successes_float, successes, abs_tol=1e-8):
        raise ValueError("rate and trials do not represent an exact binomial count")
    estimate = successes / trials
    mcse = math.sqrt(estimate * (1.0 - estimate) / trials)
    z = statistics.NormalDist().inv_cdf(0.5 + confidence_level / 2.0)
    denominator = 1.0 + z * z / trials
    center = (estimate + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(
            estimate * (1.0 - estimate) / trials + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return ProportionEvidence(
        estimate=estimate,
        successes=successes,
        trials=trials,
        monte_carlo_standard_error=mcse,
        lower_bound=max(0.0, center - radius),
        upper_bound=min(1.0, center + radius),
    )


def evaluate_calibration_cell(
    spec: AcceptanceScenario,
    result: CalibrationResult,
    law: CandidateAcceptanceLaw,
) -> AcceptanceCellResult:
    if result.scenario_id != spec.scenario.scenario_id:
        raise ValueError("result/scenario identity mismatch")
    if result.challenger_class != spec.scenario.challenger_class:
        raise ValueError("result/challenger class mismatch")
    if (
        result.n_replications <= 0
        or result.n_valid_replications < 0
        or result.n_valid_replications > result.n_replications
    ):
        raise ValueError("invalid calibration replication counts")

    coverage = _proportion_evidence(
        result.coverage_rate,
        result.n_valid_replications,
        confidence_level=law.monte_carlo_confidence_level,
    )
    false_superiority = _proportion_evidence(
        result.false_superiority_rate,
        result.n_valid_replications,
        confidence_level=law.monte_carlo_confidence_level,
    )
    directional = _proportion_evidence(
        result.directional_detection_rate,
        result.n_valid_replications,
        confidence_level=law.monte_carlo_confidence_level,
    )
    valid_rate = result.n_valid_replications / result.n_replications
    effect = abs(result.true_target_mean or 0.0)
    width_ratio = (
        result.mean_interval_width / effect
        if result.mean_interval_width is not None and effect > 0.0
        else None
    )

    reasons: list[str] = []
    if spec.role == "multiplicity_probe":
        reasons.append("unadjusted search is ineligible under one-primary policy")
        status = "INELIGIBLE_MULTIPLICITY"
    elif spec.role == "regime_probe":
        reasons.append("explicit regime break blocks confirmatory interval authority")
        status = "BLOCKED_REGIME"
    else:
        if result.status != "MEASURED":
            reasons.append(f"calibration status is {result.status}")
        if valid_rate < law.minimum_valid_replication_rate:
            reasons.append("valid replication rate below candidate minimum")
        if result.n_folds_formed < law.minimum_folds:
            reasons.append("formed folds below candidate minimum")
        if (
            result.mean_observed_fraction is None
            or result.mean_observed_fraction < law.minimum_observed_session_fraction
        ):
            reasons.append("observed-session fraction below candidate minimum")
        if coverage is None:
            reasons.append("coverage is unavailable")
        else:
            if (
                coverage.monte_carlo_standard_error
                > law.maximum_monte_carlo_standard_error
            ):
                reasons.append("coverage Monte Carlo error exceeds candidate maximum")
            if coverage.lower_bound < law.minimum_coverage:
                reasons.append("coverage lower bound below candidate minimum")
        if spec.role == "null":
            if false_superiority is None:
                reasons.append("false-superiority rate is unavailable")
            else:
                if (
                    false_superiority.monte_carlo_standard_error
                    > law.maximum_monte_carlo_standard_error
                ):
                    reasons.append(
                        "false-superiority Monte Carlo error exceeds candidate maximum"
                    )
                if false_superiority.upper_bound > law.maximum_false_superiority_rate:
                    reasons.append(
                        "false-superiority upper bound exceeds candidate maximum"
                    )
        else:
            if directional is None:
                reasons.append("directional detection is unavailable")
            else:
                if (
                    directional.monte_carlo_standard_error
                    > law.maximum_monte_carlo_standard_error
                ):
                    reasons.append(
                        "detection Monte Carlo error exceeds candidate maximum"
                    )
                if directional.lower_bound < law.minimum_directional_detection_rate:
                    reasons.append("detection lower bound below candidate minimum")
            if width_ratio is None:
                reasons.append("interval-width/effect ratio is unavailable")
            elif width_ratio > law.maximum_interval_width_to_effect:
                reasons.append("interval-width/effect ratio exceeds candidate maximum")
        status = "PASS_CANDIDATE_CELL" if not reasons else "FAIL_CANDIDATE_CELL"

    return AcceptanceCellResult(
        study_id=ACCEPTANCE_STUDY_ID,
        evidence_grade=CALIBRATION_EVIDENCE_GRADE,
        law_id=law.law_id,
        scenario_id=result.scenario_id,
        stress_family=spec.stress_family,
        role=spec.role,
        challenger_class=result.challenger_class,
        method_id=result.method_id,
        n_sessions_total=spec.scenario.n_sessions_total,
        holdout_sessions=spec.scenario.holdout_sessions,
        n_folds_formed=result.n_folds_formed,
        coverage=coverage,
        false_superiority=false_superiority,
        directional_detection=directional,
        valid_replication_rate=valid_rate,
        mean_observed_session_fraction=result.mean_observed_fraction,
        interval_width_to_effect=width_ratio,
        mean_selected_block_length=result.mean_selected_block_length,
        min_selected_block_length=result.min_selected_block_length,
        max_selected_block_length=result.max_selected_block_length,
        method_failure_counts=result.method_failure_counts,
        status=status,
        reasons=tuple(reasons),
        policy_grade_authorized=False,
    )


def default_acceptance_scenarios(
    *,
    session_counts: Sequence[int] = (120, 180, 252),
    holdout_sessions: int = 20,
) -> tuple[AcceptanceScenario, ...]:
    """Predeclared representative stress grid; values are not market estimates."""
    specs: list[AcceptanceScenario] = []
    for raw_n in session_counts:
        n = _exact_int("session_count", raw_n, minimum=1)
        h = _exact_int("holdout_sessions", holdout_sessions)
        if h >= n:
            raise ValueError("holdout_sessions must be smaller than session_count")
        suffix = f"n{n}.h{h}"
        families = (
            ("moderate", 0.4, 0.5, 45, 0.05, 20),
            ("strong_dependence", 0.7, 1.0, 45, 0.05, 20),
            ("thin_missing", 0.4, 0.5, 30, 0.30, 20),
        )
        for family, ar1, hetero, names, missing, min_names in families:
            common = dict(
                challenger_class="fixed",
                n_sessions_total=n,
                holdout_sessions=h,
                ar1=ar1,
                noise_sd_at_reference_width=0.20,
                heteroskedastic_strength=hetero,
                names_per_session=names,
                name_missing_rate=missing,
                min_valid_names=min_names,
            )
            specs.extend(
                (
                    AcceptanceScenario(
                        stress_family=family,
                        role="null",
                        scenario=CalibrationScenario(
                            scenario_id=f"accept.{family}.null.{suffix}",
                            true_effect=0.0,
                            **common,
                        ),
                    ),
                    AcceptanceScenario(
                        stress_family=family,
                        role="alternative",
                        scenario=CalibrationScenario(
                            scenario_id=f"accept.{family}.alt.{suffix}",
                            true_effect=0.05,
                            **common,
                        ),
                    ),
                )
            )
        specs.extend(
            (
                AcceptanceScenario(
                    stress_family="unadjusted_search5",
                    role="multiplicity_probe",
                    scenario=CalibrationScenario(
                        scenario_id=f"probe.search5.null.{suffix}",
                        challenger_class="fixed",
                        n_sessions_total=n,
                        holdout_sessions=h,
                        true_effect=0.0,
                        ar1=0.4,
                        noise_sd_at_reference_width=0.20,
                        heteroskedastic_strength=0.5,
                        search_width=5,
                    ),
                ),
                AcceptanceScenario(
                    stress_family="late_regime_break",
                    role="regime_probe",
                    scenario=CalibrationScenario(
                        scenario_id=f"probe.regime.alt.{suffix}",
                        challenger_class="fixed",
                        n_sessions_total=n,
                        holdout_sessions=h,
                        true_effect=0.05,
                        ar1=0.4,
                        noise_sd_at_reference_width=0.20,
                        heteroskedastic_strength=0.5,
                        regime_shift=-0.10,
                        regime_start_fraction=0.65,
                    ),
                ),
            )
        )
    return tuple(specs)


def default_acceptance_methods(
    *, n_resamples: int = 200
) -> tuple[CalibrationMethod, ...]:
    """Sensitivity grid; no member is an adopted uncertainty method."""
    methods: list[CalibrationMethod] = [
        CalibrationMethod(
            method_id="stationary_bootstrap_percentile.auto_pw2009.candidate.v1",
            method_kind="stationary_bootstrap_percentile_auto",
            block_length_selector_id=AUTO_BLOCK_SELECTOR_ID,
            n_resamples=n_resamples,
        )
    ]
    for block in (3, 5, 10):
        methods.append(
            CalibrationMethod(
                method_id=f"stationary_bootstrap_percentile.block{block}.candidate.v1",
                method_kind="stationary_bootstrap_percentile",
                block_length=block,
                n_resamples=n_resamples,
            )
        )
    for lag in (3, 5, 10):
        methods.append(
            CalibrationMethod(
                method_id=f"newey_west_normal.lag{lag}.candidate.v1",
                method_kind="newey_west_normal",
                hac_lag=lag,
                n_resamples=n_resamples,
            )
        )
    return tuple(methods)


def _candidate_results(
    cells: Sequence[AcceptanceCellResult],
) -> tuple[AcceptanceCandidateResult, ...]:
    grouped: dict[tuple[str, str, int, int], list[AcceptanceCellResult]] = {}
    for cell in cells:
        if cell.role not in {"null", "alternative"}:
            continue
        key = (
            cell.method_id,
            cell.challenger_class,
            cell.n_sessions_total,
            cell.holdout_sessions,
        )
        grouped.setdefault(key, []).append(cell)
    results: list[AcceptanceCandidateResult] = []
    for key in sorted(grouped):
        items = grouped[key]
        failed = tuple(
            sorted(
                item.scenario_id
                for item in items
                if item.status != "PASS_CANDIDATE_CELL"
            )
        )
        method_id, challenger_class, n_sessions, holdout = key
        results.append(
            AcceptanceCandidateResult(
                method_id=method_id,
                challenger_class=challenger_class,
                n_sessions_total=n_sessions,
                holdout_sessions=holdout,
                required_cells=len(items),
                passed_cells=len(items) - len(failed),
                status=(
                    "PASSES_CANDIDATE_LAW" if not failed else "FAILS_CANDIDATE_LAW"
                ),
                failed_scenarios=failed,
                policy_grade_authorized=False,
            )
        )
    return tuple(results)


def _validate_scenario_grid(scenarios: Sequence[AcceptanceScenario]) -> None:
    paired: dict[tuple[str, str, int, int], dict[str, CalibrationScenario]] = {}
    for item in scenarios:
        if item.role not in {"null", "alternative"}:
            continue
        key = (
            item.stress_family,
            item.scenario.challenger_class,
            item.scenario.n_sessions_total,
            item.scenario.holdout_sessions,
        )
        roles = paired.setdefault(key, {})
        if item.role in roles:
            raise ValueError(f"duplicate {item.role} cell for stress identity {key}")
        roles[item.role] = item.scenario
    incomplete = sorted(
        key for key, roles in paired.items() if set(roles) != {"null", "alternative"}
    )
    if incomplete:
        raise ValueError(
            "each eligible stress identity requires paired null and alternative cells"
        )
    for key, roles in paired.items():
        null_material = roles["null"].to_dict()
        alternative_material = roles["alternative"].to_dict()
        for payload in (null_material, alternative_material):
            payload.pop("scenario_id")
            payload.pop("true_effect")
        if null_material != alternative_material:
            raise ValueError(
                f"paired null and alternative DGP material mismatch for {key}"
            )


def run_acceptance_study(
    *,
    scenarios: Sequence[AcceptanceScenario] | None = None,
    methods: Sequence[CalibrationMethod] | None = None,
    law: CandidateAcceptanceLaw | None = None,
    seed: int = 20260810,
    n_replications: int = 500,
    n_folds: int = 3,
    embargo_sessions: int = 20,
) -> AcceptanceStudy:
    seed_i = _exact_int("seed", seed)
    reps = _exact_int("n_replications", n_replications, minimum=1)
    folds = _exact_int("n_folds", n_folds, minimum=1)
    embargo = _exact_int("embargo_sessions", embargo_sessions)
    law_item = law or CandidateAcceptanceLaw()
    scenario_items = tuple(scenarios or default_acceptance_scenarios())
    method_items = tuple(methods or default_acceptance_methods())
    if not scenario_items or not method_items:
        raise ValueError("scenarios and methods must be non-empty")
    scenario_ids = [item.scenario.scenario_id for item in scenario_items]
    method_ids = [item.method_id for item in method_items]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("scenario ids must be unique")
    if len(set(method_ids)) != len(method_ids):
        raise ValueError("method ids must be unique")
    _validate_scenario_grid(scenario_items)

    cells = tuple(
        evaluate_calibration_cell(
            spec,
            calibrate_scenario(
                spec.scenario,
                method,
                seed=seed_i,
                n_replications=reps,
                n_folds=folds,
                embargo_sessions=embargo,
            ),
            law_item,
        )
        for spec in scenario_items
        for method in method_items
    )
    return AcceptanceStudy(
        study_id=ACCEPTANCE_STUDY_ID,
        evidence_grade=CALIBRATION_EVIDENCE_GRADE,
        seed=seed_i,
        n_replications=reps,
        n_folds=folds,
        embargo_sessions=embargo,
        law=law_item,
        scenarios=scenario_items,
        methods=method_items,
        cells=cells,
        candidates=_candidate_results(cells),
        explicit_non_selections=(
            "Candidate tolerances are research inputs, not accepted product law.",
            "No passing synthetic candidate selects a session floor or method.",
            "No missing-calendar deletion, imputation, or coverage floor is adopted.",
            "Learned-model capacity and nested tuning are outside this fixed-challenger slice.",
            "Unadjusted search is ineligible; no multiplicity correction is implemented here.",
            "An explicit regime break blocks confirmation rather than becoming a precise interval.",
            "No confirmation contract is registered and Task 06 remains blocked.",
        ),
        policy_grade_authorized=False,
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def format_acceptance_report(study: AcceptanceStudy) -> str:
    lines = [
        "ML-OOS-02 candidate operating-characteristic acceptance study",
        f"study_id={study.study_id}",
        f"law_id={study.law.law_id}",
        f"seed={study.seed} replications={study.n_replications}",
        f"n_folds={study.n_folds} embargo_sessions={study.embargo_sessions}",
        "evidence_grade=MEASUREMENT_ONLY policy_grade_authorized=False",
        "",
        "method | sessions/holdout | cells | status",
    ]
    for candidate in study.candidates:
        lines.append(
            " | ".join(
                (
                    candidate.method_id,
                    f"{candidate.n_sessions_total}/{candidate.holdout_sessions}",
                    f"{candidate.passed_cells}/{candidate.required_cells}",
                    candidate.status,
                )
            )
        )
    lines.extend(["", "Blocked probes:"])
    for cell in study.cells:
        if cell.role in {"multiplicity_probe", "regime_probe"}:
            lines.append(f"- {cell.scenario_id} / {cell.method_id}: {cell.status}")
    lines.extend(["", "Explicit non-selections:"])
    lines.extend(f"- {item}" for item in study.explicit_non_selections)
    return "\n".join(lines)
