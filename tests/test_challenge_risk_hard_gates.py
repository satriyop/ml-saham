"""risk.accum.hard_gates — gate metric, not sleeve KEEP/DEMOTE."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.engines import list_engines
from ml_saham.challenge.panel_gates import extract_gate_components
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.scorers import mean_excess_allowed, score_gate_off, score_production
from ml_saham.challenge.types import ChallengeStatus
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "gate.db", min_bars=120)


def test_policy_and_engines():
    pol = load_policy("risk.accum.hard_gates")
    assert pol.score_kind == "gate_block"
    assert pol.panel_kind == "accum_gates"
    eng = {e["engine_id"]: e for e in list_engines()}
    assert "risk" in eng
    assert "risk.accum.hard_gates" in eng["risk"]["policies"]["accum"]
    assert "signal" in eng
    assert "signal.accum.raw_score" in eng["signal"]["policies"]["accum"]


def test_extract_bandar_gate_legacy_top_level():
    """Fixture/legacy shape still works."""
    pol = load_policy("risk.accum.hard_gates")
    payload = {
        "trade_setup": {
            "action": "BLOCKED",
            "blocking_gates": ["BandarGate"],
        }
    }
    comps = extract_gate_components(payload, pol)
    assert comps is not None
    assert comps["bandar_gate"] == 1.0
    assert comps["liquidity_gate"] == 0.0


def test_extract_gates_from_adr056_features_by_window():
    """Live captures nest trade_setup under features_by_window — not root payload."""
    from tests.fixtures.golden import load_golden

    pol = load_policy("risk.accum.hard_gates")
    payload = load_golden("risk_adr056_trade_setup.json")
    assert "trade_setup" not in payload
    comps = extract_gate_components(payload, pol)
    assert comps is not None
    assert comps["free_float_gate"] == 1.0
    assert comps["bandar_gate"] == 1.0
    assert comps["liquidity_gate"] == 0.0
    # empty payload without any trade_setup must not invent all-clear
    assert extract_gate_components({"ticker": "X"}, pol) is None


def test_mean_excess_allowed_and_gate_off():
    from ml_saham.challenge.panel import PanelRow

    pol = load_policy("risk.accum.hard_gates")
    rows = [
        PanelRow("A", "2024-01-01", {"bandar_gate": 1.0, "liquidity_gate": 0.0}, {10: -0.05}),
        PanelRow("B", "2024-01-01", {"bandar_gate": 0.0, "liquidity_gate": 0.0}, {10: 0.02}),
        PanelRow("C", "2024-01-02", {"bandar_gate": 0.0, "liquidity_gate": 0.0}, {10: 0.01}),
        PanelRow("D", "2024-01-02", {"bandar_gate": 0.0, "liquidity_gate": 1.0}, {10: -0.04}),
    ]
    prod = score_production(rows, pol)
    off = score_gate_off(rows, pol)
    assert prod == [0.0, 1.0, 1.0, 0.0]
    assert off == [1.0, 1.0, 1.0, 1.0]
    m_prod, br, n_open = mean_excess_allowed(rows, prod, 10)
    assert br == 0.5
    assert n_open == 2
    assert m_prod == pytest.approx(0.015)


def test_run_gate_on_fixture(fixture_db: Path):
    r = run_policy_challenge(
        fixture_db,
        "risk.accum.hard_gates",
        against="gate_off",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert r.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
        ChallengeStatus.BLOCKED_DATA,
    }
    text = "\n".join(r.lines)
    assert "GATE" in text or "gate" in text.lower()
    assert "mean excess" in text.lower() or "mean_open" in text or "ALLOWED" in text
    assert "KEEP_DISPLAY" not in text
    assert "KEEP/DEMOTE" in text or "not sleeve" in text.lower() or "gate" in text.lower()
    # not presented as factor KEEP
    assert "Factor validity" not in text
    if r.status not in (ChallengeStatus.BLOCKED_DATA, ChallengeStatus.BLOCKED_POLICY):
        assert r.weights.get("decision_type") == "gate"
        assert r.exit_code() == 0


def test_ridge_remaps_to_gate_off(fixture_db: Path):
    r = run_policy_challenge(
        fixture_db,
        "risk.accum.hard_gates",
        against="ridge_reweight",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert r.against_id == "gate_off" or any(
        "gate_off" in n for n in r.notes
    )
    assert r.status != ChallengeStatus.BLOCKED_POLICY or "gate" in "\n".join(r.notes)


def test_cli_gate(fixture_db: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "run",
            "risk.accum.hard_gates",
            "--against",
            "gate_off",
            "--compatibility-id",
            FIXTURE_COMPATIBILITY_ID,
            "--no-artifact",
        ],
    )
    assert r.exit_code in (0, 2), r.stdout
    assert "risk.accum.hard_gates" in r.stdout or "BLOCKED" in r.stdout
    assert "KEEP_DISPLAY" not in r.stdout
