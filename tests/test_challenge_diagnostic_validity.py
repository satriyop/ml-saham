"""Diagnostic validity track (explain-only bags — not Action)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.diagnostic_validity import (
    list_diagnostic_catalog,
    list_enabled_diagnostic_features,
    run_diagnostic_challenge,
    run_diagnostic_challenge_batch,
    run_diagnostic_health,
)
from ml_saham.challenge.diagnostics.registry import load_diagnostic, resolve_feature_key
from ml_saham.challenge.types import DiagnosticVerdict
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "diag.db", min_bars=120)


def test_list_catalog():
    rows = list_diagnostic_catalog()
    ids = {r["diagnostic_id"] for r in rows}
    assert "mce.screen_display" in ids
    assert "sector.peer_context" in ids


def test_load_and_resolve_features():
    mce = load_diagnostic("mce.screen_display")
    assert mce.kind == "diagnostic"
    assert resolve_feature_key(mce, "regime") == "regime_score"
    assert resolve_feature_key(mce, "vix") == "vix"
    assert resolve_feature_key(mce, "nope") is None

    sec = load_diagnostic("sector.peer_context")
    assert resolve_feature_key(sec, "sector") == "sector_context_score"


def test_list_features():
    rows = list_enabled_diagnostic_features("mce.screen_display")
    keys = {r["key"] for r in rows}
    assert "regime_score" in keys
    assert "vix" in keys


def test_blocked_unknown_diagnostic(fixture_db: Path):
    r = run_diagnostic_challenge(
        fixture_db, "not.a.bag", feature="vix", write_artifact=False
    )
    assert r.verdict == DiagnosticVerdict.BLOCKED_SPEC
    assert r.exit_code() == 2


def test_blocked_unknown_feature(fixture_db: Path):
    r = run_diagnostic_challenge(
        fixture_db,
        "mce.screen_display",
        feature="not_a_feature",
        write_artifact=False,
    )
    assert r.verdict == DiagnosticVerdict.BLOCKED_SPEC


def test_run_mce_feature_on_fixture(fixture_db: Path, tmp_path: Path):
    r = run_diagnostic_challenge(
        fixture_db,
        "mce.screen_display",
        feature="regime_score",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert r.verdict in {
        DiagnosticVerdict.KEEP_DISPLAY,
        DiagnosticVerdict.DEMOTE_DISPLAY,
        DiagnosticVerdict.DROP_DISPLAY,
        DiagnosticVerdict.PROMOTE_CANDIDATE,
        DiagnosticVerdict.INCONCLUSIVE,
        DiagnosticVerdict.BLOCKED_DATA,
    }
    # never production WIN/LOSE language
    assert "WIN" not in r.verdict.value
    assert "LOSE" not in r.verdict.value
    if r.verdict not in (
        DiagnosticVerdict.BLOCKED_DATA,
        DiagnosticVerdict.BLOCKED_SPEC,
    ):
        assert r.feature == "regime_score"
        assert r.primary_horizon == 10
        assert r.artifact_dir is not None
        assert (r.artifact_dir / "manifest.json").is_file()
        assert "not Action" in r.summary_md or "ADR-057" in r.summary_md
        assert r.exit_code() == 0


def test_batch_sector(fixture_db: Path, tmp_path: Path):
    batch = run_diagnostic_challenge_batch(
        fixture_db,
        "sector.peer_context",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    if batch.blocked is None:
        assert batch.exit_code() == 0
        assert len(batch.results) >= 1
        keys = {r.feature for r in batch.results}
        assert "sector_context_score" in keys
        assert batch.artifact_dir is not None
        assert "DIAGNOSTIC VALIDITY BATCH" in "\n".join(batch.lines)
        assert "Action" in "\n".join(batch.lines)
    else:
        assert batch.exit_code() == 2


def test_diagnostic_health(fixture_db: Path, tmp_path: Path):
    h = run_diagnostic_health(
        fixture_db,
        scenario="accum",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    if h.blocked is None:
        assert h.exit_code() == 0
        assert len(h.results) >= 1
        assert "DIAGNOSTIC HEALTH" in "\n".join(h.lines)
    else:
        # thin data still honest
        assert h.exit_code() == 2


def test_cli_list(fixture_db: Path):
    r = runner.invoke(app, ["--db", str(fixture_db), "challenge", "diagnostic", "list"])
    assert r.exit_code == 0
    assert "mce.screen_display" in r.stdout
    assert "sector.peer_context" in r.stdout


def test_cli_run_all(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "arts"),
            "challenge",
            "diagnostic",
            "run",
            "mce.screen_display",
            "--all",
            "--no-artifact",
        ],
    )
    # 0 success or 2 blocked data — not crash
    assert r.exit_code in (0, 2)
    assert "DIAGNOSTIC" in r.stdout or "BLOCKED" in r.stdout


def test_cli_mutual_exclusion(fixture_db: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "diagnostic",
            "run",
            "mce.screen_display",
            "--all",
            "--feature",
            "vix",
        ],
    )
    assert r.exit_code == 2
