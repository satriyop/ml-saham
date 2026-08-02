"""Phase 2: immutable policy-run requests + Result Inspector projection."""

from __future__ import annotations

from pathlib import Path

import pytest

from ml_saham.challenge.workbench import (
    build_challenge_workbench,
)
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "mvp.db")


def test_build_request_stamps_stable_request_id(tmp_path: Path, fixture_db: Path):
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    a = service.build_policy_run_request(
        policy_id="screener.accum.score_weights",
        baseline_id="static_reference",
        against_id="equal_sleeves",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        purpose_family="ACCUM",
        write_artifact=False,
    )
    b = service.build_policy_run_request(
        policy_id="screener.accum.score_weights",
        baseline_id="static_reference",
        against_id="equal_sleeves",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        purpose_family="ACCUM",
        write_artifact=False,
    )
    assert a.request_id == b.request_id
    assert a.request_id
    assert a.verb == "policy_run"
    assert a.protocol_id


def test_build_request_rejects_missing_compatibility(tmp_path: Path, fixture_db: Path):
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    with pytest.raises(ValueError, match="compatibility_id"):
        service.build_policy_run_request(
            policy_id="screener.accum.score_weights",
            baseline_id="production",
            against_id="equal_sleeves",
            compatibility_id="— no selection —",
        )


def test_build_request_rejects_unknown_challenger(tmp_path: Path, fixture_db: Path):
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    with pytest.raises(ValueError, match="against_id"):
        service.build_policy_run_request(
            policy_id="screener.accum.score_weights",
            baseline_id="static_reference",
            against_id="not_a_real_challenger_xyz",
            compatibility_id=FIXTURE_COMPATIBILITY_ID,
        )


def test_duplicate_attempt_does_not_reexecute(tmp_path: Path, fixture_db: Path):
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    request = service.build_policy_run_request(
        policy_id="screener.accum.score_weights",
        baseline_id="static_reference",
        against_id="equal_sleeves",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        write_artifact=False,
    )
    keys: set[str] = set()
    attempt = service.new_attempt_id()
    first = service.execute_policy_run(
        request, attempt_id=attempt, executed_keys=keys
    )
    second = service.execute_policy_run(
        request, attempt_id=attempt, executed_keys=keys
    )
    assert first.kind == "product_result"
    assert first.status in {
        "WIN",
        "LOSE",
        "INCONCLUSIVE",
        "BLOCKED_DATA",
        "BLOCKED_POLICY",
    }
    assert second.kind == "application_error"
    assert second.status == "DUPLICATE_ATTEMPT"
    assert f"{request.request_id}:{attempt}" in keys


def test_run_again_new_attempt_executes(tmp_path: Path, fixture_db: Path):
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    request = service.build_policy_run_request(
        policy_id="screener.accum.score_weights",
        baseline_id="static_reference",
        against_id="equal_sleeves",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        write_artifact=False,
    )
    keys: set[str] = set()
    a1 = service.execute_policy_run(
        request, attempt_id=service.new_attempt_id(), executed_keys=keys
    )
    a2 = service.execute_policy_run(
        request, attempt_id=service.new_attempt_id(), executed_keys=keys
    )
    assert a1.kind == "product_result"
    assert a2.kind == "product_result"
    assert a1.attempt_id != a2.attempt_id
    assert len(keys) == 2


def test_blocked_product_state_not_application_error(tmp_path: Path, fixture_db: Path):
    """Unknown compatibility id completes as product BLOCKED_* (not UI exception)."""
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    request = service.build_policy_run_request(
        policy_id="screener.accum.score_weights",
        baseline_id="production",
        against_id="equal_sleeves",
        compatibility_id="sha256:definitely_not_a_real_cohort_id",
        write_artifact=False,
    )
    view = service.execute_policy_run(
        request,
        attempt_id=service.new_attempt_id(),
        executed_keys=set(),
    )
    assert view.kind == "product_result"
    assert view.status in {"BLOCKED_POLICY", "BLOCKED_DATA"}
    assert view.error_reference is None
    assert view.lines
    assert view.human_next_step


def test_result_view_exposes_identity_and_folds(tmp_path: Path, fixture_db: Path):
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    request = service.build_policy_run_request(
        policy_id="screener.accum.score_weights",
        baseline_id="static_reference",
        against_id="equal_sleeves",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        write_artifact=False,
    )
    view = service.execute_policy_run(
        request,
        attempt_id=service.new_attempt_id(),
        executed_keys=set(),
    )
    assert view.policy_id == "screener.accum.score_weights"
    assert view.against_id == "equal_sleeves"
    assert view.baseline_id == "static_reference"
    assert view.request_id == request.request_id
    # folds may be empty under thin fixture, but field is always present
    assert isinstance(view.fold_metrics, tuple)
    assert view.elapsed_seconds >= 0.0


def test_protocol_summary_read_only():
    service = build_challenge_workbench()
    summary = service.describe_protocol("accum_path_v1")
    assert summary is not None
    assert summary.min_folds_for_win >= 2
    assert summary.primary_horizon == 10
    assert service.describe_protocol("nope.protocol") is None


def test_streamlit_run_page_loads(monkeypatch, tmp_path: Path, fixture_db: Path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    art = tmp_path / "artifacts"
    monkeypatch.setenv("ML_SAHAM_DB", str(fixture_db))
    monkeypatch.setenv("ML_SAHAM_ARTIFACTS", str(art))
    app_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ml_saham"
        / "ui"
        / "streamlit_app.py"
    )
    rendered = AppTest.from_file(str(app_path), default_timeout=15).run()
    assert not rendered.exception
    text = "\n".join(
        str(getattr(el, "value", el))
        for collection in (
            rendered.title,
            rendered.caption,
            rendered.info,
            rendered.markdown,
        )
        for el in collection
    )
    assert "Phase 2" in text or "Run" in text
