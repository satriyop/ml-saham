"""Verified ai-saham production policy snapshot consumer contract."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from ml_saham.challenge.policies.registry import load_policy_adapter
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.production_policy_snapshots import (
    LEARNING_OBSERVATION_CONTRACT,
    POLICY_VERSION,
    PRODUCER_OBSERVATION_CONTRACT,
    PURPOSE,
    REQUIRED_POLICIES,
    SNAPSHOT_CONTRACT,
    PolicySnapshotError,
    _stable_snapshot_id,
    canonical_json,
    compose_execution_policy,
    load_verified_snapshot_set,
)
from ml_saham.challenge.scorers import score_production

COMPATIBILITY_ID = "sha256:" + "ab" * 32
MATERIAL_HASH = "sha256:" + "cd" * 32


def test_runtime_adapter_specs_contain_no_copied_production_material():
    root = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ml_saham"
        / "challenge"
        / "policies"
    )
    paths = sorted(root.glob("*accum*.adapter.v1.json"))
    assert len(paths) == 7
    assert len(REQUIRED_POLICIES) == 9
    assert {
        "risk.accum.unevaluable_policy",
        "signal.accum.decision_policy",
    } <= set(REQUIRED_POLICIES)
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert not ({"hash", "source", "source_ref", "max_score"} & set(data))
        for component in data.get("components") or []:
            assert not ({"weight", "enabled", "note"} & set(component))


def test_identity_only_gate_rows_have_no_fabricated_challenge_adapters() -> None:
    for policy_id in (
        "risk.accum.unevaluable_policy",
        "signal.accum.decision_policy",
    ):
        with pytest.raises(KeyError):
            load_policy_adapter(policy_id)


def _payload(policy_id: str, decision_type: str, semantic: str) -> dict:
    common = {
        "policy_id": policy_id,
        "policy_version": POLICY_VERSION,
        "decision_type": decision_type,
        "semantic_engine_contract_id": semantic,
        "output_scale": {"min": 0.0, "max": 100.0},
    }
    if policy_id == "screener.accum.score_weights":
        common["components"] = [
            {"key": "consistency", "enabled": True, "weight": 33.3},
            {"key": "bci", "enabled": True, "cluster_points": 12.5},
        ]
    elif policy_id == "signal.accum.evidence_group_weights":
        common["components"] = [
            {"key": "setup_quality", "enabled": True, "weight": 0.6},
            {"key": "flow_confirmation", "enabled": True, "weight": 0.4},
        ]
    elif policy_id == "signal.accum.flags":
        common["components"] = [
            {
                "key": "valuation_stretched",
                "enabled": True,
                "score_penalty": 10,
            }
        ]
    elif policy_id == "signal.accum.classification":
        common["thresholds"] = {"strong_min_score": 70, "moderate_min_score": 45}
    elif policy_id == "risk.accum.hard_gates":
        common["components"] = [{"key": "fundamental_gate", "enabled": True}]
        common["output_scale"] = {"min": 0.0, "max": 1.0}
    elif policy_id == "screener.accum.hard_filters":
        common["formula_id"] = "accumulation_screen.first_match_hard_filters.v1"
        common["first_match_order"] = [
            "market_cap",
            "piotroski",
            "accum_score",
            "signal_score",
        ]
        common["filters"] = {
            "market_cap": {"enabled": False, "floor_idr": 0},
            "piotroski": {"enabled": False, "floor": 0},
            "accum_score": {"enabled": True, "floor": 0.0},
            "signal_score": {"enabled": False, "floor": 45.0},
        }
        common["output_scale"] = {"min": 0.0, "max": 1.0}
    elif policy_id == "signal.accum.raw_score":
        common["identity_only"] = True
        common["formula_id"] = None
    elif policy_id == "risk.accum.unevaluable_policy":
        common.update(
            {
                "formula_id": "assess_risk_gate_evaluator.evaluate.unevaluable_aggregate.v1",
                "scope": "aggregate_risk_assessment",
                "action": "surface",
                "blocks": False,
                "block_confidence": 50,
            }
        )
    elif policy_id == "signal.accum.decision_policy":
        common.update(
            {
                "formula_id": "decision_policy_service.resolve.v1",
                "scope": "canonical_accum_signal_entry_quality_and_constraints",
                "regime_policy": {
                    regime: {
                        "enter_allowed": regime in {"RISK_ON", "NEUTRAL"},
                        "max_decision": (
                            "ENTER" if regime in {"RISK_ON", "NEUTRAL"} else "WATCH"
                        ),
                        "regime_size_multiplier": 1.0,
                        "enter_threshold": 70,
                        "watch_threshold": 45,
                        "min_signal_authority_coverage": 0.7,
                    }
                    for regime in ("NEUTRAL", "RISK_OFF", "RISK_ON", "VOLATILE")
                },
                "setup_regime_policy": {
                    "foreign_bounce": {
                        regime: "allowed"
                        for regime in ("NEUTRAL", "RISK_OFF", "RISK_ON", "VOLATILE")
                    }
                },
                "setup_regime_actions": {
                    "allowed": {"max_decision": "ENTER"},
                },
                "regime_confidence_min_enter": 0.35,
                "regime_transitioning_cap_enter": True,
                "closed_vocabularies": {
                    "regimes": ["NEUTRAL", "RISK_OFF", "RISK_ON", "VOLATILE"],
                    "decisions": ["AVOID", "ENTER", "WATCH"],
                },
                "missing_data": {
                    "absent_setup_family": "no_setup_specific_action",
                    "absent_market_context_regime": "RISK_ON",
                },
                "observation_result_fields": {
                    "entry_quality": "features_by_window.7.signal.assessment.entry_quality",
                    "decision_constraints": (
                        "features_by_window.7.signal.assessment.decision_constraints"
                    ),
                },
            }
        )
    return common


def _create_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE learning_policy_snapshots (
            snapshot_id TEXT, schema_version INTEGER, contract_id TEXT,
            purpose TEXT, learning_observation_contract_id TEXT,
            producer_observation_contract TEXT, compatibility_id TEXT,
            policy_id TEXT, policy_version TEXT, decision_type TEXT,
            semantic_engine_contract_id TEXT, material_config_hash TEXT,
            canonical_payload_json TEXT, payload_digest TEXT,
            source_revision TEXT, created_at TEXT
        )
        """
    )


