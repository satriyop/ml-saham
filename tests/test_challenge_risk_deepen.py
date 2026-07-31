"""P3 deepen: expanded gates + gate_off:<name> ablation."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.panel_gates import extract_gate_components
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.scorers import score_gate_off_named, score_production
from ml_saham.challenge.types import ChallengeStatus
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "riskd.db", min_bars=120)


def test_expanded_gates_in_policy():
    pol = load_policy("risk.accum.hard_gates")
    keys = {c.key for c in pol.enabled_components()}
    assert {
        "bandar_gate",
        "liquidity_gate",
        "fundamental_gate",
        "free_float_gate",
        "technical_gate",
    } <= keys


def test_extract_fundamental_and_per_gate_off():
    pol = load_policy("risk.accum.hard_gates")
    payload = {
        "trade_setup": {
            "action": "BLOCKED",
            "blocking_gates": ["BandarGate", "FundamentalGate"],
        }
    }
    comps = extract_gate_components(payload, pol)
    assert comps is not None
    assert comps["bandar_gate"] == 1.0
    assert comps["fundamental_gate"] == 1.0
    assert comps["liquidity_gate"] == 0.0
    rows = [PanelRow("A", "2024-01-01", comps, {10: -0.02})]
    prod = score_production(rows, pol)[0]
    assert prod == 0.0  # blocked
    # turn off bandar only — fundamental still blocks
    off_b = score_gate_off_named(rows, pol, "bandar_gate")[0]
    assert off_b == 0.0
    # turn off both via full gate_off path not tested here
    off_f = score_gate_off_named(rows, pol, "fundamental_gate")[0]
    assert off_f == 0.0  # bandar still on
    # only fundamental → off fundamental leaves bandar block
    comps2 = {
        "bandar_gate": 0.0,
        "liquidity_gate": 0.0,
        "fundamental_gate": 1.0,
        "free_float_gate": 0.0,
        "technical_gate": 0.0,
    }
    rows2 = [PanelRow("B", "2024-01-01", comps2, {10: 0.01})]
    assert score_production(rows2, pol)[0] == 0.0
    assert score_gate_off_named(rows2, pol, "fundamental_gate")[0] == 1.0


def test_run_gate_off_named(fixture_db: Path):
    r = run_policy_challenge(
        fixture_db,
        "risk.accum.hard_gates",
        against="gate_off:bandar_gate",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert r.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
        ChallengeStatus.BLOCKED_DATA,
        ChallengeStatus.BLOCKED_POLICY,
    }
    if r.status not in (
        ChallengeStatus.BLOCKED_DATA,
        ChallengeStatus.BLOCKED_POLICY,
    ):
        assert any("bandar" in n.lower() for n in r.notes) or r.against_id.startswith(
            "gate_off"
        )
        text = "\n".join(r.lines)
        assert "GATE" in text or "gate" in text.lower()
        assert "KEEP_DISPLAY" not in text


def test_cli_gate_off_named(fixture_db: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "run",
            "risk.accum.hard_gates",
            "--against",
            "gate_off:liquidity",
            "--compatibility-id",
            FIXTURE_COMPATIBILITY_ID,
            "--no-artifact",
        ],
    )
    assert r.exit_code in (0, 2), r.stdout
