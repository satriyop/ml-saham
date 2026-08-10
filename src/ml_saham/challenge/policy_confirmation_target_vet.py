"""Fail-closed target-contract audit for ML-OOS-02 design research.

The audit describes whether the current synthetic calibration target is aligned
with the shipped proposal lifecycle.  It does not inspect outcomes, choose
numerical thresholds, register a confirmation contract, or authorize policy
promotion.

Semantic classification: PROTOCOL_CONTRACT design research (non-authoritative).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ml_saham.challenge.policy_confirmation_acceptance import (
    ACCEPTANCE_STUDY_ID,
    CandidateAcceptanceLaw,
    default_acceptance_scenarios,
)
from ml_saham.challenge.policy_confirmation_calibration import (
    CALIBRATION_CONTRACT_ID,
)
from ml_saham.challenge.promote import POLICY_CONFIRMATION_CONTRACTS
from ml_saham.challenge.protocols import ACCUM_PATH_V1

TARGET_CONTRACT_VET_ID = "policy_confirmation_target_contract_vet.v1"
TARGET_CONTRACT_VET_GRADE = "MEASUREMENT_ONLY"

FindingArea = Literal["DGP", "ESTIMAND", "EFFECT", "ACCEPTANCE_LAW"]
FindingSeverity = Literal["BLOCKER", "WARNING"]


@dataclass(frozen=True)
class TargetContractFinding:
    finding_id: str
    area: FindingArea
    severity: FindingSeverity
    finding: str
    executable_evidence: str
    proposed_follow_up: str
    follow_up_status: str = "NEEDS_FURTHER_VETTING"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyConfirmationTargetVet:
    vet_id: str
    evidence_grade: str
    calibration_contract_id: str
    acceptance_study_id: str
    protocol_id: str
    registered_confirmation_contracts: tuple[str, ...]
    synthetic_alternative_effects: tuple[float, ...]
    candidate_observed_session_fraction: float
    evaluation_mode: str
    dgp_basis: str
    cross_section_mode: str
    findings: tuple[TargetContractFinding, ...]
    overall_status: str
    target_contract_locked: bool
    proposal_lifecycle_evaluated: bool
    policy_grade_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["findings"] = [finding.to_dict() for finding in self.findings]
        return payload


def vet_current_policy_confirmation_target() -> PolicyConfirmationTargetVet:
    """Audit the shipped synthetic target without inspecting live outcomes."""
    scenarios = default_acceptance_scenarios(session_counts=(120,))
    law = CandidateAcceptanceLaw()
    alternative_effects = tuple(
        sorted(
            {
                item.scenario.true_effect
                for item in scenarios
                if item.role == "alternative"
            }
        )
    )
    findings = (
        TargetContractFinding(
            finding_id="DGP-01",
            area="DGP",
            severity="BLOCKER",
            finding=(
                "The stress grid is a generic session-mean AR(1) process with a "
                "sinusoidal variance scale; no accepted source binds its parameter "
                "envelope to an ACCUM proposal estimand."
            ),
            executable_evidence=(
                "CalibrationScenario exposes ar1/noise/heteroskedasticity inputs, "
                "and default_acceptance_scenarios hard-codes candidate values."
            ),
            proposed_follow_up=(
                "Predeclare a DGP envelope from conservative synthetic bounds or a "
                "separate design-only historical cohort that can never serve as "
                "confirmation evidence."
            ),
        ),
        TargetContractFinding(
            finding_id="DGP-02",
            area="DGP",
            severity="BLOCKER",
            finding=(
                "Cross-sectional width is represented only by a binomial valid-name "
                "count and variance scaling; name-level scores, targets, rank ties, "
                "cross-name dependence, and session IC construction are not simulated."
            ),
            executable_evidence=(
                "_simulate_session_estimands emits one session estimand per search "
                "member and never constructs ticker-level score/target pairs."
            ),
            proposed_follow_up=(
                "Define the exact decision-specific session metric and simulate the "
                "ticker/session inputs needed to produce it through shipped metric code."
            ),
        ),
        TargetContractFinding(
            finding_id="ESTIMAND-01",
            area="ESTIMAND",
            severity="BLOCKER",
            finding=(
                "The calibration interval targets one pooled union of outer test "
                "sessions, while the shipped proposal verdict averages fold ICs, "
                "requires directional fold agreement, and applies a tail gate."
            ),
            executable_evidence=(
                "calibrate_scenario unions fold test indices before one interval; "
                "runner._verdict evaluates fold_metrics and tail_baseline/tail_against."
            ),
            proposed_follow_up=(
                "Build a lifecycle-level simulator that produces fold-wise metrics and "
                "passes them through the same verdict aggregation contract."
            ),
        ),
        TargetContractFinding(
            finding_id="ESTIMAND-02",
            area="ESTIMAND",
            severity="BLOCKER",
            finding=(
                "The shipped fold metric itself pools ticker/session rows into one "
                "rank IC, while the outcome-blind methodology vet requires sessions "
                "to be the independent inferential unit."
            ),
            executable_evidence=(
                "runner.run_policy_challenge passes all fold test-row scores and "
                "targets directly to ic_safe before recording one fold IC."
            ),
            proposed_follow_up=(
                "Choose and version a session-native fold estimand before lifecycle "
                "calibration; preserve existing exploratory artifacts as historical."
            ),
        ),
        TargetContractFinding(
            finding_id="EFFECT-01",
            area="EFFECT",
            severity="BLOCKER",
            finding=(
                "The sole eligible alternative effect is 0.05 synthetic units and is "
                "not bound to costs, turnover, tail non-inferiority, or a minimum "
                "improvement that would justify human policy review."
            ),
            executable_evidence=(
                f"Default eligible alternative effects are {alternative_effects!r}."
            ),
            proposed_follow_up=(
                "Define a decision-specific smallest effect of interest in the exact "
                "metric unit before rerunning power or precision calibration."
            ),
        ),
        TargetContractFinding(
            finding_id="LAW-01",
            area="ACCEPTANCE_LAW",
            severity="BLOCKER",
            finding=(
                "minimum_folds currently checks only how many folds the geometry forms; "
                "it does not calibrate valid-fold count, fold agreement, or the tail gate."
            ),
            executable_evidence=(
                "evaluate_calibration_cell reads CalibrationResult.n_folds_formed, "
                "while CalibrationResult has no fold-wise verdict evidence."
            ),
            proposed_follow_up=(
                "Replace the geometry-only gate with lifecycle operating characteristics "
                "after the estimand and fold aggregation contract are frozen."
            ),
        ),
        TargetContractFinding(
            finding_id="LAW-02",
            area="ACCEPTANCE_LAW",
            severity="WARNING",
            finding=(
                "The 90% observed-session tolerance is not operational for current "
                "interval candidates because every method rejects any incomplete "
                "calendar before interval construction."
            ),
            executable_evidence=(
                "assess_calendar_estimand_series returns "
                "MISSING_CALENDAR_SESSION_UNSUPPORTED for any gap; the candidate law "
                f"still records {law.minimum_observed_session_fraction:.0%}."
            ),
            proposed_follow_up=(
                "Choose either an explicit complete-calendar requirement or a separately "
                "vetted missing-data method; do not retain a dormant tolerance as policy."
            ),
        ),
    )
    has_blocker = any(finding.severity == "BLOCKER" for finding in findings)
    return PolicyConfirmationTargetVet(
        vet_id=TARGET_CONTRACT_VET_ID,
        evidence_grade=TARGET_CONTRACT_VET_GRADE,
        calibration_contract_id=CALIBRATION_CONTRACT_ID,
        acceptance_study_id=ACCEPTANCE_STUDY_ID,
        protocol_id=ACCUM_PATH_V1.protocol_id,
        registered_confirmation_contracts=tuple(
            sorted(POLICY_CONFIRMATION_CONTRACTS)
        ),
        synthetic_alternative_effects=alternative_effects,
        candidate_observed_session_fraction=law.minimum_observed_session_fraction,
        evaluation_mode="POOLED_UNION_OF_OUTER_TEST_SESSIONS",
        dgp_basis="UNVALIDATED_GENERIC_SESSION_AR1",
        cross_section_mode="BINOMIAL_VALID_NAME_COUNT_AND_VARIANCE_SCALE_ONLY",
        findings=findings,
        overall_status=(
            "BLOCKED_TARGET_CONTRACT" if has_blocker else "READY_FOR_TARGET_LOCK"
        ),
        target_contract_locked=False,
        proposal_lifecycle_evaluated=False,
        policy_grade_authorized=False,
    )


def format_target_contract_vet(report: PolicyConfirmationTargetVet) -> str:
    lines = [
        "ML-OOS-02 target-contract vet (measurement only)",
        f"vet_id={report.vet_id}",
        f"calibration_contract_id={report.calibration_contract_id}",
        f"acceptance_study_id={report.acceptance_study_id}",
        f"protocol_id={report.protocol_id}",
        f"overall_status={report.overall_status}",
        "target_contract_locked=False",
        "proposal_lifecycle_evaluated=False",
        "policy_grade_authorized=False",
        "",
        "finding | area | severity | follow-up",
    ]
    lines.extend(
        " | ".join(
            (
                finding.finding_id,
                finding.area,
                finding.severity,
                finding.follow_up_status,
            )
        )
        for finding in report.findings
    )
    lines.extend(
        [
            "",
            "No confirmation contract was registered and Task 06 remains blocked.",
        ]
    )
    return "\n".join(lines)
