"""Phase 3 MVP chapter smoke tests (fixture DB where possible)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.chapters.loader import has_chapter_module, load_chapter
from ml_saham.chapters.orientasi import explore_text as orientasi_explore
from ml_saham.chapters.types import ChapterContext
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()

MVP_SLUGS = [
    "orientasi",
    "clean-prices",
    "screen-rules",
    "pattern-fail",
    "factor-score",
    "broker-flow",
]


@pytest.fixture(autouse=True)
def _isolate_progress(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ML_SAHAM_HOME", str(tmp_path / "home"))


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "mvp.db", min_bars=80)


def test_all_mvp_modules_load():
    for slug in MVP_SLUGS:
        assert has_chapter_module(slug)
        mod = load_chapter(slug)
        assert callable(mod.explore_text)
        assert callable(mod.run_demo)


def test_orientasi_explore_mentions_pit():
    text = orientasi_explore()
    assert "fetched_date" in text
    assert "IHSG" in text


def test_orientasi_demo_fixture(fixture_db: Path):
    mod = load_chapter("orientasi")
    result = mod.run_demo(ChapterContext(db_path=fixture_db, universe=[]))
    assert result.metrics["mvp_hard_ok"] is True
    assert result.metrics["universe_n"] >= 2
    assert result.scoreboard is True


def test_clean_prices_demo_fixture(fixture_db: Path):
    mod = load_chapter("clean-prices")
    result = mod.run_demo(
        ChapterContext(db_path=fixture_db, universe=["BBCA", "BBRI"])
    )
    assert "n_flagged" in result.metrics


def test_pattern_fail_conclusion(fixture_db: Path):
    mod = load_chapter("pattern-fail")
    result = mod.run_demo(ChapterContext(db_path=fixture_db, universe=[]))
    assert result.scoreboard is False
    assert result.metrics["conclusion"] == "wrong_question_easy_overfit"
    assert "factor-score" in "\n".join(result.lines)


def test_explore_cli_orientasi(fixture_db: Path):
    r = runner.invoke(
        app,
        ["--db", str(fixture_db), "explore", "orientasi", "--no-pager"],
    )
    assert r.exit_code == 0, r.stdout
    assert "fetched_date" in r.stdout


def test_demo_orientasi_cli_artifact(fixture_db: Path, tmp_path: Path):
    arts = tmp_path / "arts"
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(arts),
            "demo",
            "orientasi",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "Artifact:" in r.stdout
    packs = list((arts / "orientasi").glob("*_demo"))
    assert packs
    assert (packs[0] / "manifest.json").is_file()
    assert (packs[0] / "metrics.json").is_file()


def test_screen_factor_broker_demos(fixture_db: Path):
    for slug in ("screen-rules", "factor-score", "broker-flow"):
        mod = load_chapter(slug)
        result = mod.run_demo(ChapterContext(db_path=fixture_db, universe=[]))
        assert result.metrics.get("n") or result.metrics.get("n_tickers")
        assert result.scoreboard is True


def test_compare_screen_and_factor(fixture_db: Path):
    screen = load_chapter("screen-rules")
    c1 = screen.run_compare(
        ChapterContext(db_path=fixture_db, universe=[]),
        baseline="hand",
        against="tree",
    )
    assert "rank_ic" in c1.compare["baseline"]

    factor = load_chapter("factor-score")
    c2 = factor.run_compare(
        ChapterContext(db_path=fixture_db, universe=[]),
        baseline="equal-weight",
        against="elastic-net",
    )
    assert c2.compare["against"]["rank_ic"] is not None
