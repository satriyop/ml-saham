"""signal.accum.raw_score policy tournament."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.panel_signal import extract_signal_components
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.types import ChallengeStatus
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "sig.db", min_bars=120)


def test_policy_loads():
    pol = load_policy("signal.accum.raw_score")
    assert pol.panel_kind == "accum_signal"
    assert pol.score_kind == "raw_score_primary"
    assert pol.protocol_id == "accum_path_v1"


def test_extract_live_adr056_features_by_window_signal():
    """Live ACCUM captures nest SignalEngine under features_by_window — not top-level signal.raw_score."""
    pol = load_policy("signal.accum.raw_score")
    payload = {
        "ticker": "BBCA",
        "session_date": "2024-06-03",
        "canonical_window": 7,
        "features_by_window": {
            "7": {
                "signal": {
                    # no raw_score key (live shape)
                    "raw_exact_score": 55.29,
                    "raw_group_score": 55.0,
                    "active_flags": [],
                    "assessment": {
                        "score": 55.0,
                        "raw_exact_score": 55.29,
                    },
                    "alpha_trigger_score": {
                        "group_contributions": [
                            {"group": "setup_quality", "score": 0.0},
                            {"group": "institutional_flow", "score": 55.29},
                        ]
                    },
                }
            }
        },
    }
    comps = extract_signal_components(payload, pol)
    assert comps is not None
    # prefer raw_exact_score when present before assessment.score
    assert comps["production_raw_score"] == pytest.approx(55.29)
    assert comps.get("institutional_flow") == pytest.approx(55.29) or comps.get(
        "flow_confirmation"
    ) == pytest.approx(55.29)


def test_extract_assessment_score_when_raw_exact_missing():
    pol = load_policy("signal.accum.raw_score")
    payload = {
        "features_by_window": {
            "7": {
                "signal": {
                    "assessment": {"score": 41.0},
                }
            }
        }
    }
    comps = extract_signal_components(payload, pol)
    assert comps is not None
    assert comps["production_raw_score"] == 41.0


def test_extract_legacy_top_level_signal_still_works():
    pol = load_policy("signal.accum.raw_score")
    payload = {"signal": {"raw_score": 70.0}}
    comps = extract_signal_components(payload, pol)
    assert comps is not None
    assert comps["production_raw_score"] == 70.0


def test_run_signal_on_fixture(fixture_db: Path):
    r = run_policy_challenge(
        fixture_db,
        "signal.accum.raw_score",
        against="equal_sleeves",
        write_artifact=False,
    )
    assert r.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
        ChallengeStatus.BLOCKED_DATA,
    }
    assert r.policy_id == "signal.accum.raw_score"
    # tournament vocabulary — not diagnostic display
    assert r.status.value not in {
        "KEEP_DISPLAY",
        "DEMOTE_DISPLAY",
        "PROMOTE_CANDIDATE",
    }
    if r.status not in (ChallengeStatus.BLOCKED_DATA, ChallengeStatus.BLOCKED_POLICY):
        assert r.n_rows >= 80
        assert "POLICY CHALLENGE" in "\n".join(r.lines)
        assert r.exit_code() == 0


def test_cli_list_and_run(fixture_db: Path):
    lst = runner.invoke(app, ["--db", str(fixture_db), "challenge", "list"])
    assert lst.exit_code == 0
    assert "signal.accum.raw_score" in lst.stdout

    run = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "run",
            "signal.accum.raw_score",
            "--against",
            "equal_sleeves",
            "--no-artifact",
        ],
    )
    assert run.exit_code in (0, 2), run.stdout
    assert "signal.accum.raw_score" in run.stdout or "BLOCKED" in run.stdout
    assert "KEEP_DISPLAY" not in run.stdout
