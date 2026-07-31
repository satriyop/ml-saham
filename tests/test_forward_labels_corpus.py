"""Forward-label audit: canonical learning_outcome_labels, not retired tables."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ml_saham.data.doctor_checks import run_doctor
from ml_saham.data.phase2_read import load_forward_labels
from tests.fixtures.build_mvp_fixture import build_mvp_fixture


def test_load_forward_labels_from_learning_outcome_labels(tmp_path: Path):
    db = build_mvp_fixture(tmp_path / "labels.db", min_bars=80)
    conn = sqlite3.connect(db)
    try:
        rows = load_forward_labels(conn, horizon=5, limit=500)
        assert len(rows) >= 30
        assert all(r.get("label_source") == "learning_outcome_labels" for r in rows)
        assert all("ticker" in r and "signal_date" in r and "close_return" in r for r in rows)
        # Must not require retired table
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "learning_outcome_labels" in tables
        assert "learning_observations" in tables
    finally:
        conn.close()


def test_load_forward_labels_prefers_corpus_over_legacy(tmp_path: Path):
    db = tmp_path / "dual.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE learning_observations (
                observation_id TEXT, purpose TEXT, captured_at TEXT,
                decision_payload_json TEXT
            );
            CREATE TABLE learning_outcome_labels (
                label_id TEXT, observation_id TEXT, contract_id TEXT,
                metrics_json TEXT, availability TEXT, labeled_at TEXT
            );
            CREATE TABLE signal_forward_labels (
                ticker TEXT, signal_date TEXT, horizon INT, close_return REAL
            );
            """
        )
        payload = json.dumps({"ticker": "BBCA", "snapshot_date": "2024-02-01"})
        conn.execute(
            "INSERT INTO learning_observations VALUES (?,?,?,?)",
            ("oid-1", "ACCUMULATION_DISCOVERY", "2024-02-01T09:00:00", payload),
        )
        conn.execute(
            "INSERT INTO learning_outcome_labels VALUES (?,?,?,?,?,?)",
            (
                "lab-1",
                "oid-1",
                "price_path.accum_5d.v1",
                json.dumps(
                    {
                        "horizon": 5,
                        "close_return": 0.05,
                        "ticker": "BBCA",
                        "signal_date": "2024-02-01",
                    }
                ),
                "AVAILABLE",
                "2024-02-10",
            ),
        )
        conn.execute(
            "INSERT INTO signal_forward_labels VALUES (?,?,?,?)",
            ("BBRI", "2024-01-01", 5, 0.99),
        )
        conn.commit()
        rows = load_forward_labels(conn, horizon=5, limit=10)
        assert len(rows) == 1
        assert rows[0]["ticker"] == "BBCA"
        assert rows[0]["close_return"] == 0.05
        assert rows[0]["label_source"] == "learning_outcome_labels"
    finally:
        conn.close()


def test_doctor_integrity_checks_learning_plane_not_retired_ok(tmp_path: Path):
    db = build_mvp_fixture(tmp_path / "doc.db", min_bars=80)
    report = run_doctor(db, deep=True)
    names = {i.name: i for i in report.integrity.items}
    assert "learning_observations" in names
    assert names["learning_observations"].status in ("ok", "partial")
    assert "learning_outcome_labels" in names
    assert names["learning_outcome_labels"].status in ("ok", "partial")
    # retired tables must not be reported as healthy "ok" data plane
    if "signal_forward_labels" in names:
        assert names["signal_forward_labels"].status != "ok"
    if "candidate_observations" in names:
        assert names["candidate_observations"].status != "ok"
    # phase-2 soft list should include learning tables, not require retired
    p2_names = {i.name for i in report.phase2.items}
    assert "learning_observations" in p2_names
    assert "learning_outcome_labels" in p2_names