def _insert_set(
    conn: sqlite3.Connection, *, corrupt_digest_for: str | None = None
) -> None:
    for policy_id, (decision_type, semantic) in REQUIRED_POLICIES.items():
        payload_json = canonical_json(_payload(policy_id, decision_type, semantic))
        digest = hashlib.sha256(payload_json.encode()).hexdigest()
        if policy_id == corrupt_digest_for:
            digest = "0" * 64
        identity = {
            "purpose": PURPOSE,
            "learning_observation_contract_id": LEARNING_OBSERVATION_CONTRACT,
            "producer_observation_contract": PRODUCER_OBSERVATION_CONTRACT,
            "compatibility_id": COMPATIBILITY_ID,
            "policy_id": policy_id,
        }
        row = {
            **identity,
            "contract_id": SNAPSHOT_CONTRACT,
        }
        conn.execute(
            "INSERT INTO learning_policy_snapshots VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                _stable_snapshot_id(row),
                1,
                SNAPSHOT_CONTRACT,
                PURPOSE,
                LEARNING_OBSERVATION_CONTRACT,
                PRODUCER_OBSERVATION_CONTRACT,
                COMPATIBILITY_ID,
                policy_id,
                POLICY_VERSION,
                decision_type,
                semantic,
                MATERIAL_HASH,
                payload_json,
                digest,
                "ai-saham@test+git:deadbeef",
                "2026-07-31T12:00:00+00:00",
            ),
        )


def test_canonical_json_matches_upstream_non_ascii_null_bool_float_vector() -> None:
    payload = {"z": None, "aktif": True, "nilai": 1.25, "nama": "saham é"}
    assert canonical_json(payload) == (
        '{"aktif":true,"nama":"saham \\u00e9","nilai":1.25,"z":null}'
    )


