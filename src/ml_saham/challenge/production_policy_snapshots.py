"""Read and verify ai-saham production-policy snapshots without sibling imports."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections.abc import Mapping
from typing import Any

from ml_saham.challenge.types import (
    ChallengeExecutionPolicy,
    ChallengePolicyAdapter,
    ComponentWeight,
    VerifiedProductionPolicySnapshot,
)
from ml_saham.data.aisaham_read import table_columns, table_exists

SNAPSHOT_CONTRACT = "production_policy_snapshot.v4"
PURPOSE = "ACCUMULATION_DISCOVERY"
LEARNING_OBSERVATION_CONTRACT = "learning_observation.accumulation_discovery.v2"
PRODUCER_OBSERVATION_CONTRACT = "accumulation-discovery.v2"
POLICY_VERSION = "v1"
MATERIAL_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

REQUIRED_POLICIES: dict[str, tuple[str, str]] = {
    "screener.accum.score_weights": ("score", "accum_score_policy.v1"),
    "signal.accum.evidence_group_weights": ("score", "signal.semantic_engine.v1.5"),
    "signal.accum.flags": ("score", "signal.semantic_engine.v1.5"),
    "signal.accum.classification": ("score", "signal.semantic_engine.v1.5"),
    "risk.accum.hard_gates": ("gate", "risk.hard_gates.accum.v1"),
    "signal.accum.raw_score": ("score", "signal.semantic_engine.v1.5"),
    "screener.accum.hard_filters": ("gate", "screen.accum.hard_filters.v1"),
    "risk.accum.unevaluable_policy": ("gate", "risk.unevaluable_gate.accum.v1"),
    "signal.accum.decision_policy": ("gate", "signal.decision_policy.accum.v1"),
}

SNAPSHOT_COLUMNS = {
    "snapshot_id",
    "schema_version",
    "contract_id",
    "purpose",
    "learning_observation_contract_id",
    "producer_observation_contract",
    "compatibility_id",
    "policy_id",
    "policy_version",
    "decision_type",
    "semantic_engine_contract_id",
    "material_config_hash",
    "canonical_payload_json",
    "payload_digest",
    "source_revision",
    "created_at",
}


class PolicySnapshotError(ValueError):
    """Snapshot absence or verification failure; callers map to BLOCKED_POLICY."""


def _require_exact_value(
    payload: Mapping[str, Any], policy_id: str, key: str, expected: Any
) -> None:
    if payload.get(key) != expected:
        raise PolicySnapshotError(
            f"{policy_id}: payload {key!r} does not match {expected!r}"
        )


def _verify_risk_audit_result_fields(
    policy_id: str, payload: Mapping[str, Any]
) -> None:
    """Require schema-15 risk audit paths declared by ai-saham task 09."""
    fields = payload.get("observation_result_fields")
    if not isinstance(fields, Mapping):
        raise PolicySnapshotError(
            f"{policy_id}: observation_result_fields must be an object"
        )
    if policy_id == "risk.accum.unevaluable_policy":
        expected = {
            "unevaluable_gates": "features_by_window.7.risk.unevaluable_gates",
            "gate_evaluations": "features_by_window.7.risk.gate_evaluations",
        }
        if dict(fields) != expected:
            raise PolicySnapshotError(
                f"{policy_id}: observation_result_fields must bind risk audit paths"
            )
        return
    if policy_id == "risk.accum.hard_gates":
        gate_evals = fields.get("gate_evaluations")
        if gate_evals != "features_by_window.7.risk.gate_evaluations":
            raise PolicySnapshotError(
                f"{policy_id}: observation_result_fields.gate_evaluations "
                "must be features_by_window.7.risk.gate_evaluations"
            )
        # Coarse companions may remain; they are not sufficient alone.
        for companion in ("blocking_gates", "risk_status"):
            if companion in fields and not isinstance(fields[companion], str):
                raise PolicySnapshotError(
                    f"{policy_id}: observation_result_fields.{companion} must be a path string"
                )
        return


def _verify_identity_only_payload_contract(
    policy_id: str, payload: Mapping[str, Any]
) -> None:
    if policy_id == "risk.accum.unevaluable_policy":
        _require_exact_value(
            payload,
            policy_id,
            "formula_id",
            "assess_risk_gate_evaluator.evaluate.unevaluable_aggregate.v1",
        )
        _require_exact_value(payload, policy_id, "scope", "aggregate_risk_assessment")
        _verify_risk_audit_result_fields(policy_id, payload)
        return
    if policy_id == "risk.accum.hard_gates":
        _verify_risk_audit_result_fields(policy_id, payload)
        return
    if policy_id != "signal.accum.decision_policy":
        return

    _require_exact_value(
        payload,
        policy_id,
        "formula_id",
        "decision_policy_service.resolve.v1",
    )
    _require_exact_value(
        payload,
        policy_id,
        "scope",
        "canonical_accum_signal_entry_quality_and_constraints",
    )
    regimes = ("NEUTRAL", "RISK_OFF", "RISK_ON", "VOLATILE")
    decisions = ("AVOID", "ENTER", "WATCH")
    regime_policy = payload.get("regime_policy")
    if not isinstance(regime_policy, Mapping) or set(regime_policy) != set(regimes):
        raise PolicySnapshotError(f"{policy_id}: regime_policy is not the closed set")
    required_regime_fields = {
        "enter_allowed",
        "max_decision",
        "regime_size_multiplier",
        "enter_threshold",
        "watch_threshold",
        "min_signal_authority_coverage",
    }
    for regime in regimes:
        row = regime_policy[regime]
        if not isinstance(row, Mapping) or set(row) != required_regime_fields:
            raise PolicySnapshotError(
                f"{policy_id}: regime_policy.{regime} fields mismatch"
            )
        if type(row["enter_allowed"]) is not bool:
            raise PolicySnapshotError(
                f"{policy_id}: regime_policy.{regime}.enter_allowed must be boolean"
            )
        if row["max_decision"] not in decisions:
            raise PolicySnapshotError(
                f"{policy_id}: regime_policy.{regime}.max_decision is invalid"
            )
        for field in (
            "regime_size_multiplier",
            "watch_threshold",
            "min_signal_authority_coverage",
        ):
            if type(row[field]) not in (int, float):
                raise PolicySnapshotError(
                    f"{policy_id}: regime_policy.{regime}.{field} must be numeric"
                )
        enter_threshold = row["enter_threshold"]
        if enter_threshold is not None and type(enter_threshold) not in (int, float):
            raise PolicySnapshotError(
                f"{policy_id}: regime_policy.{regime}.enter_threshold "
                "must be numeric or null"
            )
    setup_regime_policy = payload.get("setup_regime_policy")
    if not isinstance(setup_regime_policy, Mapping):
        raise PolicySnapshotError(f"{policy_id}: setup_regime_policy must be an object")
    for family, by_regime in setup_regime_policy.items():
        if not isinstance(family, str) or not isinstance(by_regime, Mapping):
            raise PolicySnapshotError(
                f"{policy_id}: setup_regime_policy entries must be objects"
            )
        if set(by_regime) != set(regimes):
            raise PolicySnapshotError(
                f"{policy_id}: setup_regime_policy.{family} is not the closed regime set"
            )
        if any(not isinstance(action_name, str) for action_name in by_regime.values()):
            raise PolicySnapshotError(
                f"{policy_id}: setup_regime_policy.{family} actions must be strings"
            )
    setup_regime_actions = payload.get("setup_regime_actions")
    if not isinstance(setup_regime_actions, Mapping):
        raise PolicySnapshotError(
            f"{policy_id}: setup_regime_actions must be an object"
        )
    for action_name, action in setup_regime_actions.items():
        if not isinstance(action_name, str) or not isinstance(action, Mapping):
            raise PolicySnapshotError(
                f"{policy_id}: setup_regime_actions entries must be objects"
            )
        if set(action) != {"max_decision"} or action["max_decision"] not in decisions:
            raise PolicySnapshotError(
                f"{policy_id}: setup_regime_actions.{action_name} is invalid"
            )
    known_actions = set(setup_regime_actions)
    for family, by_regime in setup_regime_policy.items():
        unknown_actions = set(by_regime.values()) - known_actions
        if unknown_actions:
            raise PolicySnapshotError(
                f"{policy_id}: setup_regime_policy.{family} references unknown actions"
            )
    if type(payload.get("regime_confidence_min_enter")) not in (int, float):
        raise PolicySnapshotError(
            f"{policy_id}: regime_confidence_min_enter must be numeric"
        )
    if type(payload.get("regime_transitioning_cap_enter")) is not bool:
        raise PolicySnapshotError(
            f"{policy_id}: regime_transitioning_cap_enter must be boolean"
        )
    _require_exact_value(
        payload,
        policy_id,
        "closed_vocabularies",
        {"regimes": list(regimes), "decisions": list(decisions)},
    )
    _require_exact_value(
        payload,
        policy_id,
        "missing_data",
        {
            "absent_setup_family": "no_setup_specific_action",
            "absent_market_context_regime": "RISK_ON",
        },
    )
    _require_exact_value(
        payload,
        policy_id,
        "observation_result_fields",
        {
            "entry_quality": "features_by_window.7.signal.assessment.entry_quality",
            "decision_constraints": (
                "features_by_window.7.signal.assessment.decision_constraints"
            ),
        },
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PolicySnapshotError("canonical payload contains NaN or infinity")
        return value
    raise PolicySnapshotError(
        f"unsupported canonical JSON value: {type(value).__name__}"
    )


def canonical_json(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            _json_value(payload),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise PolicySnapshotError(f"invalid canonical payload: {exc}") from exc


def _stable_snapshot_id(row: Mapping[str, Any]) -> str:
    identity = {
        "purpose": row["purpose"],
        "learning_observation_contract_id": row["learning_observation_contract_id"],
        "producer_observation_contract": row["producer_observation_contract"],
        "compatibility_id": row["compatibility_id"],
        "policy_id": row["policy_id"],
    }
    material = canonical_json({"contract_id": SNAPSHOT_CONTRACT, "identity": identity})
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def stable_snapshot_id_for(
    *,
    compatibility_id: str,
    policy_id: str,
    purpose: str = PURPOSE,
    learning_observation_contract_id: str = LEARNING_OBSERVATION_CONTRACT,
    producer_observation_contract: str = PRODUCER_OBSERVATION_CONTRACT,
) -> str:
    """Recompute production ``snapshot_id`` from cohort + policy identity fields.

    Used by promote reopen validation when exports carry enough identity to
    check consistency without re-querying the upstream database.
    """
    return _stable_snapshot_id(
        {
            "purpose": purpose,
            "learning_observation_contract_id": learning_observation_contract_id,
            "producer_observation_contract": producer_observation_contract,
            "compatibility_id": compatibility_id,
            "policy_id": policy_id,
        }
    )


def _verify_row(
    row: sqlite3.Row, compatibility_id: str
) -> VerifiedProductionPolicySnapshot:
    data = dict(row)
    policy_id = str(data["policy_id"])
    expected = REQUIRED_POLICIES.get(policy_id)
    if expected is None:
        raise PolicySnapshotError(f"unsupported production policy_id={policy_id!r}")
    decision_type, semantic_contract = expected
    bindings = {
        "schema_version": (int(data["schema_version"]), 1),
        "contract_id": (str(data["contract_id"]), SNAPSHOT_CONTRACT),
        "purpose": (str(data["purpose"]), PURPOSE),
        "learning_observation_contract_id": (
            str(data["learning_observation_contract_id"]),
            LEARNING_OBSERVATION_CONTRACT,
        ),
        "producer_observation_contract": (
            str(data["producer_observation_contract"]),
            PRODUCER_OBSERVATION_CONTRACT,
        ),
        "compatibility_id": (str(data["compatibility_id"]), compatibility_id),
        "policy_version": (str(data["policy_version"]), POLICY_VERSION),
        "decision_type": (str(data["decision_type"]), decision_type),
        "semantic_engine_contract_id": (
            str(data["semantic_engine_contract_id"]),
            semantic_contract,
        ),
    }
    for field, (actual, wanted) in bindings.items():
        if actual != wanted:
            raise PolicySnapshotError(
                f"{policy_id}: {field}={actual!r} does not match {wanted!r}"
            )
    material_hash = str(data["material_config_hash"])
    if not MATERIAL_HASH_RE.fullmatch(material_hash):
        raise PolicySnapshotError(f"{policy_id}: malformed material_config_hash")
    raw_payload = str(data["canonical_payload_json"])
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PolicySnapshotError(
            f"{policy_id}: malformed canonical payload JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise PolicySnapshotError(f"{policy_id}: canonical payload must be an object")
    recanonical = canonical_json(payload)
    if recanonical != raw_payload:
        raise PolicySnapshotError(
            f"{policy_id}: canonical payload bytes do not match contract"
        )
    digest = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    if digest != str(data["payload_digest"]):
        raise PolicySnapshotError(f"{policy_id}: payload digest mismatch")
    if _stable_snapshot_id(data) != str(data["snapshot_id"]):
        raise PolicySnapshotError(f"{policy_id}: snapshot_id mismatch")
    for key, expected_value in (
        ("policy_id", policy_id),
        ("policy_version", POLICY_VERSION),
        ("decision_type", decision_type),
        ("semantic_engine_contract_id", semantic_contract),
    ):
        if payload.get(key) != expected_value:
            raise PolicySnapshotError(f"{policy_id}: payload metadata {key!r} mismatch")
    _verify_identity_only_payload_contract(policy_id, payload)
    if not str(data["source_revision"]).strip():
        raise PolicySnapshotError(f"{policy_id}: empty source_revision")
    return VerifiedProductionPolicySnapshot(
        snapshot_id=str(data["snapshot_id"]),
        schema_version=1,
        contract_id=SNAPSHOT_CONTRACT,
        purpose=PURPOSE,
        learning_observation_contract_id=LEARNING_OBSERVATION_CONTRACT,
        producer_observation_contract=PRODUCER_OBSERVATION_CONTRACT,
        compatibility_id=compatibility_id,
        policy_id=policy_id,
        policy_version=POLICY_VERSION,
        decision_type=decision_type,
        semantic_engine_contract_id=semantic_contract,
        material_config_hash=material_hash,
        canonical_payload_json=raw_payload,
        canonical_payload=payload,
        payload_digest=digest,
        source_revision=str(data["source_revision"]),
        created_at=str(data["created_at"]),
    )


def verify_export_snapshot_against_db(
    conn: sqlite3.Connection,
    *,
    compatibility_id: str,
    policy_id: str,
    snapshot_id: str,
    payload_digest: str,
) -> str | None:
    """Prove export identities match an immutable learning_policy_snapshots row.

    Returns an error string, or ``None`` when the digest/id/cohort/policy match
    a verified production row. Does not invent authority from format alone.
    """
    try:
        verified = load_verified_snapshot_set(conn, compatibility_id)
    except PolicySnapshotError as exc:
        return f"production identity invalid: authoritative snapshot set failed: {exc}"
    snap = verified.get(policy_id)
    if snap is None:
        return (
            "production identity invalid: policy_id="
            f"{policy_id!r} missing from verified snapshot set for cohort"
        )
    if snap.snapshot_id != snapshot_id:
        return (
            "production identity invalid: production_snapshot_id does not match "
            "authoritative learning_policy_snapshots.snapshot_id"
        )
    if snap.payload_digest != payload_digest:
        return (
            "production identity invalid: production_snapshot_digest does not match "
            "authoritative learning_policy_snapshots.payload_digest"
        )
    return None


def load_verified_snapshot_set(
    conn: sqlite3.Connection, compatibility_id: str
) -> dict[str, VerifiedProductionPolicySnapshot]:
    if not compatibility_id.strip():
        raise PolicySnapshotError("selected observation cohort has no compatibility_id")
    if not table_exists(conn, "learning_policy_snapshots"):
        raise PolicySnapshotError("learning_policy_snapshots table missing")
    missing_columns = SNAPSHOT_COLUMNS - table_columns(
        conn, "learning_policy_snapshots"
    )
    if missing_columns:
        raise PolicySnapshotError(
            "learning_policy_snapshots missing columns: "
            + ", ".join(sorted(missing_columns))
        )
    columns = ", ".join(sorted(SNAPSHOT_COLUMNS))
    rows = conn.execute(
        f"SELECT {columns} FROM learning_policy_snapshots "
        "WHERE purpose = ? AND compatibility_id = ? ORDER BY policy_id",
        (PURPOSE, compatibility_id),
    ).fetchall()
    found = {str(r["policy_id"]) for r in rows}
    if len(rows) != len(REQUIRED_POLICIES) or found != set(REQUIRED_POLICIES):
        missing = sorted(set(REQUIRED_POLICIES) - found)
        extra = sorted(found - set(REQUIRED_POLICIES))
        raise PolicySnapshotError(
            f"verified cohort requires exactly nine snapshots; found={len(rows)} "
            f"missing={missing} extra={extra}"
        )
    verified_rows = [_verify_row(row, compatibility_id) for row in rows]
    verified = {snapshot.policy_id: snapshot for snapshot in verified_rows}
    if set(verified) != set(REQUIRED_POLICIES):
        raise PolicySnapshotError(
            "snapshot cohort does not match the closed v4 policy set"
        )
    material_hashes = {snapshot.material_config_hash for snapshot in verified.values()}
    if len(material_hashes) != 1:
        raise PolicySnapshotError(
            "snapshot cohort has inconsistent material_config_hash values"
        )
    return verified


def _aliases(adapter: ChallengePolicyAdapter) -> dict[str, tuple[str, ...]]:
    return {c.key: c.aliases for c in adapter.components}


def _component(
    key: str, weight: float, enabled: bool, aliases: dict[str, tuple[str, ...]]
) -> ComponentWeight:
    return ComponentWeight(
        key=key, weight=weight, enabled=enabled, aliases=aliases.get(key, ())
    )


def compose_execution_policy(
    snapshot: VerifiedProductionPolicySnapshot,
    adapter: ChallengePolicyAdapter,
) -> ChallengeExecutionPolicy:
    if adapter.supported_policy_id != snapshot.policy_id:
        raise PolicySnapshotError("adapter policy_id does not match verified snapshot")
    if adapter.supported_snapshot_contract != snapshot.contract_id:
        raise PolicySnapshotError("adapter does not support snapshot contract")
    if (
        snapshot.semantic_engine_contract_id
        not in adapter.supported_semantic_engine_contract_ids
    ):
        raise PolicySnapshotError(
            f"adapter {adapter.adapter_id} does not support "
            f"{snapshot.semantic_engine_contract_id}"
        )
    if not adapter.conformance_id.strip():
        raise PolicySnapshotError(
            f"adapter {adapter.adapter_id} lacks conformance evidence"
        )
    if snapshot.policy_id == "screener.accum.hard_filters":
        probe_digest = adapter.conformance_behavioral_probe_digest
        compatibility_contract_id = (
            adapter.conformance_compatibility_contract_id
        )
        observation_schema_version = (
            adapter.conformance_observation_schema_version
        )
        if (
            len(probe_digest) != 64
            or not compatibility_contract_id
            or observation_schema_version is None
        ):
            raise PolicySnapshotError(
                "hard-filter adapter lacks behavioral cohort conformance binding"
            )
        material = canonical_json(
            {
                "contract_id": compatibility_contract_id,
                "behavioral_probe_digest": probe_digest,
                "policy_snapshot_payload_digest": snapshot.material_config_hash.removeprefix(
                    "sha256:"
                ),
                "observation_payload_schema_version": observation_schema_version,
            }
        )
        expected_compatibility_id = "sha256:" + hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()
        if snapshot.compatibility_id != expected_compatibility_id:
            raise PolicySnapshotError(
                "hard-filter adapter conformance does not bind selected behavioral cohort"
            )

    payload = snapshot.canonical_payload
    aliases = _aliases(adapter)
    components: list[ComponentWeight]
    if snapshot.policy_id == "signal.accum.raw_score":
        components = [
            ComponentWeight(key=c.key, weight=1.0, enabled=True, aliases=c.aliases)
            for c in adapter.components
        ]
    elif snapshot.policy_id == "signal.accum.classification":
        thresholds = payload.get("thresholds") or {}
        components = [
            _component("production_raw_score", 1.0, True, aliases),
            _component(
                "strong_min", float(thresholds["strong_min_score"]), True, aliases
            ),
            _component(
                "moderate_min", float(thresholds["moderate_min_score"]), True, aliases
            ),
        ]
    elif snapshot.policy_id == "signal.accum.flags":
        components = [_component("production_raw_score", 1.0, True, aliases)]
        components.extend(
            _component(
                str(row["key"]),
                float(row.get("score_penalty", row.get("weight", 0.0))),
                bool(row.get("enabled", True)),
                aliases,
            )
            for row in payload.get("components") or []
        )
    else:
        components = []
        for row in payload.get("components") or []:
            key = str(row["key"])
            raw_weight = row.get("weight")
            if raw_weight is None and key == "bci":
                raw_weight = row.get("cluster_points", 0.0)
            if raw_weight is None and snapshot.decision_type == "gate":
                raw_weight = 1.0
            components.append(
                _component(
                    key,
                    float(raw_weight or 0.0),
                    bool(row.get("enabled", True)),
                    aliases,
                )
            )
    max_score = float(
        (payload.get("output_scale") or {}).get("max", payload.get("max_score", 1.0))
    )
    return ChallengeExecutionPolicy(
        policy_id=snapshot.policy_id,
        version=snapshot.policy_version,
        hash=snapshot.payload_digest,
        max_score=max_score,
        components=tuple(components),
        source=f"verified {snapshot.contract_id}",
        source_ref=snapshot.source_revision,
        protocol_id=adapter.protocol_id,
        panel_kind=adapter.panel_kind,
        score_kind=adapter.score_kind,
        observation_compatibility_id=snapshot.compatibility_id,
        production_snapshot_id=snapshot.snapshot_id,
        production_snapshot_digest=snapshot.payload_digest,
        production_semantic_engine_contract_id=snapshot.semantic_engine_contract_id,
        challenge_adapter_id=adapter.adapter_id,
        challenge_adapter_version=adapter.adapter_version,
    )
