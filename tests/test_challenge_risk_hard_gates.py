"""risk.accum.hard_gates — gate metric from schema-15 risk.gate_evaluations."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.engines import list_engines
from ml_saham.challenge.panel_gates import (
    GatePanelRow,
    extract_gate_components,
    extract_gate_decision,
)
from ml_saham.challenge.policies.registry import load_policy, load_policy_adapter
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.scorers import (
    GATE_DECISION_QUALITY_CONTRACT_ID,
    gate_decision_quality,
    mean_excess_allowed,
    score_gate_off,
    score_production,
)
from ml_saham.challenge.types import ChallengeStatus
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "gate.db", min_bars=120)


def _window_payload(
    evaluations: list[dict],
    *,
    unevaluable: list[str] | None = None,
    gate_triggered: str | None = None,
) -> dict:
    return {
        "ticker": "X",
        "session_date": "2024-01-01",
        "canonical_window": 7,
        "features_by_window": {
            "7": {
                "trade_setup": {
                    "action": "BLOCKED_STRUCTURAL",
                    "blocking_gates": [gate_triggered] if gate_triggered else [],
                },
                "risk": {
                    "gate_triggered": gate_triggered,
                    "unevaluable_gates": unevaluable or [],
                    "gate_evaluations": evaluations,
                },
            }
        },
    }


def test_policy_and_engines():
    pol = load_policy("risk.accum.hard_gates")
    assert pol.score_kind == "gate_block"
    assert pol.panel_kind == "accum_gates"
    assert pol.version == "v2"
    adapter = load_policy_adapter("risk.accum.hard_gates")
    assert adapter.adapter_version == "v2"
    assert adapter.conformance_id == "golden.risk.accum.hard_gates.v2"
    eng = {e["engine_id"]: e for e in list_engines()}
    assert "risk" in eng
    assert "risk.accum.hard_gates" in eng["risk"]["policies"]["accum"]
    assert "signal" in eng
    assert "signal.accum.raw_score" in eng["signal"]["policies"]["accum"]


def test_extract_from_gate_evaluations_triggered():
    pol = load_policy("risk.accum.hard_gates")
    payload = _window_payload(
        [
            {
                "gate": "BandarGate",
                "outcome": "triggered",
                "triggered": True,
            },
            {
                "gate": "LiquidityGate",
                "outcome": "pass",
                "triggered": False,
            },
        ],
        gate_triggered="BandarGate",
    )
    comps = extract_gate_components(payload, pol)
    assert comps is not None
    assert comps["bandar_gate"] == 1.0
    assert comps["liquidity_gate"] == 0.0
    decision = extract_gate_decision(payload, pol)
    assert decision is not None
    assert decision[1] == ("bandar_gate",)


def test_extract_gates_from_adr056_features_by_window():
    """Live captures nest risk audit under features_by_window — not root payload."""
    from tests.fixtures.golden import load_golden

    pol = load_policy("risk.accum.hard_gates")
    payload = load_golden("risk_adr056_trade_setup.json")
    assert "trade_setup" not in payload
    comps = extract_gate_components(payload, pol)
    assert comps is not None
    assert comps["free_float_gate"] == 1.0
    assert comps["bandar_gate"] == 1.0
    assert comps["liquidity_gate"] == 0.0
    # empty payload without risk audit must not invent all-clear
    assert extract_gate_components({"ticker": "X"}, pol) is None


def test_outcome_mapping_blocked_and_clear():
    """triggered/blocked_on_missing -> 1.0; pass/skipped/not_evaluated -> 0.0."""
    pol = load_policy("risk.accum.hard_gates")
    payload = _window_payload(
        [
            {"gate": "FundamentalGate", "outcome": "triggered", "triggered": True},
            {"gate": "BandarGate", "outcome": "blocked_on_missing", "triggered": True},
            {"gate": "LiquidityGate", "outcome": "pass", "triggered": False},
            {"gate": "FreeFloatGate", "outcome": "skipped", "triggered": False},
            {
                "gate": "TechnicalGate",
                "outcome": "not_evaluated",
                "triggered": None,
            },
        ]
    )
    comps = extract_gate_components(payload, pol)
    assert comps is not None
    assert comps["fundamental_gate"] == 1.0
    assert comps["bandar_gate"] == 1.0
    assert comps["liquidity_gate"] == 0.0
    assert comps["free_float_gate"] == 0.0
    assert comps["technical_gate"] == 0.0


def test_aggregate_unevaluable_block_is_not_genuine_fundamental_trigger():
    """Counterexample: gate_triggered=FundamentalGate but outcome=skipped -> 0.0."""
    pol = load_policy("risk.accum.hard_gates")
    payload = _window_payload(
        [
            {
                "gate": "FundamentalGate",
                "outcome": "skipped",
                "triggered": False,
            }
        ],
        unevaluable=["FundamentalGate"],
        gate_triggered="FundamentalGate",
    )
    # Coarse companion would have said fundamental blocked; audit says skipped.
    assert payload["features_by_window"]["7"]["trade_setup"]["blocking_gates"] == [
        "FundamentalGate"
    ]
    comps = extract_gate_components(payload, pol)
    assert comps is not None
    assert comps["fundamental_gate"] == 0.0
    assert all(v == 0.0 for v in comps.values())


def test_no_first_enabled_gate_fallback_on_blocked_action():
    """Blocked action without extractable audit must not invent a gate fire."""
    pol = load_policy("risk.accum.hard_gates")
    # Historical coarse shape only — no risk.gate_evaluations.
    legacy = {
        "trade_setup": {
            "action": "BLOCKED_STRUCTURAL",
            "blocking_gates": [],
        }
    }
    assert extract_gate_components(legacy, pol) is None
    window_only_ts = {
        "features_by_window": {
            "7": {
                "trade_setup": {
                    "action": "BLOCKED",
                    "blocking_gates": [],
                }
            }
        }
    }
    assert extract_gate_components(window_only_ts, pol) is None


def test_malformed_gate_evaluations_fail_closed():
    pol = load_policy("risk.accum.hard_gates")
    bad_type = {
        "features_by_window": {"7": {"risk": {"gate_evaluations": "not-a-list"}}}
    }
    assert extract_gate_components(bad_type, pol) is None
    bad_outcome = _window_payload(
        [{"gate": "BandarGate", "outcome": "mystery", "triggered": True}]
    )
    assert extract_gate_components(bad_outcome, pol) is None
    bad_row = _window_payload([{"gate": "BandarGate"}])  # missing outcome
    assert extract_gate_components(bad_row, pol) is None


def test_mean_excess_allowed_and_gate_off():
    from ml_saham.challenge.panel import PanelRow

    pol = load_policy("risk.accum.hard_gates")
    rows = [
        PanelRow(
            "A", "2024-01-01", {"bandar_gate": 1.0, "liquidity_gate": 0.0}, {10: -0.05}
        ),
        PanelRow(
            "B", "2024-01-01", {"bandar_gate": 0.0, "liquidity_gate": 0.0}, {10: 0.02}
        ),
        PanelRow(
            "C", "2024-01-02", {"bandar_gate": 0.0, "liquidity_gate": 0.0}, {10: 0.01}
        ),
        PanelRow(
            "D", "2024-01-02", {"bandar_gate": 0.0, "liquidity_gate": 1.0}, {10: -0.04}
        ),
    ]
    prod = score_production(rows, pol)
    off = score_gate_off(rows, pol)
    assert prod == [0.0, 1.0, 1.0, 0.0]
    assert off == [1.0, 1.0, 1.0, 1.0]
    m_prod, br, n_open = mean_excess_allowed(rows, prod, 10)
    assert br == 0.5
    assert n_open == 2
    assert m_prod == pytest.approx(0.015)


def test_gate_decision_quality_books_and_attribution():
    rows = [
        GatePanelRow(
            "A",
            "2024-01-01",
            {"bandar_gate": 1.0, "liquidity_gate": 1.0, "fundamental_gate": 0.0},
            {10: 0.04},
            ordered_blockers=("liquidity_gate", "bandar_gate"),
        ),
        GatePanelRow(
            "B",
            "2024-01-02",
            {"bandar_gate": 0.0, "liquidity_gate": 0.0, "fundamental_gate": 1.0},
            {10: -0.03},
            ordered_blockers=("fundamental_gate",),
        ),
        GatePanelRow(
            "C",
            "2024-01-03",
            {"bandar_gate": 0.0, "liquidity_gate": 0.0, "fundamental_gate": 0.0},
            {10: -0.02},
        ),
        GatePanelRow(
            "D",
            "2024-01-04",
            {"bandar_gate": 0.0, "liquidity_gate": 0.0, "fundamental_gate": 0.0},
            {10: 0.05},
        ),
        GatePanelRow(
            "E",
            "2024-01-05",
            {"bandar_gate": 1.0, "liquidity_gate": 0.0, "fundamental_gate": 0.0},
            {},
            ordered_blockers=("bandar_gate",),
        ),
    ]
    quality = gate_decision_quality(
        rows,
        [0.0, 0.0, 1.0, 1.0, 0.0],
        10,
        active_gate_keys=("bandar_gate", "liquidity_gate", "fundamental_gate"),
    )
    assert quality["contract_id"] == GATE_DECISION_QUALITY_CONTRACT_ID
    assert quality["n_labeled"] == 4
    assert quality["allowed_book"] == {
        "n": 2,
        "mean_excess": pytest.approx(0.015),
        "median_excess": pytest.approx(0.015),
    }
    assert quality["blocked_book"] == {
        "n": 2,
        "mean_excess": pytest.approx(0.005),
        "median_excess": pytest.approx(0.005),
    }
    assert quality["false_blocks"] == {"n": 1, "rate_of_blocked": 0.5}
    assert quality["harmful_allows"] == {"n": 1, "rate_of_allowed": 0.5}
    attribution = quality["gate_attribution"]
    assert attribution["first_blocker"]["liquidity_gate"]["n"] == 1
    assert attribution["first_blocker"]["fundamental_gate"]["n"] == 1
    assert attribution["overlapping_blockers"]["bandar_gate"]["n"] == 1
    assert attribution["multi_gate_blocked_n"] == 1

    gate_off = gate_decision_quality(
        rows, [1.0] * len(rows), 10, active_gate_keys=()
    )
    assert gate_off["blocked_book"]["n"] == 0
    assert gate_off["false_blocks"]["rate_of_blocked"] is None
    assert gate_off["harmful_allows"]["rate_of_allowed"] == 0.5

    with pytest.raises(ValueError, match="score must be finite"):
        gate_decision_quality(rows[:1], [float("nan")], 10, active_gate_keys=())


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
    assert (
        "KEEP/DEMOTE" in text or "not sleeve" in text.lower() or "gate" in text.lower()
    )
    # not presented as factor KEEP
    assert "Factor validity" not in text
    if r.status not in (ChallengeStatus.BLOCKED_DATA, ChallengeStatus.BLOCKED_POLICY):
        assert r.weights.get("decision_type") == "gate"
        assert (
            r.horizon_metrics["decision_quality_contract_id"]
            == GATE_DECISION_QUALITY_CONTRACT_ID
        )
        primary = r.horizon_metrics["decision_quality"]["10"]
        assert primary["baseline"]["n_labeled"] > 0
        assert primary["against"]["blocked_book"]["n"] == 0
        assert all("decision_quality_baseline" in fold for fold in r.fold_metrics)
        assert "Decision quality" in text
        assert "quality_base" in text
        assert "Descriptive only" in r.summary_md

        from ml_saham.challenge.artifacts import (
            challenge_content_digest,
            challenge_result_export_payload,
        )

        export = challenge_result_export_payload(r)
        assert export["horizon_metrics"]["decision_quality_contract_id"] == (
            GATE_DECISION_QUALITY_CONTRACT_ID
        )
        assert export["content_digest"] == challenge_content_digest(export)
        export["horizon_metrics"]["decision_quality"]["10"]["baseline"][
            "false_blocks"
        ]["n"] += 1
        assert export["content_digest"] != challenge_content_digest(export)
        assert r.exit_code() == 0


def test_ridge_remaps_to_gate_off(fixture_db: Path):
    r = run_policy_challenge(
        fixture_db,
        "risk.accum.hard_gates",
        against="ridge_reweight",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert r.against_id == "gate_off" or any("gate_off" in n for n in r.notes)
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
