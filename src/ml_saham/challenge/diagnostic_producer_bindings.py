"""Verify ai-saham diagnostic producer snapshots and observation bindings.

This module has no ai-saham imports and performs read-only verification only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ml_saham.data.aisaham_read import table_columns, table_exists

SNAPSHOT_CONTRACT = "diagnostic_producer_snapshot.v1"
BINDING_CONTRACT = "diagnostic_binding.accum.v1"
PURPOSE = "ACCUMULATION_DISCOVERY"
OBSERVATION_SCHEMA_VERSION = 14

REQUIRED_PRODUCERS: dict[str, tuple[str, ...]] = {
    "mce.screen_display": ("diagnostic.market_context.frozen",),
    "sector.peer_context": (
        "diagnostic.alpha_trigger_projection",
        "diagnostic.sector_peer_context",
    ),
    "institutional.accumulation_bag": (
        "diagnostic.alpha_trigger_projection",
        "diagnostic.institutional_accumulation",
    ),
    "company_quality.bag": (
        "diagnostic.alpha_trigger_projection",
        "diagnostic.company_quality_context",
        "diagnostic.ticker_profile",
    ),
}

SNAPSHOT_COLUMNS = {
    "snapshot_id",
    "schema_version",
    "contract_id",
    "purpose",
    "producer_id",
    "producer_contract_id",
    "formula_id",
    "canonical_payload_json",
    "payload_digest",
    "source_revision",
    "created_at",
}


class DiagnosticBindingError(ValueError):
    """Missing, mixed, or invalid diagnostic producer authority."""


@dataclass(frozen=True)
class VerifiedDiagnosticBinding:
    diagnostic_id: str
    compatibility_id: str
    producer_snapshot_ids: tuple[str, ...]
    producer_payload_digests: tuple[str, ...]
    producer_source_revisions: tuple[str, ...]


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_id(payload: Mapping[str, Any]) -> str:
    return (
        "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    )


def _exact_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DiagnosticBindingError(f"{field} must be an object")
    return value


def _verify_snapshot_row(
    row: sqlite3.Row,
    *,
    expected_producer_id: str,
    expected_snapshot_id: str,
    expected_payload_digest: str,
) -> None:
    if int(row["schema_version"]) != 1:
        raise DiagnosticBindingError(
            f"{expected_producer_id}: unsupported snapshot schema"
        )
    if row["contract_id"] != SNAPSHOT_CONTRACT or row["purpose"] != PURPOSE:
        raise DiagnosticBindingError(
            f"{expected_producer_id}: snapshot contract mismatch"
        )
    if row["producer_id"] != expected_producer_id:
        raise DiagnosticBindingError(f"{expected_producer_id}: producer id mismatch")
    if row["snapshot_id"] != expected_snapshot_id:
        raise DiagnosticBindingError(f"{expected_producer_id}: snapshot id mismatch")
    if row["payload_digest"] != expected_payload_digest:
        raise DiagnosticBindingError(
            f"{expected_producer_id}: payload digest linkage mismatch"
        )
    if (
        not str(row["producer_contract_id"]).strip()
        or not str(row["formula_id"]).strip()
    ):
        raise DiagnosticBindingError(f"{expected_producer_id}: empty semantic contract")
    if not str(row["source_revision"]).strip() or not str(row["created_at"]).strip():
        raise DiagnosticBindingError(f"{expected_producer_id}: empty provenance")
    raw_payload = str(row["canonical_payload_json"])
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DiagnosticBindingError(
            f"{expected_producer_id}: malformed canonical payload"
        ) from exc
    if not isinstance(payload, dict) or canonical_json(payload) != raw_payload:
        raise DiagnosticBindingError(f"{expected_producer_id}: non-canonical payload")
    payload_digest = _sha256_id(payload)
    if payload_digest != row["payload_digest"]:
        raise DiagnosticBindingError(f"{expected_producer_id}: payload digest mismatch")
    if payload.get("formula_id") != row["formula_id"]:
        raise DiagnosticBindingError(f"{expected_producer_id}: formula id mismatch")
    snapshot_id = _sha256_id(
        {
            "contract_id": SNAPSHOT_CONTRACT,
            "purpose": PURPOSE,
            "producer_id": expected_producer_id,
            "producer_contract_id": row["producer_contract_id"],
            "payload_digest": payload_digest,
        }
    )
    if snapshot_id != row["snapshot_id"]:
        raise DiagnosticBindingError(
            f"{expected_producer_id}: snapshot identity mismatch"
        )


def verify_diagnostic_observation_bindings(
    conn: sqlite3.Connection,
    *,
    diagnostic_id: str,
    diagnostic_compatibility_id: str | None,
    decision_payloads: Sequence[Mapping[str, Any]],
) -> VerifiedDiagnosticBinding:
    """Verify one exact binding shared by every candidate observation row."""

    selected = (diagnostic_compatibility_id or "").strip()
    if not selected:
        raise DiagnosticBindingError(
            "production-facing diagnostic requires explicit diagnostic compatibility id"
        )
    required = REQUIRED_PRODUCERS.get(diagnostic_id)
    if required is None:
        raise DiagnosticBindingError(f"unsupported diagnostic_id={diagnostic_id!r}")
    if not decision_payloads:
        raise DiagnosticBindingError("selected Action cohort has no observations")
    if not table_exists(conn, "learning_diagnostic_producer_snapshots"):
        raise DiagnosticBindingError(
            "learning_diagnostic_producer_snapshots table missing"
        )
    missing_columns = SNAPSHOT_COLUMNS - table_columns(
        conn, "learning_diagnostic_producer_snapshots"
    )
    if missing_columns:
        raise DiagnosticBindingError(
            "diagnostic producer snapshot table missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    reference: Mapping[str, Any] | None = None
    for payload in decision_payloads:
        if payload.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
            raise DiagnosticBindingError(
                "diagnostic panels require observation schema 14"
            )
        bindings = _exact_mapping(
            payload.get("diagnostic_bindings"), field="diagnostic_bindings"
        )
        if set(bindings) != set(REQUIRED_PRODUCERS):
            raise DiagnosticBindingError(
                "observation diagnostic binding set is not closed"
            )
        binding = _exact_mapping(
            bindings.get(diagnostic_id), field=f"diagnostic_bindings.{diagnostic_id}"
        )
        if set(binding) != {
            "contract_id",
            "diagnostic_id",
            "compatibility_id",
            "producers",
        }:
            raise DiagnosticBindingError(f"{diagnostic_id}: binding fields mismatch")
        if binding.get("contract_id") != BINDING_CONTRACT:
            raise DiagnosticBindingError(f"{diagnostic_id}: binding contract mismatch")
        if binding.get("diagnostic_id") != diagnostic_id:
            raise DiagnosticBindingError(
                f"{diagnostic_id}: binding diagnostic id mismatch"
            )
        if binding.get("compatibility_id") != selected:
            raise DiagnosticBindingError(
                f"{diagnostic_id}: mixed or unselected binding"
            )
        producers = _exact_mapping(binding.get("producers"), field="producers")
        if set(producers) != set(required):
            raise DiagnosticBindingError(f"{diagnostic_id}: producer set mismatch")
        if reference is None:
            reference = binding
        elif binding != reference:
            raise DiagnosticBindingError(f"{diagnostic_id}: mixed binding payloads")

    assert reference is not None
    producers = _exact_mapping(reference["producers"], field="producers")
    identity_rows: list[dict[str, str]] = []
    snapshot_ids: list[str] = []
    payload_digests: list[str] = []
    source_revisions: list[str] = []
    for producer_id in sorted(required):
        link = _exact_mapping(producers[producer_id], field=f"producers.{producer_id}")
        if set(link) != {"snapshot_id", "payload_digest"}:
            raise DiagnosticBindingError(
                f"{producer_id}: snapshot link fields mismatch"
            )
        snapshot_id = link.get("snapshot_id")
        payload_digest = link.get("payload_digest")
        if type(snapshot_id) is not str or type(payload_digest) is not str:
            raise DiagnosticBindingError(f"{producer_id}: malformed snapshot link")
        columns = ", ".join(sorted(SNAPSHOT_COLUMNS))
        rows = conn.execute(
            f"SELECT {columns} FROM learning_diagnostic_producer_snapshots "
            "WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchall()
        if len(rows) != 1:
            raise DiagnosticBindingError(
                f"{producer_id}: snapshot row missing or duplicated"
            )
        _verify_snapshot_row(
            rows[0],
            expected_producer_id=producer_id,
            expected_snapshot_id=snapshot_id,
            expected_payload_digest=payload_digest,
        )
        snapshot_ids.append(snapshot_id)
        payload_digests.append(payload_digest)
        source_revisions.append(str(rows[0]["source_revision"]))
        identity_rows.append(
            {
                "producer_id": producer_id,
                "snapshot_id": snapshot_id,
                "payload_digest": payload_digest,
            }
        )
    recomputed = _sha256_id(
        {
            "contract_id": BINDING_CONTRACT,
            "diagnostic_id": diagnostic_id,
            "observation_schema_version": OBSERVATION_SCHEMA_VERSION,
            "producers": identity_rows,
        }
    )
    if recomputed != selected:
        raise DiagnosticBindingError(f"{diagnostic_id}: compatibility id mismatch")
    return VerifiedDiagnosticBinding(
        diagnostic_id=diagnostic_id,
        compatibility_id=selected,
        producer_snapshot_ids=tuple(snapshot_ids),
        producer_payload_digests=tuple(payload_digests),
        producer_source_revisions=tuple(source_revisions),
    )
