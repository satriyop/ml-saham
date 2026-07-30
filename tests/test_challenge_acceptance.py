"""Challenge acceptance — ADR-002 PolicySpec product surface (not chapter-loop)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.engines import ENGINE_POLICIES, list_engines
from ml_saham.challenge.policies.registry import list_policy_ids, load_policy
from ml_saham.challenge.protocols import PROTOCOLS, get_protocol
from ml_saham.chapters.loader import has_chapter_module, load_chapter
from ml_saham.chapters.types import ChapterContext
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_progress(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ML_SAHAM_HOME", str(tmp_path / "home"))


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "challenge.db", min_bars=100)


@pytest.fixture
def chapter_ctx(fixture_db: Path) -> ChapterContext:
    return ChapterContext(db_path=fixture_db, universe=[])


def test_policy_registry_nonempty_and_loadable():
    ids = list_policy_ids()
    assert len(ids) >= 3
    assert "screener.accum.score_weights" in ids
    assert "screener.pre_open.iev_rank" in ids
    assert "screener.pre_open.directional_score" in ids
    for pid in ids:
        snap = load_policy(pid)
        assert snap.policy_id
        assert snap.protocol_id in PROTOCOLS
        assert snap.components


def test_protocols_known():
    assert "accum_path_v1" in PROTOCOLS
    assert "pre_open_session_v1" in PROTOCOLS
    accum = get_protocol("accum_path_v1")
    assert accum.primary_horizon == 10
    pre = get_protocol("pre_open_session_v1")
    assert pre.primary_horizon == 0


def test_engine_portfolio_covers_registered_policies():
    engines = list_engines()
    assert any(e["engine_id"] == "screener" for e in engines)
    registered = set(list_policy_ids())
    portfolio: set[str] = set()
    for scenarios in ENGINE_POLICIES.values():
        for pids in scenarios.values():
            portfolio.update(pids)
    assert portfolio <= registered
    assert "screener.accum.score_weights" in portfolio


def test_challenge_list_cli():
    r = runner.invoke(app, ["challenge", "list"])
    assert r.exit_code == 0, r.stdout
    assert "screener.accum.score_weights" in r.stdout
    assert "accum_path_v1" in r.stdout or "protocol" in r.stdout.lower()


def test_challenge_run_cli(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "arts"),
            "challenge",
            "run",
            "screener.accum.score_weights",
            "--against",
            "equal_sleeves",
        ],
    )
    assert r.exit_code == 0, r.stdout
    out = r.stdout.upper()
    assert any(
        token in out
        for token in ("WIN", "LOSE", "INCONCLUSIVE", "BLOCKED")
    ), r.stdout


def test_challenge_engine_cli(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "arts"),
            "challenge",
            "engine",
            "screener",
            "--scenario",
            "accum",
            "--against",
            "equal_sleeves",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "screener" in r.stdout.lower() or "score_weights" in r.stdout


def test_challenge_legacy_removed():
    r = runner.invoke(app, ["challenge", "legacy", "all"])
    assert r.exit_code != 0
    # Typer unknown command or no such command
    combined = (r.stdout or "") + (r.stderr or "")
    assert "legacy" in combined.lower() or "No such command" in combined or r.exit_code == 2


def test_data_integrity_chapter_compare(chapter_ctx: ChapterContext):
    """Curriculum data-integrity still has run_compare (learning lab, not product authority)."""
    assert has_chapter_module("data-integrity")
    mod = load_chapter("data-integrity")
    result = mod.run_compare(chapter_ctx)
    assert "integrity" in (result.metrics or {}) or "integrity_score" in (result.metrics or {})
    assert result.title


def test_vet_and_doctor_deep_cli(fixture_db: Path):
    r = runner.invoke(app, ["--db", str(fixture_db), "doctor", "--deep"])
    assert r.exit_code == 0, r.stdout
    assert "Data integrity" in r.stdout

    r2 = runner.invoke(app, ["--db", str(fixture_db), "vet"])
    assert r2.exit_code == 0, r2.stdout
    assert "DATA PLANE VET" in r2.stdout or "Data integrity" in r2.stdout
