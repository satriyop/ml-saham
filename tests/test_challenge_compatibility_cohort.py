"""Accum panels must not mix compatibility_id rulebooks."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ml_saham.challenge.panel import (
    fetch_accum_observation_raw,
    list_accum_compatibility_cohorts,
    resolve_accum_compatibility_id,
)
from ml_saham.data.aisaham_read import connect


def _make_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE learning_observations (
            observation_id TEXT,
            purpose TEXT,
            compatibility_id TEXT,
            captured_at TEXT,
            decision_payload_json TEXT
        );
        """
    )
    # Large older cohort (3 rows)
    for i, t in enumerate(("BBCA", "BBRI", "TLKM")):
        payload = {
            "ticker": t,
            "session_date": f"2026-07-0{i+1}",
            "features_by_window": {
                "7": {
                    "candidate": {
                        "accum_score_breakdown": {
                            "components": [
                                {"key": "cons", "score_points": 10.0},
                                {"key": "streak", "score_points": 8.0},
                                {"key": "vwap", "score_points": 5.0},
                            ]
                        }
                    }
                }
            },
            "canonical_window": 7,
        }
        conn.execute(
            "INSERT INTO learning_observations VALUES (?,?,?,?,?)",
            (
                f"old-{t}",
                "ACCUMULATION_DISCOVERY",
                "sha256:old_cohort_aaaaaaaa",
                f"2026-07-29T10:00:0{i}",
                json.dumps(payload),
            ),
        )
    # Small newer cohort (1 row)
    payload_new = {
        "ticker": "ASII",
        "session_date": "2026-07-30",
        "features_by_window": {
            "7": {
                "candidate": {
                    "accum_score_breakdown": {
                        "components": [
                            {"key": "cons", "score_points": 9.0},
                            {"key": "streak", "score_points": 7.0},
                            {"key": "vwap", "score_points": 4.0},
                        ]
                    }
                }
            }
        },
        "canonical_window": 7,
    }
    conn.execute(
        "INSERT INTO learning_observations VALUES (?,?,?,?,?)",
        (
            "new-ASII",
            "ACCUMULATION_DISCOVERY",
            "sha256:new_cohort_bbbbbbbb",
            "2026-07-30T19:00:00",
            json.dumps(payload_new),
        ),
    )
    conn.commit()
    conn.close()
    return path


def test_list_cohorts_orders_by_size(tmp_path: Path):
    db = _make_db(tmp_path / "c.db")
    with connect(db) as conn:
        cohorts = list_accum_compatibility_cohorts(conn)
    assert len(cohorts) == 2
    assert cohorts[0][0] == "sha256:old_cohort_aaaaaaaa"
    assert cohorts[0][1] == 3
    assert cohorts[1][0] == "sha256:new_cohort_bbbbbbbb"
    assert cohorts[1][1] == 1


def test_auto_selects_largest_never_mixes(tmp_path: Path):
    db = _make_db(tmp_path / "c.db")
    with connect(db) as conn:
        cid, notes = resolve_accum_compatibility_id(conn)
        assert cid == "sha256:old_cohort_aaaaaaaa"
        assert any("auto-selected largest" in n for n in notes)
        assert any("excluded" in n for n in notes)

        rows, notes2, resolved = fetch_accum_observation_raw(conn)
        assert resolved == "sha256:old_cohort_aaaaaaaa"
        assert len(rows) == 3
        # no ASII from small cohort
        tickers = []
        for r in rows:
            p = json.loads(r["decision_payload_json"])
            tickers.append(p["ticker"])
        assert "ASII" not in tickers
        assert set(tickers) == {"BBCA", "BBRI", "TLKM"}


def test_explicit_compatibility_id(tmp_path: Path):
    db = _make_db(tmp_path / "c.db")
    with connect(db) as conn:
        rows, notes, resolved = fetch_accum_observation_raw(
            conn, preferred_compatibility_id="sha256:new_cohort_bbbbbbbb"
        )
        assert resolved == "sha256:new_cohort_bbbbbbbb"
        assert len(rows) == 1
        p = json.loads(rows[0]["decision_payload_json"])
        assert p["ticker"] == "ASII"
        assert any("explicit" in n for n in notes)


def test_legacy_fixture_without_column_loads_all(tmp_path: Path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE learning_observations (
            purpose TEXT, captured_at TEXT, decision_payload_json TEXT
        )
        """
    )
    for t in ("A", "B"):
        conn.execute(
            "INSERT INTO learning_observations VALUES (?,?,?)",
            (
                "ACCUMULATION_DISCOVERY",
                "2024-01-01",
                json.dumps({"ticker": t, "session_date": "2024-01-01"}),
            ),
        )
    conn.commit()
    conn.close()
    with connect(db) as c:
        rows, notes, resolved = fetch_accum_observation_raw(c)
        assert resolved is None
        assert len(rows) == 2
        assert notes == []
