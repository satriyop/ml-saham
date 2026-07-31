"""signal.accum.evidence_group_weights — production setup 0.60 / flow 0.40."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.engines import list_engines
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.panel_signal import extract_signal_components
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.scorers import (
    score_evidence_equal_groups,
    score_evidence_group_weights,
    score_production,
)
from ml_saham.challenge.types import ChallengeStatus
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "evg.db", min_bars=120)


def test_policy_and_engine_registration():
    pol = load_policy("signal.accum.evidence_group_weights")
    assert pol.score_kind == "evidence_group_weights"
    w = pol.weight_map()
    assert abs(w["setup_quality"] - 0.60) < 1e-9
    assert abs(w["flow_confirmation"] - 0.40) < 1e-9
    eng = next(e for e in list_engines() if e["engine_id"] == "signal")
    assert "signal.accum.evidence_group_weights" in eng["policies"]["accum"]


def test_extract_maps_institutional_flow_to_flow_confirmation():
    pol = load_policy("signal.accum.evidence_group_weights")
    payload = {
        "signal": {
            "raw_score": 55.0,
            "alpha_trigger_score": {
                "group_contributions": [
                    {"group": "setup_quality", "score": 80.0},
                    {"group": "institutional_flow", "score": 40.0},
                ]
            },
        }
    }
    comps = extract_signal_components(payload, pol)
    assert comps is not None
    assert comps["setup_quality"] == 80.0
    assert comps["flow_confirmation"] == 40.0


def test_production_weighted_mean_and_drop_setup():
    pol = load_policy("signal.accum.evidence_group_weights")
    row = PanelRow(
        "X",
        "2024-01-01",
        {"setup_quality": 100.0, "flow_confirmation": 0.0},
        {10: 0.01},
    )
    prod = score_production([row], pol)[0]
    # 0.6*100 + 0.4*0 = 60
    assert prod == pytest.approx(60.0)
    eq = score_evidence_equal_groups([row], pol)[0]
    assert eq == pytest.approx(50.0)
    drop_s = score_evidence_group_weights([row], pol, drop_key="setup_quality")[0]
    # only flow 0
    assert drop_s == pytest.approx(0.0)
    drop_f = score_evidence_group_weights([row], pol, drop_key="flow_confirmation")[0]
    assert drop_f == pytest.approx(100.0)


def test_run_equal_and_drop_setup(fixture_db: Path):
    for against in ("equal_sleeves", "drop_setup", "drop_flow"):
        r = run_policy_challenge(
            fixture_db,
            "signal.accum.evidence_group_weights",
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
            assert "POLICY CHALLENGE" in "\n".join(r.lines)


def test_cli(fixture_db: Path):
    from ml_saham.challenge.runner import list_policies

    ids = {p["policy_id"] for p in list_policies()}
    assert "signal.accum.evidence_group_weights" in ids

    lst = runner.invoke(app, ["--db", str(fixture_db), "challenge", "list"])
    assert lst.exit_code == 0
    # Rich table may ellipsize long policy_ids
    assert "evidence_group" in lst.stdout or "signal.accum" in lst.stdout

    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "run",
            "signal.accum.evidence_group_weights",
            "--against",
            "drop_setup",
            "--compatibility-id",
            FIXTURE_COMPATIBILITY_ID,
            "--no-artifact",
        ],
    )
    assert r.exit_code in (0, 2), r.stdout
    assert (
        "evidence_group" in r.stdout
        or "signal.accum.evidence" in r.stdout
        or "BLOCKED" in r.stdout
        or "POLICY CHALLENGE" in r.stdout
    )
