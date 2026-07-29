"""Challenge acceptance — ENGINE_FACTORS contract + fixture smoke (ADR-001)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.chapters.loader import has_chapter_module, load_chapter
from ml_saham.chapters.types import ChapterContext
from ml_saham.cli.app import app
from ml_saham.eval.challenge import (
    ENGINE_FACTORS,
    all_engine_slugs,
    challenge_engine,
    challenge_other,
    challenge_screener,
    challenge_summary,
    run_full_challenge,
)
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()

ENGINE_SLUGS = all_engine_slugs()


@pytest.fixture(autouse=True)
def _isolate_progress(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ML_SAHAM_HOME", str(tmp_path / "home"))


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    # slightly longer history for walk-forward / seasonality-style splits
    return build_mvp_fixture(tmp_path / "challenge.db", min_bars=100)


@pytest.fixture
def chapter_ctx(fixture_db: Path) -> ChapterContext:
    return ChapterContext(db_path=fixture_db, universe=[])


def test_engine_factors_nonempty_and_unique():
    assert set(ENGINE_FACTORS) >= {
        "screener",
        "signal_engine",
        "risk_engine",
        "market_context",
        "other_aspects",
    }
    slugs = ENGINE_SLUGS
    assert len(slugs) >= 30
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize("slug", ENGINE_SLUGS)
def test_engine_factor_has_run_compare(slug: str):
    assert has_chapter_module(slug), slug
    mod = load_chapter(slug)
    assert hasattr(mod, "run_compare"), f"{slug} missing run_compare"
    assert callable(mod.run_compare)


@pytest.mark.parametrize("slug", ENGINE_SLUGS)
def test_engine_factor_compare_smoke(chapter_ctx: ChapterContext, slug: str):
    """Every challenge factor must run_compare on the fixture without error."""
    mod = load_chapter(slug)
    from ml_saham.eval.challenge import _compare_kwargs

    result = mod.run_compare(chapter_ctx, **_compare_kwargs(slug, mod.run_compare))
    assert result is not None
    assert getattr(result, "title", None)
    # metrics dict present (may be empty for some labs)
    assert hasattr(result, "metrics")


def test_run_full_challenge_ok_rate(chapter_ctx: ChapterContext):
    results = run_full_challenge(chapter_ctx)
    # Flatten group maps
    flat: dict = {}
    for group, payload in results.items():
        assert isinstance(payload, dict), group
        flat.update(payload)

    summary = {
        "n_total": len(flat),
        "n_ok": sum(1 for v in flat.values() if not v.get("error")),
        "n_error": sum(1 for v in flat.values() if v.get("error")),
        "errors": {k: v.get("error") for k, v in flat.items() if v.get("error")},
    }
    assert summary["n_total"] == len(ENGINE_SLUGS), summary
    assert summary["n_error"] == 0, summary["errors"]
    assert summary["n_ok"] == summary["n_total"]


def test_challenge_group_runners(chapter_ctx: ChapterContext):
    scr = challenge_screener(chapter_ctx)
    eng = challenge_engine(chapter_ctx)
    oth = challenge_other(chapter_ctx)
    assert scr and eng and oth
    assert all(not v.get("error") for v in scr.values()), scr
    assert all(not v.get("error") for v in eng.values()), eng
    assert all(not v.get("error") for v in oth.values()), oth


def test_challenge_cli_exports(fixture_db: Path, tmp_path: Path):
    json_path = tmp_path / "challenge.json"
    md_path = tmp_path / "challenge.md"
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "legacy",
            "all",
            "--export-json",
            str(json_path),
            "--export-md",
            str(md_path),
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "LEGACY ENGINE CHALLENGE" in r.stdout or "CHALLENGE" in r.stdout
    text = json_path.read_text()
    assert "screener" in text
    assert "signal_engine" in text or "engine" in text or "meta-ensemble" in text
    assert md_path.is_file() and md_path.stat().st_size > 50


def test_challenge_screener_scenario_cli(fixture_db: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "legacy",
            "screener",
            "--scenario",
            "accum",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "accum" in r.stdout.lower() or "ACCUM" in r.stdout or "policy" in r.stdout.lower()


def test_challenge_summary_helper(chapter_ctx: ChapterContext):
    # Single-group map
    res = challenge_screener(chapter_ctx)
    summary = challenge_summary({"screener": res})
    assert summary["n_ok"] == summary["n_total"]
    assert summary["n_error"] == 0


def test_data_integrity_in_engine_map_and_compare(chapter_ctx: ChapterContext):
    assert "data-integrity" in ENGINE_FACTORS["other_aspects"]
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