def test_loads_closed_verified_set_and_composes_production_material(tmp_path) -> None:
    path = tmp_path / "verified.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _create_table(conn)
    _insert_set(conn)

    snapshots = load_verified_snapshot_set(conn, COMPATIBILITY_ID)
    assert set(snapshots) == set(REQUIRED_POLICIES)
    policy = compose_execution_policy(
        snapshots["screener.accum.score_weights"],
        load_policy_adapter("screener.accum.score_weights"),
    )
    assert policy.hash == snapshots[policy.policy_id].payload_digest
    assert policy.observation_compatibility_id == COMPATIBILITY_ID
    assert policy.weight_map()["consistency"] == 33.3
    assert policy.weight_map()["bci"] == 12.5
    assert "sector_breadth" not in policy.weight_map()


def test_missing_or_bad_snapshot_fails_closed(tmp_path) -> None:
    conn = sqlite3.connect(tmp_path / "bad.db")
    conn.row_factory = sqlite3.Row
    _create_table(conn)
    _insert_set(conn, corrupt_digest_for="signal.accum.flags")
    with pytest.raises(PolicySnapshotError, match="digest mismatch"):
        load_verified_snapshot_set(conn, COMPATIBILITY_ID)

    conn.execute(
        "DELETE FROM learning_policy_snapshots WHERE policy_id = ?",
        ("signal.accum.flags",),
    )
    with pytest.raises(PolicySnapshotError, match="exactly nine"):
        load_verified_snapshot_set(conn, COMPATIBILITY_ID)


def test_decision_policy_formula_contract_mismatch_fails_closed(tmp_path) -> None:
    conn = sqlite3.connect(tmp_path / "bad-decision-formula.db")
    conn.row_factory = sqlite3.Row
    _create_table(conn)
    _insert_set(conn)
    row = conn.execute(
        "SELECT canonical_payload_json FROM learning_policy_snapshots WHERE policy_id = ?",
        ("signal.accum.decision_policy",),
    ).fetchone()
    payload = json.loads(row[0])
    payload["formula_id"] = "wrong.formula.v1"
    payload_json = canonical_json(payload)
    conn.execute(
        "UPDATE learning_policy_snapshots SET canonical_payload_json = ?, payload_digest = ? "
        "WHERE policy_id = ?",
        (
            payload_json,
            hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            "signal.accum.decision_policy",
        ),
    )

    with pytest.raises(PolicySnapshotError, match="formula_id"):
        load_verified_snapshot_set(conn, COMPATIBILITY_ID)


def test_decision_policy_boolean_threshold_fails_closed(tmp_path) -> None:
    conn = sqlite3.connect(tmp_path / "bad-decision-threshold.db")
    conn.row_factory = sqlite3.Row
    _create_table(conn)
    _insert_set(conn)
    row = conn.execute(
        "SELECT canonical_payload_json FROM learning_policy_snapshots WHERE policy_id = ?",
        ("signal.accum.decision_policy",),
    ).fetchone()
    payload = json.loads(row[0])
    payload["regime_confidence_min_enter"] = True
    payload_json = canonical_json(payload)
    conn.execute(
        "UPDATE learning_policy_snapshots SET canonical_payload_json = ?, payload_digest = ? "
        "WHERE policy_id = ?",
        (
            payload_json,
            hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            "signal.accum.decision_policy",
        ),
    )

    with pytest.raises(PolicySnapshotError, match="must be numeric"):
        load_verified_snapshot_set(conn, COMPATIBILITY_ID)


