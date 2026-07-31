"""Challenge health control-tower recipe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.health import build_health_report
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "health.db", min_bars=120)


def test_health_engine_only_fixture(fixture_db: Path, tmp_path: Path):
    result = build_health_report(
        fixture_db,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert result.exit_code() == 0
    assert result.resolve_error is None
    assert result.artifact_dir is not None
    assert (result.artifact_dir / "manifest.json").is_file()
    assert (result.artifact_dir / "summary.md").is_file()
    assert (result.artifact_dir / "engine.json").is_file()
    assert (result.artifact_dir / "index.json").is_file()
    manifest = json.loads(
        (result.artifact_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["production_identities"]
    assert {
        "observation_compatibility_id",
        "production_snapshot_id",
        "production_snapshot_digest",
        "production_policy_id",
        "production_policy_version",
        "production_semantic_engine_contract_id",
        "challenge_adapter_id",
        "challenge_adapter_version",
    } <= set(manifest["production_identities"][0])
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
            "--compatibility-id",
            "sha256:fixture_cohort_primary",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "HEALTH" in r.stdout or "health" in r.stdout.lower()


def test_challenge_list_is_catalog_entry_with_ritual_digs(fixture_db: Path):
    """CLI catalog surfaces all policies + weekly/dig ritual (not a parallel catalog)."""
    r = runner.invoke(app, ["--db", str(fixture_db), "challenge", "list"])
    assert r.exit_code == 0, r.stdout
    out = r.stdout
    assert "catalog" in out.lower() or "Policy catalog" in out
    for pid in (
        "screener.accum.score_weights",
        "signal.accum.raw_score",
        "risk.accum.hard_gates",
    ):
        assert pid in out
    assert "health --with-diagnostics" in out
    assert "engine signal" in out or "signal|risk" in out
    assert "PROMOTE_CANDIDATE" in out
    assert "ENTER" in out or "Action" in out


def test_health_next_digs_codify_ritual_and_no_action_from_diagnostics(
    fixture_db: Path,
):
    result = build_health_report(
        fixture_db,
        with_diagnostics=True,
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert result.exit_code() == 0
    md = result.summary_md
    assert "challenge list" in md
    assert "health --with-diagnostics" in md
    assert "engine signal" in md
    assert "engine risk" in md
    assert "never set TradeSetup Action" in md.lower() or "never Action" in md
    assert "P4" in md or "ENTER" in md
    assert "Diagnostics (display bags" in md
    assert "not Action authority" in md


def test_health_champion_flag(fixture_db: Path, tmp_path: Path):
    result = build_health_report(
        fixture_db,
        with_champion=True,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
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
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
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
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
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
            "--compatibility-id",
            FIXTURE_COMPATIBILITY_ID,
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
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert result.exit_code() == 0
    assert result.champion_payload is None
    assert any("skip champion" in n.lower() for n in result.notes)


def test_health_bad_scenario(fixture_db: Path):
    result = build_health_report(fixture_db, scenario="nope", write_artifact=False, compatibility_id=FIXTURE_COMPATIBILITY_ID)
    assert result.exit_code() == 2
    assert result.resolve_error
