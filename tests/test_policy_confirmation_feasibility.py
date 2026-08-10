"""ML-OOS-02 cohort feasibility audit: explicit, read-only, no outcomes."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ml_saham.challenge.policy_confirmation_feasibility import (
    FEASIBILITY_AUDIT_CONTRACT_ID,
    audit_accum_cohort_feasibility,
    capture_read_only_db_fingerprint,
    format_feasibility_report,
)
from ml_saham.data.aisaham_read import connect
from tests.fixtures.build_mvp_fixture import (
    FIXTURE_COMPATIBILITY_ID,
    build_mvp_fixture,
)

SECONDARY_ID = "sha256:fixture_cohort_secondary"


@pytest.fixture()
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "mvp.db", min_bars=120)


def test_audit_keeps_discovered_cohorts_separate_and_non_authoritative(
    fixture_db: Path,
):
    audit = audit_accum_cohort_feasibility(fixture_db)
    assert audit.contract_id == FEASIBILITY_AUDIT_CONTRACT_ID
    assert audit.db_unchanged is True
    assert audit.before == audit.after
    assert audit.outcomes_inspected is False
    assert audit.policy_grade_authorized is False
    assert {cohort.compatibility_id for cohort in audit.cohorts} == {
        FIXTURE_COMPATIBILITY_ID,
        SECONDARY_ID,
    }

    primary = next(
        cohort
        for cohort in audit.cohorts
        if cohort.compatibility_id == FIXTURE_COMPATIBILITY_ID
    )
    assert primary.raw_extractable_rows == primary.cohort_observation_rows
    assert primary.unique_ticker_sessions <= primary.raw_extractable_rows
    assert primary.primary_eligible_rows <= primary.unique_ticker_sessions
    assert primary.outcomes_inspected is False
    assert primary.policy_grade_authorized is False

    secondary = next(
        cohort for cohort in audit.cohorts if cohort.compatibility_id == SECONDARY_ID
    )
    assert secondary.status == "BLOCKED_POLICY"
    assert secondary.challenge_blocked_status == "BLOCKED_POLICY"


def test_explicit_cohort_never_falls_open_or_pools(fixture_db: Path):
    audit = audit_accum_cohort_feasibility(
        fixture_db,
        compatibility_ids=(FIXTURE_COMPATIBILITY_ID,),
    )
    assert [cohort.compatibility_id for cohort in audit.cohorts] == [
        FIXTURE_COMPATIBILITY_ID
    ]
    with pytest.raises(ValueError, match="not found"):
        audit_accum_cohort_feasibility(
            fixture_db,
            compatibility_ids=("sha256:not-present",),
        )


def test_canonical_connection_is_physically_read_only(fixture_db: Path):
    before = capture_read_only_db_fingerprint(fixture_db)
    with connect(fixture_db) as conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TABLE forbidden_write (id INTEGER)")
    after = capture_read_only_db_fingerprint(fixture_db)
    assert before == after


def test_report_states_limits_and_geometry(fixture_db: Path):
    audit = audit_accum_cohort_feasibility(
        fixture_db,
        compatibility_ids=(FIXTURE_COMPATIBILITY_ID,),
    )
    text = format_feasibility_report(audit)
    assert "read-only, non-authoritative" in text
    assert "outcomes_inspected=False" in text
    assert "policy_grade_authorized=False" in text
    assert "folds_formed=" in text
    assert "No policy confirmation contract was registered" in text


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"compatibility_ids": "bad"}, "sequence"),
        ({"holdout_candidates": ()}, "non-empty"),
        ({"holdout_candidates": (5, 5)}, "unique"),
        ({"holdout_candidates": (True,)}, "exact non-negative ints"),
    ],
)
def test_audit_rejects_ambiguous_inputs(fixture_db: Path, kwargs, match):
    with pytest.raises(ValueError, match=match):
        audit_accum_cohort_feasibility(fixture_db, **kwargs)
