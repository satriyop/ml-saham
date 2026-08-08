from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from ml_saham.challenge.diagnostic_producer_bindings import (
    DiagnosticBindingError,
    verify_diagnostic_observation_bindings,
)
from ml_saham.challenge.diagnostics.registry import load_diagnostic
from ml_saham.challenge.panel_diagnostic import extract_diagnostic_features
from ml_saham.data.aisaham_read import connect
from ml_saham.data.observation_cohort import fetch_accum_observation_raw
from tests.fixtures.build_mvp_fixture import (
    FIXTURE_COMPATIBILITY_ID,
    build_mvp_fixture,
)
from tests.fixtures.diagnostic_bindings import bind_schema14_diagnostics


@pytest.fixture
def bound_db(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    path = build_mvp_fixture(tmp_path / "bound.db", min_bars=80)
    with sqlite3.connect(path) as conn:
        diagnostic_ids = bind_schema14_diagnostics(
            conn, compatibility_id=FIXTURE_COMPATIBILITY_ID
        )
    return path, diagnostic_ids


def _payloads(conn: sqlite3.Connection) -> list[dict]:
    rows, _, _ = fetch_accum_observation_raw(
        conn, compatibility_id=FIXTURE_COMPATIBILITY_ID
    )
    return [
        json.loads(
            row["decision_payload_json"] if isinstance(row, sqlite3.Row) else row[2]
        )
        for row in rows
    ]


def test_valid_binding_verifies_without_mutating_sqlite(
    bound_db: tuple[Path, dict[str, str]],
) -> None:
    path, ids = bound_db
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with connect(path) as conn:
        verified = verify_diagnostic_observation_bindings(
            conn,
            diagnostic_id="sector.peer_context",
            diagnostic_compatibility_id=ids["sector.peer_context"],
            decision_payloads=_payloads(conn),
        )
    assert verified.compatibility_id == ids["sector.peer_context"]
    assert len(verified.producer_snapshot_ids) == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize(
    "mutation",
    ["schema13", "missing", "extra", "mixed", "bad_digest", "bad_formula"],
)
def test_invalid_bindings_fail_closed(
    bound_db: tuple[Path, dict[str, str]], mutation: str
) -> None:
    path, ids = bound_db
    if mutation == "bad_formula":
        with sqlite3.connect(path) as writable:
            payloads = _payloads(writable)
            snapshot_id = payloads[0]["diagnostic_bindings"]["sector.peer_context"][
                "producers"
            ]["diagnostic.sector_peer_context"]["snapshot_id"]
            writable.execute(
                "UPDATE learning_diagnostic_producer_snapshots SET formula_id = ? "
                "WHERE snapshot_id = ?",
                ("mutated.formula", snapshot_id),
            )
    with connect(path) as conn:
        payloads = _payloads(conn)
        if mutation == "schema13":
            payloads[0]["schema_version"] = 13
        elif mutation == "missing":
            del payloads[0]["diagnostic_bindings"]["sector.peer_context"]
        elif mutation == "extra":
            payloads[0]["diagnostic_bindings"]["unknown.bag"] = {}
        elif mutation == "mixed":
            payloads[0]["diagnostic_bindings"]["sector.peer_context"][
                "compatibility_id"
            ] = "sha256:" + "00" * 32
        elif mutation == "bad_digest":
            producer = payloads[0]["diagnostic_bindings"]["sector.peer_context"][
                "producers"
            ]["diagnostic.sector_peer_context"]
            producer["payload_digest"] = "sha256:" + "11" * 32
        with pytest.raises(DiagnosticBindingError):
            verify_diagnostic_observation_bindings(
                conn,
                diagnostic_id="sector.peer_context",
                diagnostic_compatibility_id=ids["sector.peer_context"],
                decision_payloads=payloads,
            )


def test_exact_window_and_sector_breadth_path_only(
    bound_db: tuple[Path, dict[str, str]],
) -> None:
    path, _ = bound_db
    with connect(path) as conn:
        payload = _payloads(conn)[0]
    spec = load_diagnostic("sector.peer_context")
    features = extract_diagnostic_features(payload, spec)
    assert features is not None
    assert (
        features["peer_breadth"]
        == payload["features_by_window"]["7"]["sub_signal_fingerprint"][
            "sc_sector_breadth"
        ]
    )

    fingerprint = payload["features_by_window"]["7"]["sub_signal_fingerprint"]
    fingerprint["sector_breadth"] = fingerprint.pop("sc_sector_breadth")
    aliased = extract_diagnostic_features(payload, spec)
    assert aliased is not None
    assert aliased["peer_breadth"] != aliased["peer_breadth"]  # NaN, unavailable


def test_root_and_noncanonical_window_do_not_acquire_authority(
    bound_db: tuple[Path, dict[str, str]],
) -> None:
    path, _ = bound_db
    with connect(path) as conn:
        payload = _payloads(conn)[0]
    spec = load_diagnostic("sector.peer_context")
    payload["features_by_window"]["30"]["sub_signal_fingerprint"][
        "sc_sector_breadth"
    ] = 0.999
    del payload["features_by_window"]["7"]["sub_signal_fingerprint"][
        "sc_sector_breadth"
    ]
    payload["sub_signal_fingerprint"]["sc_sector_breadth"] = 0.888
    features = extract_diagnostic_features(payload, spec)
    assert features is not None
    assert features["peer_breadth"] != features["peer_breadth"]
