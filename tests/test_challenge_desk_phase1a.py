"""Phase 1A: Control Tower, cohort discovery, policy catalog via workbench."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ml_saham.challenge.runner import list_policies
from ml_saham.challenge.workbench import (
    CAPABILITY_AVAILABLE,
    CAPABILITY_NOT_IMPLEMENTED,
    CAPABILITY_UNAVAILABLE,
    build_challenge_workbench,
)


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _mini_obs_db(path: Path) -> None:
    """Minimal learning_observations table for cohort inventory."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE learning_observations (
                purpose TEXT NOT NULL,
                compatibility_id TEXT,
                captured_at TEXT,
                decision_payload_json TEXT
            )
            """
        )
        rows = [
            ("ACCUMULATION_DISCOVERY", "sha256:aaa", "2026-07-01T10:00:00+07:00", "{}"),
            ("ACCUMULATION_DISCOVERY", "sha256:aaa", "2026-07-02T10:00:00+07:00", "{}"),
            ("ACCUMULATION_DISCOVERY", "sha256:bbb", "2026-07-03T10:00:00+07:00", "{}"),
            (
                "PRE_OPEN_AUCTION_DIRECTION",
                "sha256:pre1",
                "2026-07-04T08:00:00+07:00",
                "{}",
            ),
        ]
        conn.executemany(
            "INSERT INTO learning_observations "
            "(purpose, compatibility_id, captured_at, decision_payload_json) "
            "VALUES (?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def test_policy_catalog_matches_list_policies_ids():
    service = build_challenge_workbench()
    catalog = service.list_policy_catalog()
    catalog_ids = [r.policy_id for r in catalog]
    list_ids = [r["policy_id"] for r in list_policies()]
    assert catalog_ids == list_ids
    assert catalog
    for row in catalog:
        assert row.readiness_capability.status == CAPABILITY_AVAILABLE
        assert "C0" in row.readiness_capability.detail
        assert row.support_status in {"registered", "error"}
        assert row.protocol_id
        assert "production" in row.supported_baselines


def test_diagnostic_catalog_labels_non_action_authority():
    service = build_challenge_workbench()
    diags = service.list_diagnostic_catalog()
    assert diags
    for d in diags:
        assert "never Action" in d.authority_note.lower() or "Action" in d.authority_note


def test_cohort_inventory_no_preselection_and_factual_only(tmp_path: Path):
    db = tmp_path / "obs.db"
    _mini_obs_db(db)
    service = build_challenge_workbench(
        db_path=db,
        artifacts_root=tmp_path / "artifacts",
    )
    inv = service.list_cohort_inventory()
    assert inv.status == "AVAILABLE"
    assert len(inv.rows) >= 2
    families = {r.purpose_family for r in inv.rows}
    assert "ACCUM" in families
    assert "PRE_OPEN" in families
    for row in inv.rows:
        assert row.observation_count >= 1
        assert row.distinct_sessions.status == CAPABILITY_NOT_IMPLEMENTED
        assert row.economic_date_range.status == CAPABILITY_NOT_IMPLEMENTED
        assert row.readiness_capability.status == CAPABILITY_NOT_IMPLEMENTED
        # Never invent fold estimates or eligibility flags
        assert not hasattr(row, "eligible")
        assert not hasattr(row, "estimated_folds")


def test_cohort_inventory_missing_db(tmp_path: Path):
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=tmp_path / "artifacts",
    )
    inv = service.list_cohort_inventory()
    assert inv.status == CAPABILITY_UNAVAILABLE
    assert inv.rows == ()
    assert inv.notes


def test_control_tower_historical_packs_only(tmp_path: Path):
    art = tmp_path / "artifacts"
    run_dir = art / "challenge" / "screener.accum.score_weights" / "20260101_120000"
    _write_manifest(
        run_dir / "manifest.json",
        {
            "schema_version": 2,
            "mode": "challenge_run",
            "track": "policy_tournament",
            "policy_id": "screener.accum.score_weights",
            "protocol_id": "accum_path_v1",
            "baseline_id": "production",
            "against_id": "equal_sleeves",
            "status": "INCONCLUSIVE",
            "created_at": "2026-01-01T12:00:00+07:00",
        },
    )
    factor_dir = (
        art
        / "challenge"
        / "factor"
        / "screener.accum.score_weights"
        / "consistency"
        / "20260101_120100"
    )
    _write_manifest(
        factor_dir / "manifest.json",
        {
            "schema_version": 2,
            "mode": "challenge_factor",
            "track": "factor_validity",
            "policy_id": "screener.accum.score_weights",
            "factor": "consistency",
            "verdict": "KEEP",
            "created_at": "2026-01-01T12:01:00+07:00",
        },
    )
    health_dir = art / "challenge" / "health" / "20260101_130000"
    _write_manifest(
        health_dir / "manifest.json",
        {
            "schema_version": 3,
            "mode": "challenge_health",
            "created_at": "2026-01-01T13:00:00+07:00",
            "n_index": 2,
        },
    )
    (health_dir / "index.json").write_text(
        json.dumps(
            [
                {
                    "section": "engine",
                    "policy_id": "screener.accum.score_weights",
                    "status": "BLOCKED_POLICY",
                    "against_id": "equal_sleeves",
                },
                {
                    "section": "diagnostic_display",
                    "diagnostic_id": "mce.screen_display",
                    "status": "KEEP_DISPLAY",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=art,
    )
    snap = service.control_tower_snapshot()
    assert snap.status == "AVAILABLE"
    statuses = {r.status for r in snap.rows}
    assert "INCONCLUSIVE" in statuses
    assert "KEEP" in statuses
    assert "BLOCKED_POLICY" in statuses
    assert "KEEP_DISPLAY" in statuses
    tracks = {r.track for r in snap.rows}
    assert "tune" in tracks
    assert "factor" in tracks
    assert "diagnostic" in tracks
    diag_rows = [r for r in snap.rows if r.track == "diagnostic"]
    assert all(r.is_diagnostic_display for r in diag_rows)


def test_control_tower_empty_artifacts(tmp_path: Path):
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=tmp_path / "empty_artifacts",
    )
    snap = service.control_tower_snapshot()
    assert snap.status == CAPABILITY_UNAVAILABLE
    assert snap.rows == ()


def test_streamlit_phase1a_pages_apptest(monkeypatch, tmp_path: Path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    db = tmp_path / "obs.db"
    _mini_obs_db(db)
    art = tmp_path / "artifacts"
    run_dir = art / "challenge" / "screener.accum.score_weights" / "t1"
    _write_manifest(
        run_dir / "manifest.json",
        {
            "schema_version": 2,
            "mode": "challenge_run",
            "track": "policy_tournament",
            "policy_id": "screener.accum.score_weights",
            "status": "WIN",
            "created_at": "2026-01-01T00:00:00+07:00",
        },
    )
    monkeypatch.setenv("ML_SAHAM_DB", str(db))
    monkeypatch.setenv("ML_SAHAM_ARTIFACTS", str(art))
    # Reset cached service if any
    app_path = Path(__file__).resolve().parents[1] / "src" / "ml_saham" / "ui" / "streamlit_app.py"
    rendered = AppTest.from_file(str(app_path), default_timeout=15).run()
    assert not rendered.exception
    text = "\n".join(
        str(getattr(el, "value", el))
        for collection in (
            rendered.title,
            rendered.caption,
            rendered.info,
            rendered.warning,
            rendered.markdown,
            rendered.text,
        )
        for el in collection
    )
    assert "Challenge Desk" in text or "ml-saham Challenge Desk" in text
    assert "Phase 2" in text or "read-only" in text.lower() or "Run" in text
