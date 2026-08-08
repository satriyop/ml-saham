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
from ml_saham.challenge.diagnostic_artifact import (
    DiagnosticArtifactError,
    verify_diagnostic_artifact,
)
from ml_saham.challenge.diagnostics.registry import (
    diagnostic_spec_content_digest,
    load_diagnostic,
    resolve_feature_key,
)
from ml_saham.challenge.types import DiagnosticVerdict
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID
from tests.fixtures.diagnostic_bindings import bind_schema15_diagnostics

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "diag.db", min_bars=120)


@pytest.fixture
def bound_fixture_db(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    path = build_mvp_fixture(tmp_path / "diag-bound.db", min_bars=120)
    import sqlite3

    with sqlite3.connect(path) as conn:
        diagnostic_ids = bind_schema15_diagnostics(
            conn, compatibility_id=FIXTURE_COMPATIBILITY_ID
        )
    return path, diagnostic_ids


def test_list_catalog():
    rows = list_diagnostic_catalog()
    ids = {r["diagnostic_id"] for r in rows}
    assert "mce.screen_display" in ids
    assert "sector.peer_context" in ids
    assert "institutional.accumulation_bag" in ids
    assert "company_quality.bag" in ids


def test_load_and_resolve_features():
    mce = load_diagnostic("mce.screen_display")
    assert mce.kind == "diagnostic"
    assert resolve_feature_key(mce, "regime") == "regime_score"
    assert resolve_feature_key(mce, "vix") == "vix"
    assert resolve_feature_key(mce, "nope") is None

    sec = load_diagnostic("sector.peer_context")
    assert resolve_feature_key(sec, "sector") == "sector_context_score"


def test_spec_content_identity_covers_spec_regime_and_extractor_contract() -> None:
    spec_data = {"diagnostic_id": "mce.screen_display", "features": [{"key": "vix"}]}
    base = diagnostic_spec_content_digest(spec_data)
    assert (
        diagnostic_spec_content_digest(
            {"diagnostic_id": "mce.screen_display", "features": [{"key": "eido"}]}
        )
        != base
    )
    assert (
        diagnostic_spec_content_digest(spec_data, regime_map={"RISK_ON": 0.9}) != base
    )
    assert (
        diagnostic_spec_content_digest(
            spec_data, extractor_contract_id="mutated.extractor"
        )
        != base
    )


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


def test_run_mce_feature_on_fixture(
    bound_fixture_db: tuple[Path, dict[str, str]], tmp_path: Path
):
    fixture_db, diagnostic_ids = bound_fixture_db
    r = run_diagnostic_challenge(
        fixture_db,
        "mce.screen_display",
        feature="regime_score",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        diagnostic_compatibility_id=diagnostic_ids["mce.screen_display"],
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
        manifest = __import__("json").loads(
            (r.artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["schema_version"] == 4
        assert manifest["non_promotable"] is True
        assert manifest["observation_schema_version"] == 15
        assert manifest["observation_compatibility_id"] == FIXTURE_COMPATIBILITY_ID
        assert (
            verify_diagnostic_artifact(r.artifact_dir, db_path=fixture_db) == manifest
        )
        assert "not Action" in r.summary_md or "ADR-057" in r.summary_md
        assert r.exit_code() == 0


def test_diagnostic_artifact_reopen_rejects_upstream_mutation(
    bound_fixture_db: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    fixture_db, diagnostic_ids = bound_fixture_db
    result = run_diagnostic_challenge(
        fixture_db,
        "sector.peer_context",
        feature="peer_breadth",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        diagnostic_compatibility_id=diagnostic_ids["sector.peer_context"],
    )
    assert result.artifact_dir is not None
    assert verify_diagnostic_artifact(result.artifact_dir, db_path=fixture_db)
    import sqlite3

    with sqlite3.connect(fixture_db) as conn:
        conn.execute(
            "UPDATE learning_diagnostic_producer_snapshots SET source_revision = ? "
            "WHERE producer_id = ?",
            ("mutated", "diagnostic.sector_peer_context"),
        )
    with pytest.raises(DiagnosticArtifactError):
        verify_diagnostic_artifact(result.artifact_dir, db_path=fixture_db)


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


def test_diagnostic_health_missing_mapping_blocks_only_that_bag(
    bound_fixture_db: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    fixture_db, diagnostic_ids = bound_fixture_db
    health = run_diagnostic_health(
        fixture_db,
        scenario="accum",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        diagnostic_compatibility_ids={
            "sector.peer_context": diagnostic_ids["sector.peer_context"]
        },
    )
    by_diagnostic = {result.diagnostic_id: result for result in health.results}
    assert by_diagnostic["mce.screen_display"].verdict == (
        DiagnosticVerdict.BLOCKED_DIAGNOSTIC_BINDING
    )
    assert by_diagnostic["institutional.accumulation_bag"].verdict == (
        DiagnosticVerdict.BLOCKED_DIAGNOSTIC_BINDING
    )
    assert any(
        result.diagnostic_id == "sector.peer_context"
        and result.verdict != DiagnosticVerdict.BLOCKED_DIAGNOSTIC_BINDING
        for result in health.results
    )
    assert health.artifact_dir is not None
    assert verify_diagnostic_artifact(health.artifact_dir, db_path=fixture_db)


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


def test_cli_requires_both_action_and_diagnostic_ids(fixture_db: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "diagnostic",
            "run",
            "sector.peer_context",
            "--all",
            "--no-artifact",
        ],
    )
    assert result.exit_code == 2
    assert "BLOCKED_DIAGNOSTIC_BINDING" in result.stdout


def test_cli_accepts_explicit_identity_pair(
    bound_fixture_db: tuple[Path, dict[str, str]],
) -> None:
    fixture_db, diagnostic_ids = bound_fixture_db
    result = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "diagnostic",
            "run",
            "sector.peer_context",
            "--all",
            "--no-artifact",
            "--compatibility-id",
            FIXTURE_COMPATIBILITY_ID,
            "--diagnostic-compatibility-id",
            diagnostic_ids["sector.peer_context"],
        ],
    )
    assert result.exit_code in (0, 2)
    assert "diagnostic_id=sector.peer_context" in result.stdout


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


def test_batch_institutional_and_cq(fixture_db: Path, tmp_path: Path):
    for did, key in (
        ("institutional.accumulation_bag", "institutional_flow_score"),
        ("company_quality.bag", "company_quality_score"),
    ):
        batch = run_diagnostic_challenge_batch(
            fixture_db,
            did,
            write_artifact=True,
            artifacts_dir=tmp_path / "arts",
        )
        if batch.blocked is None:
            assert batch.exit_code() == 0
            assert any(r.feature == key for r in batch.results)
            for r in batch.results:
                assert r.verdict.value in {
                    "KEEP_DISPLAY",
                    "DEMOTE_DISPLAY",
                    "DROP_DISPLAY",
                    "PROMOTE_CANDIDATE",
                    "INCONCLUSIVE",
                    "BLOCKED_DATA",
                    "BLOCKED_SPEC",
                }
                assert "WIN" not in r.verdict.value
                assert "LOSE" not in r.verdict.value
        else:
            assert batch.exit_code() == 2
            assert batch.blocked.value.startswith("BLOCKED")
