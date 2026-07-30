"""Phase 4 — MVP harden: smoke, error UX, progress."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.chapters.loader import load_chapter
from ml_saham.cli.app import app
from ml_saham.progress import mark, topic_flags
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


@pytest.mark.parametrize("slug", MVP_SLUGS)
def test_explore_smoke_nonempty(fixture_db: Path, slug: str):
    r = runner.invoke(
        app,
        ["--db", str(fixture_db), "explore", slug, "--no-pager"],
    )
    assert r.exit_code == 0, r.stdout
    assert "Masalah" in r.stdout or "Ch." in r.stdout
    assert len(r.stdout.strip()) > 80


@pytest.mark.parametrize("slug", MVP_SLUGS)
def test_demo_smoke_fixture(fixture_db: Path, slug: str, tmp_path: Path):
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


def test_deepdive_command_retired():
    r = runner.invoke(app, ["deepdive", "orientasi", "--no-artifact"])
    assert r.exit_code != 0


def test_error_ux_no_traceback_missing_db(tmp_path: Path):
    missing = tmp_path / "nope.db"
    r = runner.invoke(
        app,
        ["--db", str(missing), "demo", "factor-score", "--no-artifact"],
    )
    assert r.exit_code == 1
    out = r.stdout + (r.stderr or "")
    assert "doctor" in out.lower()
    assert "Traceback" not in out
    assert "PermissionError" not in out


def test_error_ux_empty_shell_db(tmp_path: Path):
    db = build_mvp_fixture(tmp_path / "empty.db", with_hard=False)
    r = runner.invoke(
        app,
        ["--db", str(db), "demo", "broker-flow", "--no-artifact"],
    )
    assert r.exit_code == 1
    out = r.stdout + (r.stderr or "")
    assert "doctor" in out.lower()
    assert "Traceback" not in out


def test_progress_marks_show_in_chapters(fixture_db: Path):
    mark("orientasi", "explore")
    mark("orientasi", "demo")
    r = runner.invoke(app, ["--db", str(fixture_db), "chapters"])
    assert r.exit_code == 0
    assert "E✓" in r.stdout
    assert "D✓" in r.stdout
    flags = topic_flags("orientasi")
    assert flags["explore"] and flags["demo"]


def test_no_aisaham_python_imports():
    root = Path(__file__).resolve().parents[1] / "src" / "ml_saham"
    offenders: list[str] = []
    pat = re.compile(
        r"^\s*(from|import)\s+ai[_-]?saham\b",
        re.MULTILINE,
    )
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if pat.search(text):
            offenders.append(str(path.relative_to(root.parent.parent)))
    assert offenders == []


def test_compare_screen_rules_cli(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "arts"),
            "compare",
            "screen-rules",
            "--baseline",
            "hand",
            "--against",
            "tree",
            "--no-artifact",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "rank_ic" in r.stdout.lower() or "rank IC" in r.stdout or "Hand" in r.stdout or "hand" in r.stdout


def test_chapter_data_error_message():
    from ml_saham.chapters.errors import ChapterDataError

    err = ChapterDataError("panel tipis")
    assert err.hint.startswith("Cek:")
    with pytest.raises(ChapterDataError):
        raise ChapterDataError("x")
