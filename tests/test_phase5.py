"""Phase 5 — v1.1 doctor + cluster-peers / insider / volume-anomaly."""

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

V11_SLUGS = ["cluster-peers", "insider", "volume-anomaly"]


@pytest.fixture(autouse=True)
def _isolate_progress(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ML_SAHAM_HOME", str(tmp_path / "home"))


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "mvp.db", min_bars=80)


def test_doctor_reports_v11(fixture_db: Path):
    report = run_doctor(fixture_db)
    assert report.mvp_hard_ok
    assert report.v1_1_hard_ok
    assert report.tier_ok("v1_1")
    text = format_doctor_report(report)
    assert "v1.1 data:" in text
    assert "insider_cache" in text
    assert "sector_coverage" in text
    assert "absurd" in text or "usable=" in text


def test_v11_modules_load():
    for slug in V11_SLUGS:
        assert has_chapter_module(slug)
        mod = load_chapter(slug)
        assert "Masalah" in mod.explore_text()
        assert not hasattr(mod, "deepdive_text")


@pytest.mark.parametrize("slug", V11_SLUGS)
def test_v11_explore_and_demo(fixture_db: Path, slug: str, tmp_path: Path):
    er = runner.invoke(
        app, ["--db", str(fixture_db), "explore", slug, "--no-pager"]
    )
    assert er.exit_code == 0, er.stdout
    dr = runner.invoke(
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
    assert dr.exit_code == 0, dr.stdout
    assert "Bukan saran" in dr.stdout


def test_cluster_and_volume_direct(fixture_db: Path):
    ctx = ChapterContext(db_path=fixture_db, universe=[])
    c = load_chapter("cluster-peers").run_demo(ctx)
    assert c.metrics["n_clusters"] >= 2
    v = load_chapter("volume-anomaly").run_demo(ctx)
    assert v.metrics["n_flagged"] >= 1


def test_insider_scrubs_absurd(fixture_db: Path):
    ctx = ChapterContext(db_path=fixture_db, universe=[])
    result = load_chapter("insider").run_demo(ctx)
    assert result.metrics["insider_stats"]["absurd"] >= 1
    assert result.metrics["n"] >= 8


def test_chapters_lists_v11(fixture_db: Path):
    r = runner.invoke(app, ["--db", str(fixture_db), "chapters"])
    assert r.exit_code == 0
    assert "cluster-peers" in r.stdout
    assert "insider" in r.stdout
    assert "volume-anomaly" in r.stdout
