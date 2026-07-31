"""Screen hard-filter extract: golden conformance + read-only tripwire."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ml_saham.challenge.panel_screen_filters import (
    GATE_ACCUM_SCORE,
    GATE_MARKET_CAP,
    GATE_PIOTROSKI,
    GATE_SIGNAL_SCORE,
    ScreenFilterPolicy,
    ScreenFilterResult,
    audit_screen_filter_cohort,
    classify_screen_filters,
    extract_screen_filter_inputs,
    sufficiency_verdict,
)
from ml_saham.data.aisaham_read import connect
from tests.fixtures.golden import load_golden


def _policy_from_case(case: dict) -> ScreenFilterPolicy:
    p = case.get("policy") or {}
    return ScreenFilterPolicy(
        min_market_cap_idr=float(p.get("min_market_cap_idr") or 0),
        min_piotroski=float(p.get("min_piotroski") or 0),
        min_accum_score=float(p.get("min_accum_score") or 0),
        min_accum_score_enabled=bool(p.get("min_accum_score_enabled") or False),
        min_signal_score=float(p.get("min_signal_score") or 0),
        min_signal_score_enabled=bool(p.get("min_signal_score_enabled") or False),
    )


def test_golden_screen_hard_filter_cases():
    doc = load_golden("accum_screen_hard_filters.json")
    cases = doc["cases"]
    assert len(cases) >= 8
    for case in cases:
        pol = _policy_from_case(case)
        extracted = extract_screen_filter_inputs(case["payload"])
        cls = classify_screen_filters(extracted, pol)
        exp = case["expect"]
        assert cls.result.value == exp["result"], case["id"]
        if exp.get("firing_gate") is None:
            assert cls.firing_gate is None, case["id"]
        else:
            assert cls.firing_gate == exp["firing_gate"], case["id"]


def test_first_match_order_market_cap_before_piotroski():
    payload = {
        "ticker": "X",
        "session_date": "2026-06-02",
        "canonical_window": 7,
        "features_by_window": {
            "7": {
                "candidate": {
                    "accum_score": 10.0,
                    "fundamentals": {
                        "market_cap_idr": 1,
                        "piotroski_f_score": 0,
                    },
                },
                "signal": {"assessment": {"score": 1}},
            }
        },
    }
    pol = ScreenFilterPolicy(
        min_market_cap_idr=1e12,
        min_piotroski=9,
        min_accum_score_enabled=True,
        min_accum_score=90,
        min_signal_score_enabled=True,
        min_signal_score=90,
    )
    cls = classify_screen_filters(extract_screen_filter_inputs(payload), pol)
    assert cls.firing_gate == GATE_MARKET_CAP
    assert cls.result is ScreenFilterResult.REJECTED_FLOW


def test_window_30_not_used_as_unit():
    payload = {
        "ticker": "X",
        "session_date": "2026-06-02",
        "canonical_window": 7,
        "features_by_window": {
            "7": {
                "candidate": {
                    "accum_score": 10.0,
                    "fundamentals": {"market_cap_idr": 1e15, "piotroski_f_score": 8},
                },
                "signal": {"assessment": {"score": 80}},
            },
            "30": {
                "candidate": {
                    "accum_score": 99.0,
                    "fundamentals": {"market_cap_idr": 1, "piotroski_f_score": 0},
                }
            },
        },
    }
    pol = ScreenFilterPolicy(
        min_accum_score=50, min_accum_score_enabled=True, min_signal_score_enabled=False
    )
    # window-7 accum_score 10 → reject; must not use window-30's 99
    cls = classify_screen_filters(extract_screen_filter_inputs(payload), pol)
    assert cls.firing_gate == GATE_ACCUM_SCORE


def test_audit_requires_compatibility_id(tmp_path: Path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE learning_observations ("
        "observation_id TEXT, purpose TEXT, compatibility_id TEXT, "
        "decision_payload_json TEXT, contract_id TEXT, captured_at TEXT)"
    )
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="compatibility_id"):
        audit_screen_filter_cohort(db, compatibility_id="")


def _obs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE learning_observations ("
        "observation_id TEXT PRIMARY KEY, purpose TEXT, compatibility_id TEXT, "
        "decision_payload_json TEXT, contract_id TEXT, captured_at TEXT)"
    )


def _good_payload(ticker: str = "A", session: str = "2026-06-02") -> dict:
    return {
        "ticker": ticker,
        "session_date": session,
        "canonical_window": 7,
        "features_by_window": {
            "7": {
                "candidate": {
                    "accum_score": 60.0,
                    "fundamentals": {
                        "market_cap_idr": 2e12,
                        "piotroski_f_score": 5,
                    },
                },
                "signal": {"assessment": {"score": 40}},
            }
        },
    }


def test_audit_read_only_and_zero_growth(tmp_path: Path):
    db = tmp_path / "audit.db"
    conn = sqlite3.connect(db)
    _obs_table(conn)
    cid = "sha256:testcohort"
    conn.execute(
        "INSERT INTO learning_observations VALUES (?,?,?,?,?,?)",
        (
            "oid1",
            "ACCUMULATION_DISCOVERY",
            cid,
            json.dumps(_good_payload()),
            "learning_observation.accumulation_discovery.v2",
            "2026-06-02T16:00:00+07:00",
        ),
    )
    conn.commit()
    page_count_before = conn.execute("PRAGMA page_count").fetchone()[0]
    row_count_before = conn.execute(
        "SELECT COUNT(*) FROM learning_observations"
    ).fetchone()[0]
    conn.close()

    mtime_before = db.stat().st_mtime_ns
    summary = audit_screen_filter_cohort(
        db,
        compatibility_id=cid,
        policy=ScreenFilterPolicy(min_market_cap_idr=1e12, min_piotroski=3),
        measure_h10=False,
    )
    assert summary.selected_row_count == 1
    assert summary.extracted_count == 1
    assert summary.unextractable_count == 0
    assert sufficiency_verdict(summary) == "SUFFICIENT_FOR_REPLAY"

    with connect(db) as c2:
        assert (
            c2.execute("SELECT COUNT(*) FROM learning_observations").fetchone()[0]
            == row_count_before
        )
        assert c2.execute("PRAGMA page_count").fetchone()[0] == page_count_before
    assert db.stat().st_mtime_ns == mtime_before


def test_adversarial_cohort_fails_closed(tmp_path: Path):
    """Wrong contract + non-7 window + duplicate → not SUFFICIENT."""
    db = tmp_path / "adv.db"
    conn = sqlite3.connect(db)
    _obs_table(conn)
    cid = "sha256:adv"
    bad = _good_payload("X", "2026-06-02")
    bad["canonical_window"] = 30
    bad["features_by_window"] = {"30": bad["features_by_window"]["7"]}
    conn.execute(
        "INSERT INTO learning_observations VALUES (?,?,?,?,?,?)",
        (
            "a",
            "ACCUMULATION_DISCOVERY",
            cid,
            json.dumps(bad),
            "learning_observation.wrong.v0",
            "2026-06-02T00:00:00+07:00",
        ),
    )
    conn.execute(
        "INSERT INTO learning_observations VALUES (?,?,?,?,?,?)",
        (
            "b",
            "ACCUMULATION_DISCOVERY",
            cid,
            json.dumps(bad),
            "learning_observation.accumulation_discovery.v2",
            "2026-06-02T01:00:00+07:00",
        ),
    )
    conn.commit()
    conn.close()

    summary = audit_screen_filter_cohort(db, compatibility_id=cid, measure_h10=False)
    assert summary.wrong_contract_excluded >= 1
    assert summary.selected_row_count == 0
    assert summary.bad_canonical_window_excluded >= 1
    assert sufficiency_verdict(summary) == "INSUFFICIENT_NEEDS_CORPUS_EXTENSION"


def test_duplicate_ticker_session_excluded(tmp_path: Path):
    db = tmp_path / "dup.db"
    conn = sqlite3.connect(db)
    _obs_table(conn)
    cid = "sha256:dup"
    payload = json.dumps(_good_payload("A", "2026-06-02"))
    for i, oid in enumerate(("o1", "o2")):
        conn.execute(
            "INSERT INTO learning_observations VALUES (?,?,?,?,?,?)",
            (
                oid,
                "ACCUMULATION_DISCOVERY",
                cid,
                payload,
                "learning_observation.accumulation_discovery.v2",
                f"2026-06-02T0{i}:00:00+07:00",
            ),
        )
    conn.commit()
    conn.close()

    summary = audit_screen_filter_cohort(db, compatibility_id=cid, measure_h10=False)
    assert summary.raw_fetch_count == 2
    assert summary.selected_row_count == 1
    assert summary.duplicate_ticker_session_excluded == 1
    assert summary.extracted_count == 1
    assert sufficiency_verdict(summary) == "SUFFICIENT_FOR_REPLAY"


def test_wrong_purpose_not_fetched(tmp_path: Path):
    db = tmp_path / "purp.db"
    conn = sqlite3.connect(db)
    _obs_table(conn)
    cid = "sha256:purp"
    conn.execute(
        "INSERT INTO learning_observations VALUES (?,?,?,?,?,?)",
        (
            "o1",
            "ACCUM_PATH",
            cid,
            json.dumps(_good_payload()),
            "learning_observation.accumulation_discovery.v2",
            "2026-06-02T00:00:00+07:00",
        ),
    )
    conn.commit()
    conn.close()
    summary = audit_screen_filter_cohort(db, compatibility_id=cid, measure_h10=False)
    assert summary.selected_row_count == 0
    assert sufficiency_verdict(summary) == "INSUFFICIENT_NEEDS_CORPUS_EXTENSION"


def test_canonical_window_30_not_accepted():
    payload = _good_payload()
    payload["canonical_window"] = 30
    payload["features_by_window"]["30"] = payload["features_by_window"]["7"]
    ext = extract_screen_filter_inputs(payload)
    assert ext.is_unextractable
    assert ext.unextractable_reason == "canonical_window_not_7"


def test_gate_ids_stable():
    assert GATE_MARKET_CAP.startswith("screen.accum.")
    assert GATE_PIOTROSKI.startswith("screen.accum.")
    assert GATE_ACCUM_SCORE.startswith("screen.accum.")
    assert GATE_SIGNAL_SCORE.startswith("screen.accum.")
