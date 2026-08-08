"""Schema-15 diagnostic authority fixture matching the upstream wire contract."""

from __future__ import annotations

import json
import sqlite3

from ml_saham.challenge.diagnostic_producer_bindings import (
    BINDING_CONTRACT,
    OBSERVATION_SCHEMA_VERSION,
    PURPOSE,
    REQUIRED_PRODUCERS,
    SNAPSHOT_CONTRACT,
    _sha256_id,
    canonical_json,
)


def bind_schema15_diagnostics(
    conn: sqlite3.Connection, *, compatibility_id: str
) -> dict[str, str]:
    conn.execute(
        """
        CREATE TABLE learning_diagnostic_producer_snapshots (
            snapshot_id TEXT, schema_version INTEGER, contract_id TEXT,
            purpose TEXT, producer_id TEXT, producer_contract_id TEXT,
            formula_id TEXT, canonical_payload_json TEXT, payload_digest TEXT,
            source_revision TEXT, created_at TEXT
        )
        """
    )
    links: dict[str, dict[str, str]] = {}
    for producer_id in sorted(
        {p for values in REQUIRED_PRODUCERS.values() for p in values}
    ):
        formula_id = f"{producer_id}.formula.v1"
        payload = {"fixture": "upstream-wire", "formula_id": formula_id}
        payload_json = canonical_json(payload)
        payload_digest = _sha256_id(payload)
        producer_contract_id = f"{producer_id}.v1"
        snapshot_id = _sha256_id(
            {
                "contract_id": SNAPSHOT_CONTRACT,
                "purpose": PURPOSE,
                "producer_id": producer_id,
                "producer_contract_id": producer_contract_id,
                "payload_digest": payload_digest,
            }
        )
        conn.execute(
            "INSERT INTO learning_diagnostic_producer_snapshots VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?)",
            (
                snapshot_id,
                1,
                SNAPSHOT_CONTRACT,
                PURPOSE,
                producer_id,
                producer_contract_id,
                formula_id,
                payload_json,
                payload_digest,
                "ai-saham@test+git:deadbeef",
                "2026-08-08T00:00:00+00:00",
            ),
        )
        links[producer_id] = {
            "snapshot_id": snapshot_id,
            "payload_digest": payload_digest,
        }

    diagnostic_ids: dict[str, str] = {}
    bindings: dict[str, dict[str, object]] = {}
    for diagnostic_id, producer_ids in REQUIRED_PRODUCERS.items():
        identity_rows = [
            {"producer_id": producer_id, **links[producer_id]}
            for producer_id in sorted(producer_ids)
        ]
        diagnostic_cid = _sha256_id(
            {
                "contract_id": BINDING_CONTRACT,
                "diagnostic_id": diagnostic_id,
                "observation_schema_version": OBSERVATION_SCHEMA_VERSION,
                "producers": identity_rows,
            }
        )
        diagnostic_ids[diagnostic_id] = diagnostic_cid
        bindings[diagnostic_id] = {
            "contract_id": BINDING_CONTRACT,
            "diagnostic_id": diagnostic_id,
            "compatibility_id": diagnostic_cid,
            "producers": {
                producer_id: links[producer_id] for producer_id in producer_ids
            },
        }

    rows = conn.execute(
        "SELECT id, decision_payload_json FROM learning_observations "
        "WHERE purpose = ? AND compatibility_id = ?",
        (PURPOSE, compatibility_id),
    ).fetchall()
    for row_id, raw in rows:
        payload = json.loads(raw)
        fingerprint = dict(payload["sub_signal_fingerprint"])
        fingerprint["sc_sector_breadth"] = fingerprint.pop("sector_breadth", None)
        window = {
            "signal": payload["signal"],
            "sub_signal_fingerprint": fingerprint,
            "candidate": payload["candidate"],
            "structural_filter": {
                "outcome": "disabled",
                "field": None,
                "reason": None,
                "observed_value": None,
                "threshold": None,
            },
        }
        payload.update(
            {
                "schema_version": OBSERVATION_SCHEMA_VERSION,
                "session_date": payload["snapshot_date"],
                "features_by_window": {"7": window, "30": window, "90": window},
                "shared": {
                    "market_context": {
                        "regime": "NEUTRAL",
                        "factors": [
                            {"name": "vix", "value": 1.0},
                            {"name": "eido", "value": 2.0},
                            {"name": "usd_idr", "value": 3.0},
                            {"name": "idx_trend", "value": 4.0},
                            {"name": "idx_breadth", "value": 5.0},
                            {"name": "foreign_flow", "value": 6.0},
                        ],
                    },
                    "provenance": {
                        "decision_at": f"{payload['snapshot_date']}T09:00:00+07:00"
                    },
                },
                "population_binding": {
                    "membership_digest": "sha256:fixture_population"
                },
                "diagnostic_bindings": bindings,
            }
        )
        conn.execute(
            "UPDATE learning_observations SET decision_payload_json = ? WHERE id = ?",
            (json.dumps(payload), row_id),
        )
    conn.commit()
    return diagnostic_ids