def test_composed_adapters_reproduce_declared_golden_vectors(tmp_path) -> None:
    conn = sqlite3.connect(tmp_path / "golden.db")
    conn.row_factory = sqlite3.Row
    _create_table(conn)
    _insert_set(conn)
    snapshots = load_verified_snapshot_set(conn, COMPATIBILITY_ID)

    def policy(policy_id: str):
        adapter = load_policy_adapter(policy_id)
        assert adapter.conformance_id == f"golden.{policy_id}.v1"
        assert adapter.supported_challengers
        return compose_execution_policy(snapshots[policy_id], adapter)

    row = PanelRow(
        "BBCA",
        "2026-07-31",
        {
            "production_observed_score": 42.5,
            "consistency": 33.3,
            "bci": 12.5,
        },
        {10: 0.01},
    )
    assert score_production([row], policy("screener.accum.score_weights")) == [42.5]

    raw = PanelRow("BBCA", "2026-07-31", {"production_raw_score": 61.25}, {10: 0.01})
    assert score_production([raw], policy("signal.accum.raw_score")) == [61.25]

    evidence = PanelRow(
        "BBCA",
        "2026-07-31",
        {"setup_quality": 60.0, "flow_confirmation": 40.0},
        {10: 0.01},
    )
    assert score_production(
        [evidence], policy("signal.accum.evidence_group_weights")
    ) == [52.0]

    flagged = PanelRow(
        "BBCA",
        "2026-07-31",
        {"production_raw_score": 80.0, "valuation_stretched": 1.0},
        {10: 0.01},
    )
    assert score_production([flagged], policy("signal.accum.flags")) == [70.0]

    classified = PanelRow(
        "BBCA", "2026-07-31", {"production_raw_score": 70.0}, {10: 0.01}
    )
    assert score_production([classified], policy("signal.accum.classification")) == [
        100.0
    ]

    gated = PanelRow("BBCA", "2026-07-31", {"fundamental_gate": 1.0}, {10: 0.01})
    assert score_production([gated], policy("risk.accum.hard_gates")) == [0.0]


def test_unknown_extra_policy_row_fails_closed_for_v4(tmp_path) -> None:
    conn = sqlite3.connect(tmp_path / "extra.db")
    conn.row_factory = sqlite3.Row
    _create_table(conn)
    _insert_set(conn)
    conn.execute(
        "INSERT INTO learning_policy_snapshots VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "ignored",
            999,
            "future.contract",
            PURPOSE,
            "future.observation",
            "future.producer",
            COMPATIBILITY_ID,
            "future.policy",
            "v9",
            "label",
            "future.semantic",
            MATERIAL_HASH,
            "{}",
            "ignored",
            "future",
            "2026-07-31T12:00:00+00:00",
        ),
    )
    with pytest.raises(PolicySnapshotError, match="extra=.*future.policy"):
        load_verified_snapshot_set(conn, COMPATIBILITY_ID)


def test_historical_v1_six_row_cohort_is_not_active_production(tmp_path) -> None:
    conn = sqlite3.connect(tmp_path / "historical-v1.db")
    conn.row_factory = sqlite3.Row
    _create_table(conn)
    for policy_id, (decision_type, semantic) in REQUIRED_POLICIES.items():
        if policy_id in {
            "screener.accum.hard_filters",
            "risk.accum.unevaluable_policy",
            "signal.accum.decision_policy",
        }:
            continue
        conn.execute(
            "INSERT INTO learning_policy_snapshots VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "historical-" + policy_id,
                1,
                "production_policy_snapshot.v1",
                PURPOSE,
                LEARNING_OBSERVATION_CONTRACT,
                PRODUCER_OBSERVATION_CONTRACT,
                COMPATIBILITY_ID,
                policy_id,
                POLICY_VERSION,
                decision_type,
                semantic,
                MATERIAL_HASH,
                canonical_json(_payload(policy_id, decision_type, semantic)),
                "historical",
                "ai-saham@historical",
                "2026-07-30T12:00:00+00:00",
            ),
        )
    with pytest.raises(PolicySnapshotError, match="exactly nine"):
        load_verified_snapshot_set(conn, COMPATIBILITY_ID)


def test_hard_filter_adapter_stays_blocked_until_tournament_conformance(
    tmp_path,
) -> None:
    conn = sqlite3.connect(tmp_path / "hard-filter.db")
    conn.row_factory = sqlite3.Row
    _create_table(conn)
    _insert_set(conn)
    snapshots = load_verified_snapshot_set(conn, COMPATIBILITY_ID)
    adapter = load_policy_adapter("screener.accum.hard_filters")
    assert adapter.conformance_id == ""
    with pytest.raises(PolicySnapshotError, match="lacks conformance evidence"):
        compose_execution_policy(
            snapshots["screener.accum.hard_filters"],
            adapter,
        )
