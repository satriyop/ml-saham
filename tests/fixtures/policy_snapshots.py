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
        payload["observation_result_fields"] = {
            "gate_evaluations": "features_by_window.7.risk.gate_evaluations",
            "blocking_gates": "features_by_window.7.trade_setup.blocking_gates",
            "risk_status": "features_by_window.7.candidate.risk_status",
        }
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
    elif policy_id == "risk.accum.unevaluable_policy":
        payload.update(
            {
                "formula_id": "assess_risk_gate_evaluator.evaluate.unevaluable_aggregate.v1",
                "scope": "aggregate_risk_assessment",
                "action": "surface",
                "blocks": False,
                "block_confidence": 50,
                "observation_result_fields": {
                    "unevaluable_gates": "features_by_window.7.risk.unevaluable_gates",
                    "gate_evaluations": "features_by_window.7.risk.gate_evaluations",
                },
            }
        )
    elif policy_id == "signal.accum.decision_policy":
        regimes = ("NEUTRAL", "RISK_OFF", "RISK_ON", "VOLATILE")
        payload.update(
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
                    for regime in regimes
                },
                "setup_regime_policy": {},
                "setup_regime_actions": {"allowed": {"max_decision": "ENTER"}},
                "regime_confidence_min_enter": 0.35,
                "regime_transitioning_cap_enter": True,
                "closed_vocabularies": {
                    "regimes": list(regimes),
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
