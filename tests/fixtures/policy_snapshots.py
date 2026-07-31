"""Upstream-shaped production policy snapshots for ml-saham fixtures."""

from __future__ import annotations

import hashlib
import sqlite3

from ml_saham.challenge.production_policy_snapshots import (
    LEARNING_OBSERVATION_CONTRACT,
    POLICY_VERSION,
    PRODUCER_OBSERVATION_CONTRACT,
    PURPOSE,
    REQUIRED_POLICIES,
    SNAPSHOT_CONTRACT,
    _stable_snapshot_id,
    canonical_json,
)

MATERIAL_HASH = "sha256:" + "cd" * 32


def _payload(policy_id: str, decision_type: str, semantic: str) -> dict:
    payload = {
        "policy_id": policy_id,
        "policy_version": POLICY_VERSION,
        "decision_type": decision_type,
        "semantic_engine_contract_id": semantic,
        "output_scale": {"min": 0.0, "max": 100.0},
    }
    if policy_id == "screener.accum.score_weights":
        payload["components"] = [
            {"key": "consistency", "enabled": True, "weight": 33.3},
            {"key": "streak", "enabled": True, "weight": 25.0},
            {"key": "vwap_discount", "enabled": True, "weight": 16.7},
            {"key": "foreign_flow_ratio", "enabled": True, "weight": 8.3},
            {"key": "rsi_headroom", "enabled": True, "weight": 8.3},
            {"key": "bci", "enabled": True, "cluster_points": 12.5},
        ]
    elif policy_id == "signal.accum.evidence_group_weights":
        payload["components"] = [
            {"key": "setup_quality", "enabled": True, "weight": 0.6},
            {"key": "flow_confirmation", "enabled": True, "weight": 0.4},
        ]
    elif policy_id == "signal.accum.flags":
        payload["components"] = [
            {"key": "valuation_stretched", "enabled": True, "score_penalty": 10}
        ]
    elif policy_id == "signal.accum.classification":
        payload["thresholds"] = {"strong_min_score": 70, "moderate_min_score": 45}
    elif policy_id == "risk.accum.hard_gates":
        payload["components"] = [
            {"key": "bandar_gate", "enabled": True},
            {"key": "liquidity_gate", "enabled": True},
            {"key": "fundamental_gate", "enabled": True},
            {"key": "free_float_gate", "enabled": True},
            {"key": "technical_gate", "enabled": True},
        ]
        payload["output_scale"] = {"min": 0.0, "max": 1.0}
    elif policy_id == "screener.accum.hard_filters":
        payload["formula_id"] = "accumulation_screen.first_match_hard_filters.v1"
        payload["first_match_order"] = [
            "market_cap",
            "piotroski",
            "accum_score",
            "signal_score",
        ]
        payload["filters"] = {
            "market_cap": {"enabled": False, "floor_idr": 0},
            "piotroski": {"enabled": False, "floor": 0},
            "accum_score": {"enabled": True, "floor": 0.0},
            "signal_score": {"enabled": False, "floor": 45.0},
        }
        payload["output_scale"] = {"min": 0.0, "max": 1.0}
    else:
        payload["identity_only"] = True
        payload["formula_id"] = None
    return payload


def insert_verified_policy_snapshots(
    conn: sqlite3.Connection,
    compatibility_id: str,
) -> None:
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
    for policy_id, (decision_type, semantic) in REQUIRED_POLICIES.items():
        payload_json = canonical_json(_payload(policy_id, decision_type, semantic))
        identity = {
            "purpose": PURPOSE,
            "learning_observation_contract_id": LEARNING_OBSERVATION_CONTRACT,
            "producer_observation_contract": PRODUCER_OBSERVATION_CONTRACT,
            "compatibility_id": compatibility_id,
            "policy_id": policy_id,
        }
        conn.execute(
            "INSERT INTO learning_policy_snapshots VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                _stable_snapshot_id({**identity, "contract_id": SNAPSHOT_CONTRACT}),
                1,
                SNAPSHOT_CONTRACT,
                PURPOSE,
                LEARNING_OBSERVATION_CONTRACT,
                PRODUCER_OBSERVATION_CONTRACT,
                compatibility_id,
                policy_id,
                POLICY_VERSION,
                decision_type,
                semantic,
                MATERIAL_HASH,
                payload_json,
                hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                "ai-saham@test+git:deadbeef",
                "2026-07-31T12:00:00+00:00",
            ),
        )
