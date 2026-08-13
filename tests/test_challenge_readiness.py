"""C0 readiness keeps producer and Protocol authority independent."""

import hashlib
import json
import sqlite3
from datetime import date, timedelta

from pathlib import Path

from ml_saham.challenge.readiness import (
    PRODUCER_HORIZON_CONTRACT,
    PRODUCER_OBSERVATION_CONTRACT,
    PRODUCER_POLICY_CONTRACT,
    _producer_projection,
    build_accum_challenge_readiness,
)
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture
from tests.fixtures.policy_snapshots import insert_verified_policy_snapshots


def _digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _current_producer_db(path: Path) -> tuple[Path, str]:
    cid = "sha256:" + "ab" * 32
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE learning_observations (
            observation_id TEXT PRIMARY KEY, artifact_digest TEXT,
            schema_version INTEGER, contract_id TEXT, purpose TEXT,
            policy_contract TEXT, horizon_contract TEXT, compatibility_id TEXT,
            cutoff_at TEXT, universe_id TEXT, window_id TEXT,
            decision_payload_json TEXT, captured_at TEXT, artifact_json TEXT
        );
        CREATE TABLE learning_outcome_labels (
            label_id TEXT PRIMARY KEY, artifact_digest TEXT,
            schema_version INTEGER, contract_id TEXT, observation_id TEXT,
            outcome_basis TEXT, availability TEXT, outcome TEXT,
            metrics_json TEXT, fingerprint TEXT, labeled_at TEXT,
            artifact_json TEXT
        );
        """
    )
    insert_verified_policy_snapshots(conn, cid)
    membership = ["BBCA"]
    population_digest = _digest({"tickers": membership})
    observation_ids: list[str] = []
    for offset in range(2):
        session = (date(2026, 8, 10) + timedelta(days=offset)).isoformat()
        captured = f"{session}T21:00:00+07:00"
        cutoff = f"{session}T16:00:00+07:00"
        window_id = f"BBCA:{session}"
        payload = {
            "artifact_type": "accumulation_session_observation",
            "schema_version": 15,
            "workflow": "research_accum_capture",
            "canonical_window": 7,
            "ticker": "BBCA",
            "session_date": session,
            "captured_at": captured,
            "population_binding": {
                "schema_version": 2,
                "contract_id": "population.accum.lq45_current_roster_pit_tradable.v1",
                "population_name": "lq45",
                "benchmark_symbol": "IHSG",
                "membership_session": session,
                "membership_count": 1,
                "membership_digest": population_digest,
                "named_universe_digest": population_digest,
                "membership_tickers": membership,
                "named_universe_tickers": membership,
            },
            "features_by_window": {
                "7": {
                    "trade_setup": {"action": "WATCH"},
                    "signal": {"setup_readiness": {"status": "UNAVAILABLE"}},
                }
            },
        }
        identity = {
            "purpose": "ACCUMULATION_DISCOVERY",
            "policy_contract": PRODUCER_POLICY_CONTRACT,
            "horizon_contract": PRODUCER_HORIZON_CONTRACT,
            "compatibility_id": cid,
            "cutoff_at": cutoff,
            "universe_id": population_digest,
            "window_id": window_id,
        }
        observation_id = _digest(
            {"contract_id": PRODUCER_OBSERVATION_CONTRACT, "identity": identity}
        )
        observation_ids.append(observation_id)
        artifact = {
            "schema_version": 1,
            "contract_id": PRODUCER_OBSERVATION_CONTRACT,
            **identity,
            "decision_payload": payload,
            "captured_at": captured,
            "producer_source_revision": "ai-saham@test",
        }
        artifact_digest = _digest(
            {k: v for k, v in artifact.items() if k != "producer_source_revision"}
        )
        artifact.update(
            {"observation_id": observation_id, "artifact_digest": artifact_digest}
        )
        conn.execute(
            "INSERT INTO learning_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                observation_id,
                artifact_digest,
                1,
                PRODUCER_OBSERVATION_CONTRACT,
                "ACCUMULATION_DISCOVERY",
                PRODUCER_POLICY_CONTRACT,
                PRODUCER_HORIZON_CONTRACT,
                cid,
                cutoff,
                population_digest,
                window_id,
                json.dumps(payload),
                captured,
                json.dumps(artifact),
            ),
        )

    observation_id = observation_ids[0]
    sessions = [(date(2026, 8, 11) + timedelta(days=i)).isoformat() for i in range(10)]
    metrics = {
        "path_label_metrics_schema_version": 3,
        "ticker": "BBCA",
        "signal_date": "2026-08-10",
        "label_window_sessions": sessions,
        "label_window_start": sessions[0],
        "label_window_end": sessions[-1],
    }
    contract = "price_path.accum_10d.v1"
    label_id = _digest(
        {
            "contract_id": contract,
            "identity": {"observation_id": observation_id, "contract_id": contract},
        }
    )
    obs_digest = conn.execute(
        "SELECT artifact_digest FROM learning_observations WHERE observation_id=?",
        (observation_id,),
    ).fetchone()[0]
    fingerprint = _digest(
        {
            "observation_id": observation_id,
            "decision_digest": obs_digest,
            "label_contract": contract,
        }
    )
    label_artifact = {
        "schema_version": 1,
        "contract_id": contract,
        "observation_id": observation_id,
        "outcome_basis": "PRICE_PATH_ONLY",
        "availability": "AVAILABLE",
        "outcome": "SUCCESS",
        "metrics": metrics,
        "fingerprint": fingerprint,
    }
    label_digest = _digest(label_artifact)
    label_artifact.update(
        {
            "label_id": label_id,
            "artifact_digest": label_digest,
            "labeled_at": "2026-08-13T07:00:00+07:00",
        }
    )
    conn.execute(
        "INSERT INTO learning_outcome_labels VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            label_id,
            label_digest,
            1,
            contract,
            observation_id,
            "PRICE_PATH_ONLY",
            "AVAILABLE",
            "SUCCESS",
            json.dumps(metrics),
            fingerprint,
            "2026-08-13T07:00:00+07:00",
            json.dumps(label_artifact),
        ),
    )
    conn.commit()
    conn.close()
    return path, cid


def test_readiness_requires_explicit_cohort(tmp_path: Path) -> None:
    db = build_mvp_fixture(tmp_path / "readiness.db", min_bars=90)
    result = build_accum_challenge_readiness(db, compatibility_id=None)

    assert result.producer_handoff.status == "BLOCKED_POLICY"
    assert result.protocol_readiness.status == "BLOCKED_POLICY"
    assert result.producer_handoff.reasons == ("explicit_compatibility_id_required",)


def test_readiness_axes_and_protocol_geometry_are_typed(tmp_path: Path) -> None:
    db = build_mvp_fixture(tmp_path / "readiness.db", min_bars=120)
    result = build_accum_challenge_readiness(
        db,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    payload = result.to_dict()

    assert payload["contract_id"] == "accum_challenge_readiness.v1"
    # The legacy test observation payload is intentionally not upgraded into
    # current producer authority merely because its v4 snapshots verify.
    assert payload["producer_handoff"]["status"] in {
        "LEGACY_RAW_ONLY",
        "BLOCKED_POLICY",
    }
    protocol = payload["protocol_readiness"]
    assert protocol["protocol_id"] == "accum_path_v1"
    assert protocol["target_source"] == "protocol_computed_candles"
    assert protocol["benchmark"] == "IHSG"
    assert protocol["estimated_valid_post_embargo_folds"] >= 0
    assert protocol["status"] in {
        "BLOCKED_DATA",
        "INCONCLUSIVE_DEPTH",
        "READY_FOR_PROTOCOL",
    }


def test_current_producer_projection_verifies_integrity_and_fails_closed(
    tmp_path: Path,
) -> None:
    db, cid = _current_producer_db(tmp_path / "current.db")
    ready = _producer_projection(db, cid)
    assert ready.status == "CHALLENGE_INPUT_READY"
    assert (ready.valid_observation_count, ready.session_count) == (2, 2)
    assert ready.snapshot_verified_count == 9
    assert ready.labels_by_horizon["H10"]["available"] == 1

    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE learning_observations SET decision_payload_json='{}' "
        "WHERE observation_id=(SELECT observation_id FROM learning_observations LIMIT 1)"
    )
    conn.commit()
    conn.close()

    blocked = _producer_projection(db, cid)
    assert blocked.status == "BLOCKED_POLICY"
    assert blocked.invalid_observation_count == 1
