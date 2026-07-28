"""Phase 6 — phase-2 curriculum chapters 9–18."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.chapters.loader import has_chapter_module, load_chapter
from ml_saham.chapters.types import ChapterContext
from ml_saham.cli.app import app
from ml_saham.data.doctor_checks import format_doctor_report, run_doctor
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()

PHASE2_SLUGS = [
    "headline-tone",
    "volatility-sizing",
    "market-regime",
    "walk-forward",
    "portfolio-small",
    "corp-events",
    "earnings-surprise",
    "pre-open-rank",
    "research-pipeline",
    "seasonality-drift",
    "analyst-consensus",
    "broker-accumulation",
    "sector-breadth",
    "volatility-squeeze",
    "relative-strength",
    "financial-quality",
    "financial-distress",
    "ichimoku-cloud",
    "bandar-detector",
    "forward-valuation",
    "special-monitoring",
]
OPTIONAL_SLUGS = ["rl-sandbox"]


@pytest.fixture(autouse=True)
def _isolate_progress(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ML_SAHAM_HOME", str(tmp_path / "home"))


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "mvp.db", min_bars=80)


def test_doctor_phase2(fixture_db: Path):
    report = run_doctor(fixture_db)
    assert report.mvp_hard_ok
    assert report.phase2_hard_ok
    text = format_doctor_report(report)
    assert "Phase-2 data:" in text
    assert "earnings_cache" in text
    assert "iev_snapshots" in text
    assert "headlines" in text  # soft missing OK


@pytest.mark.parametrize("slug", PHASE2_SLUGS + OPTIONAL_SLUGS)
def test_phase2_modules(slug: str):
    assert has_chapter_module(slug)
    mod = load_chapter(slug)
    assert "Masalah" in mod.explore_text()
    assert "Deep-dive" in mod.deepdive_text()


@pytest.mark.parametrize("slug", PHASE2_SLUGS + OPTIONAL_SLUGS)
def test_phase2_explore_cli(fixture_db: Path, slug: str):
    r = runner.invoke(
        app, ["--db", str(fixture_db), "explore", slug, "--no-pager"]
    )
    assert r.exit_code == 0, r.stdout


@pytest.mark.parametrize("slug", PHASE2_SLUGS + OPTIONAL_SLUGS)
def test_phase2_demo_fixture(fixture_db: Path, slug: str, tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "arts"),
            "demo",
            slug,
            "--no-artifact",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "Bukan saran" in r.stdout or "bukan saran" in r.stdout.lower()


def test_pre_open_uses_open_session_banner(fixture_db: Path):
    result = load_chapter("pre-open-rank").run_demo(
        ChapterContext(db_path=fixture_db, universe=[])
    )
    assert result.scoreboard_kind == "open_session"


def test_headline_marks_synthetic(fixture_db: Path):
    result = load_chapter("headline-tone").run_demo(
        ChapterContext(db_path=fixture_db, universe=[])
    )
    joined = "\n".join(result.lines).lower()
    assert "sintetis" in joined or "synthetic" in joined


def test_chapters_lists_phase2(fixture_db: Path):
    r = runner.invoke(app, ["--db", str(fixture_db), "chapters"])
    assert r.exit_code == 0
    assert "walk-forward" in r.stdout
    assert "pre-open-rank" in r.stdout


def test_export_json_and_md(fixture_db: Path, tmp_path: Path):
    json_path = tmp_path / "out.json"
    md_path = tmp_path / "out.md"
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "demo",
            "clean-prices",
            "--export-json",
            str(json_path),
            "--export-md",
            str(md_path),
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert json_path.is_file()
    assert md_path.is_file()
    assert "clean-prices" in json_path.read_text()
    assert "CUSUM" in md_path.read_text()
