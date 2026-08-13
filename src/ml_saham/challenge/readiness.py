"""Typed C0 ACCUM producer-handoff and Protocol readiness projection."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ml_saham.challenge.metrics import time_purged_folds
from ml_saham.challenge.production_policy_snapshots import (
    REQUIRED_POLICIES,
    SNAPSHOT_CONTRACT,
    PolicySnapshotError,
    load_verified_snapshot_set,
)
from ml_saham.challenge.runner import prepare_for_policy
from ml_saham.data.accum_readiness_read import (
    fetch_accum_readiness_rows,
    fetch_snapshot_binding_claims,
)
from ml_saham.data.aisaham_read import connect as db_connect

READINESS_CONTRACT_ID = "accum_challenge_readiness.v1"
PRODUCER_OBSERVATION_CONTRACT = "learning_observation.accumulation_discovery.v2"
PRODUCER_PAYLOAD_SCHEMA = 15
PRODUCER_POLICY_CONTRACT = "accumulation_discovery.policy.v1"
PRODUCER_HORIZON_CONTRACT = "accum_10d"
POPULATION_CONTRACT = "population.accum.lq45_current_roster_pit_tradable.v1"
LABEL_CONTRACTS = {
    "H3": "price_path.accum_3d.v1",
    "H10": "price_path.accum_10d.v1",
    "H20": "price_path.accum_20d.v1",
}
LABEL_HORIZON_SESSIONS = {"H3": 3, "H10": 10, "H20": 20}


@dataclass(frozen=True)
class ProducerHandoffReadiness:
    status: str
    compatibility_id: str
    observation_count: int = 0
    valid_observation_count: int = 0
    invalid_observation_count: int = 0
    session_count: int = 0
    economic_date_min: str | None = None
    economic_date_max: str | None = None
    snapshot_contract: str = SNAPSHOT_CONTRACT
    snapshot_required_count: int = len(REQUIRED_POLICIES)
    snapshot_verified_count: int = 0
    snapshot_verified_policy_ids: tuple[str, ...] = ()
    labels_by_horizon: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    action_distribution: Mapping[str, int] = field(default_factory=dict)
    setup_readiness_present: int = 0
    setup_readiness_missing: int = 0
    setup_readiness_state_distribution: Mapping[str, int] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProtocolReadiness:
    status: str
    policy_id: str
    protocol_id: str = ""
    target_source: str = ""
    benchmark: str = ""
    primary_horizon: int | None = None
    horizons: tuple[int, ...] = ()
    embargo_sessions: int | None = None
    min_n_total: int | None = None
    min_n_test: int | None = None
    min_folds_for_verdict: int | None = None
    panel_rows: int = 0
    panel_sessions: int = 0
    estimated_valid_post_embargo_folds: int = 0
    excluded_observations: int = 0
    production_snapshot_id: str = ""
    production_snapshot_digest: str = ""
    challenge_adapter_id: str = ""
    challenge_adapter_version: str = ""
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AccumChallengeReadiness:
    contract_id: str
    producer_handoff: ProducerHandoffReadiness
    protocol_readiness: ProtocolReadiness

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _stable_id(contract_id: str, identity: Mapping[str, Any]) -> str:
    return _digest({"contract_id": contract_id, "identity": identity})


def _json_object(raw: Any, field_name: str) -> dict[str, Any]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: expected JSON object")
    return value


def _validate_artifact(row: Mapping[str, Any], *, id_field: str) -> dict[str, Any]:
    artifact = _json_object(row["artifact_json"], "artifact_json")
    if (
        artifact.get(id_field) != row[id_field]
        or artifact.get("artifact_digest") != row["artifact_digest"]
    ):
        raise ValueError("artifact envelope differs from relational columns")
    material = dict(artifact)
    material.pop(id_field, None)
    material.pop("artifact_digest", None)
    if id_field == "observation_id":
        material.pop("producer_source_revision", None)
    elif id_field == "label_id":
        material.pop("labeled_at", None)
    if _digest(material) != row["artifact_digest"]:
        raise ValueError("artifact_digest mismatch")
    return artifact


def _validate_population(payload: Mapping[str, Any], row: Mapping[str, Any]) -> None:
    binding = payload.get("population_binding")
    if not isinstance(binding, dict):
        raise ValueError("population_binding missing")
    expected = {
        "schema_version": 2,
        "contract_id": POPULATION_CONTRACT,
        "population_name": "lq45",
        "benchmark_symbol": "IHSG",
    }
    for key, value in expected.items():
        if binding.get(key) != value:
            raise ValueError(f"population_binding.{key} mismatch")
    membership = binding.get("membership_tickers")
    named = binding.get("named_universe_tickers")
    if (
        not isinstance(membership, list)
        or not membership
        or not isinstance(named, list)
        or not named
    ):
        raise ValueError("population_binding ticker attestations missing")
    if membership != sorted(set(membership)) or named != sorted(set(named)):
        raise ValueError("population_binding ticker attestations are not sorted unique")
    if not set(membership).issubset(named):
        raise ValueError("population membership is outside named universe")
    membership_digest = _digest({"tickers": membership})
    named_digest = _digest({"tickers": named})
    if binding.get("membership_count") != len(membership):
        raise ValueError("population membership_count mismatch")
    if (
        binding.get("membership_digest") != membership_digest
        or row["universe_id"] != membership_digest
    ):
        raise ValueError("population membership_digest mismatch")
    if binding.get("named_universe_digest") != named_digest:
        raise ValueError("population named_universe_digest mismatch")
    if binding.get("membership_session") != payload.get("session_date"):
        raise ValueError("population membership_session mismatch")


def _validate_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    artifact = _validate_artifact(row, id_field="observation_id")
    expected_columns = {
        "schema_version": 1,
        "contract_id": PRODUCER_OBSERVATION_CONTRACT,
        "purpose": "ACCUMULATION_DISCOVERY",
        "policy_contract": PRODUCER_POLICY_CONTRACT,
        "horizon_contract": PRODUCER_HORIZON_CONTRACT,
    }
    for key, value in expected_columns.items():
        if row[key] != value:
            raise ValueError(f"observation {key} mismatch")
    identity = {
        key: row[key]
        for key in (
            "purpose",
            "policy_contract",
            "horizon_contract",
            "compatibility_id",
            "cutoff_at",
            "universe_id",
            "window_id",
        )
    }
    if _stable_id(PRODUCER_OBSERVATION_CONTRACT, identity) != row["observation_id"]:
        raise ValueError("observation_id mismatch")
    payload = _json_object(row["decision_payload_json"], "decision_payload_json")
    if artifact.get("decision_payload") != payload:
        raise ValueError("decision payload differs from artifact")
    expected_payload = {
        "artifact_type": "accumulation_session_observation",
        "schema_version": PRODUCER_PAYLOAD_SCHEMA,
        "workflow": "research_accum_capture",
        "canonical_window": 7,
    }
    for key, value in expected_payload.items():
        if payload.get(key) != value:
            raise ValueError(f"payload {key} mismatch")
    if payload.get("captured_at") != row["captured_at"]:
        raise ValueError("payload captured_at mismatch")
    if row["window_id"] != f"{payload.get('ticker')}:{payload.get('session_date')}":
        raise ValueError("window_id mismatch")
    _validate_population(payload, row)
    return payload


def _producer_projection(
    db_path: Path | str, compatibility_id: str | None
) -> ProducerHandoffReadiness:
    cid = (compatibility_id or "").strip()
    if not cid:
        return ProducerHandoffReadiness(
            status="BLOCKED_POLICY",
            compatibility_id="",
            reasons=("explicit_compatibility_id_required",),
        )
    reasons: list[str] = []
    try:
        with db_connect(db_path) as conn:
            observations, labels = fetch_accum_readiness_rows(conn, cid)
            snapshot_claim_count, snapshot_claim_contracts = (
                fetch_snapshot_binding_claims(conn, cid)
            )
            verified: dict[str, Any] = {}
            snapshot_error = ""
            try:
                verified = load_verified_snapshot_set(conn, cid)
            except PolicySnapshotError as exc:
                snapshot_error = str(exc)
    except (OSError, ValueError) as exc:
        return ProducerHandoffReadiness(
            status="BLOCKED_POLICY",
            compatibility_id=cid,
            reasons=(f"read_contract_error:{exc}",),
        )

    valid: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    invalid: list[str] = []
    legacy = False
    for row in observations:
        try:
            payload = _validate_observation(row)
            valid[str(row["observation_id"])] = (row, payload)
        except (KeyError, TypeError, ValueError) as exc:
            if (
                row["contract_id"] != PRODUCER_OBSERVATION_CONTRACT
                or row["schema_version"] != 1
            ):
                legacy = True
            invalid.append(f"{row['observation_id']}:{exc}")

    sessions = sorted(
        {str(payload.get("session_date")) for _, payload in valid.values()}
    )
    actions: Counter[str] = Counter()
    readiness: Counter[str] = Counter()
    for _, payload in valid.values():
        window = (payload.get("features_by_window") or {}).get("7") or {}
        action = (window.get("trade_setup") or {}).get("action")
        readiness_payload = (window.get("signal") or {}).get("setup_readiness")
        state = (
            readiness_payload.get("status")
            if isinstance(readiness_payload, Mapping)
            else None
        )
        actions[str(action) if action is not None else "null"] += 1
        readiness[str(state) if state is not None else "null"] += 1

    label_counts: dict[str, dict[str, int]] = {
        h: {
            "available": 0,
            "unavailable": 0,
            "insufficient_horizon": len(valid),
            "conflict": 0,
        }
        for h in LABEL_CONTRACTS
    }
    seen: set[tuple[str, str]] = set()
    terminal_presence: dict[str, set[str]] = {h: set() for h in LABEL_CONTRACTS}
    invalid_labels: list[str] = []
    contract_to_h = {v: k for k, v in LABEL_CONTRACTS.items()}
    for row in labels:
        obs_id = str(row["observation_id"])
        contract = str(row["contract_id"])
        if obs_id not in valid:
            continue
        if contract in contract_to_h:
            terminal_presence[contract_to_h[contract]].add(obs_id)
        try:
            artifact = _validate_artifact(row, id_field="label_id")
            if (
                contract not in contract_to_h
                or row["schema_version"] != 1
                or row["outcome_basis"] != "PRICE_PATH_ONLY"
            ):
                raise ValueError("unsupported label contract")
            if (
                _stable_id(
                    contract, {"observation_id": obs_id, "contract_id": contract}
                )
                != row["label_id"]
            ):
                raise ValueError("label_id mismatch")
            metrics = _json_object(row["metrics_json"], "metrics_json")
            if artifact.get("metrics") != metrics:
                raise ValueError("label metrics differ from artifact")
            parent_row, parent_payload = valid[obs_id]
            expected_fingerprint = _digest(
                {
                    "observation_id": obs_id,
                    "decision_digest": parent_row["artifact_digest"],
                    "label_contract": contract,
                }
            )
            if row["fingerprint"] != expected_fingerprint:
                raise ValueError("label fingerprint mismatch")
            availability = str(row["availability"])
            outcome = row["outcome"]
            if availability == "AVAILABLE" and outcome not in {
                "SUCCESS",
                "FAILURE",
                "NEUTRAL",
            }:
                raise ValueError("AVAILABLE label has invalid outcome")
            if availability == "UNAVAILABLE" and outcome is not None:
                raise ValueError("UNAVAILABLE label has outcome")
            if availability not in {"AVAILABLE", "UNAVAILABLE"}:
                raise ValueError("invalid label availability")
            key = (obs_id, contract)
            h = contract_to_h[contract]
            if availability == "AVAILABLE":
                window_sessions = metrics.get("label_window_sessions")
                if (
                    metrics.get("path_label_metrics_schema_version") != 3
                    or metrics.get("ticker") != parent_payload.get("ticker")
                    or metrics.get("signal_date")
                    != parent_payload.get("session_date")
                    or not isinstance(window_sessions, list)
                    or len(window_sessions) != LABEL_HORIZON_SESSIONS[h]
                    or window_sessions != sorted(set(window_sessions))
                    or metrics.get("label_window_start") != window_sessions[0]
                    or metrics.get("label_window_end") != window_sessions[-1]
                ):
                    raise ValueError("AVAILABLE label window contract mismatch")
            if key in seen:
                label_counts[h]["conflict"] += 1
                raise ValueError("duplicate observation/horizon label")
            seen.add(key)
            label_counts[h][availability.lower()] += 1
        except (KeyError, TypeError, ValueError) as exc:
            invalid_labels.append(f"{row['label_id']}:{exc}")

    for horizon, present_ids in terminal_presence.items():
        label_counts[horizon]["insufficient_horizon"] = max(
            0, len(valid) - len(present_ids)
        )

    if invalid:
        reasons.append(f"observation_contract_corruption:{len(invalid)}")
    if invalid_labels:
        reasons.append(f"label_contract_corruption:{len(invalid_labels)}")
    if snapshot_error:
        reasons.append(f"snapshot_binding:{snapshot_error}")

    snapshot_verified = len(verified)
    claims_active_snapshot = (
        snapshot_claim_count > 0 and SNAPSHOT_CONTRACT in snapshot_claim_contracts
    )
    if invalid or invalid_labels or (snapshot_error and claims_active_snapshot):
        status = "BLOCKED_POLICY"
    elif not observations or legacy or snapshot_verified != len(REQUIRED_POLICIES):
        status = "LEGACY_RAW_ONLY"
    elif len(sessions) < 2 or label_counts["H10"]["available"] < 1:
        status = "COLLECTING"
        if len(sessions) < 2:
            reasons.append("fewer_than_two_valid_sessions")
        if label_counts["H10"]["available"] < 1:
            reasons.append("no_available_h10_producer_label")
    else:
        status = "CHALLENGE_INPUT_READY"
    present = sum(n for state, n in readiness.items() if state != "null")
    return ProducerHandoffReadiness(
        status=status,
        compatibility_id=cid,
        observation_count=len(observations),
        valid_observation_count=len(valid),
        invalid_observation_count=len(invalid),
        session_count=len(sessions) if not invalid else 0,
        economic_date_min=sessions[0] if sessions else None,
        economic_date_max=sessions[-1] if sessions else None,
        snapshot_verified_count=snapshot_verified,
        snapshot_verified_policy_ids=tuple(sorted(verified)),
        labels_by_horizon=label_counts,
        action_distribution=dict(sorted(actions.items())),
        setup_readiness_present=present,
        setup_readiness_missing=readiness.get("null", 0),
        setup_readiness_state_distribution=dict(sorted(readiness.items())),
        reasons=tuple(reasons),
    )


def _protocol_projection(
    db_path: Path | str, compatibility_id: str | None, policy_id: str
) -> ProtocolReadiness:
    cid = (compatibility_id or "").strip()
    if not cid:
        return ProtocolReadiness(
            status="BLOCKED_POLICY",
            policy_id=policy_id,
            reasons=("explicit_compatibility_id_required",),
        )
    try:
        prep = prepare_for_policy(db_path, policy_id, preferred_compatibility_id=cid)
    except (KeyError, OSError, ValueError) as exc:
        return ProtocolReadiness(
            status="BLOCKED_POLICY",
            policy_id=policy_id,
            reasons=(f"policy_or_protocol_error:{exc}",),
        )
    policy, protocol = prep.policy, prep.protocol
    if policy is None or protocol is None:
        return ProtocolReadiness(
            status="BLOCKED_POLICY", policy_id=policy_id, reasons=tuple(prep.notes[-8:])
        )
    folds = time_purged_folds(prep.rows, protocol)
    if prep.blocked is not None:
        status = (
            "BLOCKED_POLICY"
            if prep.blocked.value == "BLOCKED_POLICY"
            else "BLOCKED_DATA"
        )
    elif len(folds) < protocol.min_folds_for_verdict:
        status = "INCONCLUSIVE_DEPTH"
    else:
        status = "READY_FOR_PROTOCOL"
    excluded = 0
    for note in prep.notes:
        match = re.search(r"dropped (\d+)", note)
        if match:
            excluded += int(match.group(1))
    return ProtocolReadiness(
        status=status,
        policy_id=policy.policy_id,
        protocol_id=protocol.protocol_id,
        target_source="protocol_computed_candles",
        benchmark="IHSG",
        primary_horizon=protocol.primary_horizon,
        horizons=protocol.horizons_report,
        embargo_sessions=protocol.embargo_sessions,
        min_n_total=protocol.min_n_total,
        min_n_test=protocol.min_n_test,
        min_folds_for_verdict=protocol.min_folds_for_verdict,
        panel_rows=len(prep.rows),
        panel_sessions=len({row.date for row in prep.rows}),
        estimated_valid_post_embargo_folds=len(folds),
        excluded_observations=excluded,
        production_snapshot_id=policy.production_snapshot_id,
        production_snapshot_digest=policy.production_snapshot_digest,
        challenge_adapter_id=policy.challenge_adapter_id,
        challenge_adapter_version=policy.challenge_adapter_version,
        reasons=tuple(prep.notes[-8:]),
    )


def build_accum_challenge_readiness(
    db_path: Path | str,
    *,
    compatibility_id: str | None,
    policy_id: str = "screener.accum.score_weights",
) -> AccumChallengeReadiness:
    """Build both independent C0 axes from one explicit ACCUM cohort."""
    return AccumChallengeReadiness(
        contract_id=READINESS_CONTRACT_ID,
        producer_handoff=_producer_projection(db_path, compatibility_id),
        protocol_readiness=_protocol_projection(db_path, compatibility_id, policy_id),
    )
