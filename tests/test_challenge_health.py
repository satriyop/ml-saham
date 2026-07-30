"""Challenge health control-tower recipe."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.health import build_health_report
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "health.db", min_bars=120)


def test_health_engine_only_fixture(fixture_db: Path, tmp_path: Path):
    result = build_health_report(
        fixture_db,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert result.exit_code() == 0
    assert result.resolve_error is None
    assert result.artifact_dir is not None
    assert (result.artifact_dir / "manifest.json").is_file()
    assert (result.artifact_dir / "summary.md").is_file()
    assert (result.artifact_dir / "engine.json").is_file()
    assert (result.artifact_dir / "index.json").is_file()
    assert len(result.index) >= 1
    assert "health report" in result.summary_md.lower() or "Engine" in result.summary_md
    assert "screener.accum.score_weights" in result.summary_md or any(
        i.get("policy_id") == "screener.accum.score_weights" for i in result.index
    )


def test_health_cli(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "health",
            "--scenario",
            "accum",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "HEALTH" in r.stdout or "health" in r.stdout.lower()


def test_health_champion_flag(fixture_db: Path, tmp_path: Path):
    result = build_health_report(
        fixture_db,
        with_champion=True,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert result.exit_code() == 0
    assert result.artifact_dir is not None
    # champion.json present if run completed (payload not None)
    assert result.champion_payload is not None
    assert (result.artifact_dir / "champion.json").is_file()
    assert "Champion" in result.summary_md or "champion" in result.summary_md.lower()


def test_health_factors_flag(fixture_db: Path, tmp_path: Path):
    result = build_health_report(
        fixture_db,
        with_factors=True,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert result.exit_code() == 0
    assert result.factors_payload is not None
    assert (result.artifact_dir / "factors.json").is_file()


def test_health_diagnostics_flag(fixture_db: Path, tmp_path: Path):
    result = build_health_report(
        fixture_db,
        with_diagnostics=True,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert result.exit_code() == 0
    assert result.diagnostics_payload is not None
    assert result.diagnostics_payload.get("section") == "diagnostics_display"
    assert "not Action" in (result.diagnostics_payload.get("banner") or "")
    assert (result.artifact_dir / "diagnostics.json").is_file()
    # Separate from sleeve KEEP/DEMOTE
    assert "Diagnostics (display bags" in result.summary_md
    assert "not Action authority" in result.summary_md
    # Index uses diagnostic_display, not factor KEEP
    diag_idx = [i for i in result.index if i.get("section") == "diagnostic_display"]
    if diag_idx:
        for i in diag_idx:
            st = str(i.get("status") or "")
            assert st not in ("KEEP", "DEMOTE", "DROP_CANDIDATE")
            assert "WIN" not in st and "LOSE" not in st


def test_health_cli_with_diagnostics(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "health",
            "--scenario",
            "accum",
            "--with-diagnostics",
            "--no-artifact",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "diagnostics=True" in r.stdout or "diagnostic" in r.stdout.lower()


def test_health_preopen_skips_champion(fixture_db: Path, tmp_path: Path):
    result = build_health_report(
        fixture_db,
        scenario="pre-open",
        with_champion=True,
        write_artifact=False,
    )
    assert result.exit_code() == 0
    assert result.champion_payload is None
    assert any("skip champion" in n.lower() for n in result.notes)


def test_health_bad_scenario(fixture_db: Path):
    result = build_health_report(fixture_db, scenario="nope", write_artifact=False)
    assert result.exit_code() == 2
    assert result.resolve_error
