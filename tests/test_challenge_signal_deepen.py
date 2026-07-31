"""P2 deepen: signal.accum.flags + signal.accum.classification."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.engines import list_engines
from ml_saham.challenge.panel_signal import extract_signal_components
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.scorers import score_flags_off, score_production
from ml_saham.challenge.types import ChallengeStatus
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "sigd.db", min_bars=120)


def test_signal_engine_lists_deep_policies():
    eng = next(e for e in list_engines() if e["engine_id"] == "signal")
    pids = eng["policies"]["accum"]
    assert "signal.accum.raw_score" in pids
    assert "signal.accum.flags" in pids
    assert "signal.accum.classification" in pids


def test_extract_flags_and_score():
    pol = load_policy("signal.accum.flags")
    payload = {
        "signal": {
            "raw_score": 80.0,
            "flags": ["VALUATION_STRETCHED", "INSIDER_SELLING"],
        }
    }
    comps = extract_signal_components(payload, pol)
    assert comps is not None
    assert comps["production_raw_score"] == 80.0
    assert comps["valuation_stretched"] == 1.0
    assert comps["insider_selling"] == 1.0
    assert comps["analyst_bearish"] == 0.0
    from ml_saham.challenge.panel import PanelRow

    row = PanelRow("X", "2024-01-01", comps, {10: 0.01})
    prod = score_production([row], pol)[0]
    off = score_flags_off([row], pol)[0]
    assert off == 80.0
    assert prod == pytest.approx(80.0 - 10.0 - 12.0)


def test_run_flags_and_classification(fixture_db: Path):
    for pid, against in (
        ("signal.accum.flags", "flags_off"),
        ("signal.accum.classification", "threshold_shift"),
    ):
        r = run_policy_challenge(
            fixture_db,
            pid,
            against=against,
            write_artifact=False,
            compatibility_id=FIXTURE_COMPATIBILITY_ID,
        )
        assert r.status in {
            ChallengeStatus.WIN,
            ChallengeStatus.LOSE,
            ChallengeStatus.INCONCLUSIVE,
            ChallengeStatus.BLOCKED_DATA,
        }
        assert r.status.value not in {"KEEP_DISPLAY", "PROMOTE_CANDIDATE"}
        if r.status not in (
            ChallengeStatus.BLOCKED_DATA,
            ChallengeStatus.BLOCKED_POLICY,
        ):
            assert r.n_rows >= 80
            assert r.exit_code() == 0


def test_cli_flags(fixture_db: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "run",
            "signal.accum.flags",
            "--against",
            "flags_off",
            "--compatibility-id",
            FIXTURE_COMPATIBILITY_ID,
            "--no-artifact",
        ],
    )
    assert r.exit_code in (0, 2), r.stdout
    assert "signal.accum.flags" in r.stdout or "BLOCKED" in r.stdout
