"""ML-OOS-02 DGP/effect/acceptance target-contract vet."""

from __future__ import annotations

from ml_saham.challenge.policy_confirmation_target_vet import (
    TARGET_CONTRACT_VET_ID,
    format_target_contract_vet,
    vet_current_policy_confirmation_target,
)


def test_target_vet_is_deterministic_and_fail_closed():
    first = vet_current_policy_confirmation_target()
    second = vet_current_policy_confirmation_target()

    assert first == second
    assert first.vet_id == TARGET_CONTRACT_VET_ID
    assert first.overall_status == "BLOCKED_TARGET_CONTRACT"
    assert first.target_contract_locked is False
    assert first.proposal_lifecycle_evaluated is False
    assert first.policy_grade_authorized is False
    assert first.registered_confirmation_contracts == ()


def test_target_vet_records_current_unbound_dgp_and_effect():
    report = vet_current_policy_confirmation_target()

    assert report.synthetic_alternative_effects == (0.05,)
    assert report.candidate_observed_session_fraction == 0.90
    assert report.evaluation_mode == "POOLED_UNION_OF_OUTER_TEST_SESSIONS"
    assert report.dgp_basis == "UNVALIDATED_GENERIC_SESSION_AR1"
    assert report.cross_section_mode == (
        "BINOMIAL_VALID_NAME_COUNT_AND_VARIANCE_SCALE_ONLY"
    )


def test_target_vet_covers_each_required_review_area():
    report = vet_current_policy_confirmation_target()
    ids = {finding.finding_id for finding in report.findings}
    areas = {finding.area for finding in report.findings}

    assert ids == {
        "DGP-01",
        "DGP-02",
        "ESTIMAND-01",
        "ESTIMAND-02",
        "EFFECT-01",
        "LAW-01",
        "LAW-02",
    }
    assert areas == {"DGP", "ESTIMAND", "EFFECT", "ACCEPTANCE_LAW"}
    assert all(
        finding.follow_up_status == "NEEDS_FURTHER_VETTING"
        for finding in report.findings
    )
    assert sum(finding.severity == "BLOCKER" for finding in report.findings) == 6


def test_target_vet_serialization_and_report_preserve_non_authority():
    report = vet_current_policy_confirmation_target()
    payload = report.to_dict()
    text = format_target_contract_vet(report)

    assert payload["overall_status"] == "BLOCKED_TARGET_CONTRACT"
    assert payload["proposal_lifecycle_evaluated"] is False
    assert payload["policy_grade_authorized"] is False
    assert "Task 06 remains blocked" in text
    assert "policy_grade_authorized=False" in text
