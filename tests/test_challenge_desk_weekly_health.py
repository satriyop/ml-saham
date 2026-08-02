"""Weekly Control Tower ritual: last health pack + health run request discipline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ml_saham.challenge.types import HealthReportResult
from ml_saham.challenge.workbench import build_challenge_workbench
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "mvp.db")


def _health_pack(art: Path, name: str = "20260802_100000") -> Path:
    pack = art / "challenge" / "health" / name
    pack.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 3,
        "mode": "challenge_health",
        "engine_id": "screener",
        "with_diagnostics": True,
        "with_factors": False,
        "with_champion": False,
        "created_at": "2026-08-02T10:00:00+07:00",
        "n_index": 2,
    }
    (pack / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (pack / "index.json").write_text(
        json.dumps(
            [
                {
                    "section": "engine",
                    "policy_id": "screener.accum.score_weights",
                    "status": "INCONCLUSIVE",
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
    (pack / "summary.md").write_text("# Health\n", encoding="utf-8")
    return pack


def test_latest_health_pack_none(tmp_path: Path):
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=tmp_path / "art",
    )
    latest = service.latest_health_pack()
    assert latest.found is False
    assert latest.artifact_path is None


def test_latest_health_pack_picks_newest(tmp_path: Path):
    art = tmp_path / "art"
    _health_pack(art, "20260801_090000")
    newer = _health_pack(art, "20260802_100000")
    # bump mtime order: touch newer after older already written
    newer.joinpath("manifest.json").write_text(
        newer.joinpath("manifest.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=art,
    )
    latest = service.latest_health_pack()
    assert latest.found is True
    assert latest.artifact_path is not None
    assert latest.engine_id == "screener"
    assert latest.with_diagnostics is True
    assert latest.n_index == 2


def test_health_request_requires_compatibility(tmp_path: Path, fixture_db: Path):
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    with pytest.raises(ValueError, match="compatibility_id"):
        service.build_health_run_request(compatibility_id="— no selection —")


def test_health_run_idempotent_and_uses_build_health_report(
    tmp_path: Path, fixture_db: Path
):
    service = build_challenge_workbench(
        db_path=fixture_db,
        artifacts_root=tmp_path / "art",
    )
    request = service.build_health_run_request(
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        with_diagnostics=True,
        write_artifact=False,
    )
    fake = HealthReportResult(
        engine_id="screener",
        scenario_filter=None,
        with_champion=False,
        with_factors=False,
        with_diagnostics=True,
        summary_md="# ok\n",
        lines=["HEALTH_COMPLETE"],
        notes=[],
        index=[
            {
                "section": "engine",
                "policy_id": "screener.accum.score_weights",
                "status": "BLOCKED_POLICY",
            }
        ],
        artifact_dir=tmp_path / "art" / "challenge" / "health" / "x",
    )
    keys: set[str] = set()
    attempt = service.new_attempt_id()
    with patch(
        "ml_saham.challenge.workbench.build_health_report",
        return_value=fake,
    ) as mocked:
        first = service.execute_health_run(
            request, attempt_id=attempt, executed_keys=keys
        )
        second = service.execute_health_run(
            request, attempt_id=attempt, executed_keys=keys
        )
    assert mocked.call_count == 1
    assert first.kind == "product_result"
    assert first.status.startswith("BLOCKED")
    assert first.index
    assert second.status == "DUPLICATE_ATTEMPT"
    assert second.kind == "application_error"


def test_streamlit_tower_still_loads(monkeypatch, tmp_path: Path, fixture_db: Path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    art = tmp_path / "artifacts"
    _health_pack(art)
    monkeypatch.setenv("ML_SAHAM_DB", str(fixture_db))
    monkeypatch.setenv("ML_SAHAM_ARTIFACTS", str(art))
    app_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ml_saham"
        / "ui"
        / "streamlit_app.py"
    )
    rendered = AppTest.from_file(str(app_path), default_timeout=15).run()
    assert not rendered.exception
