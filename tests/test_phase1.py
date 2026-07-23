"""Phase 1: doctor, loaders, universe, scoreboard."""

from pathlib import Path

from typer.testing import CliRunner

from ml_saham.cli.app import app
from ml_saham.data.aisaham_read import (
    connect,
    has_ihsg,
    load_candles,
    load_latest_fundamentals,
)
from ml_saham.data.doctor_checks import format_doctor_report, run_doctor
from ml_saham.data.universe import default_universe
from ml_saham.eval import DISCLAIMER_ID, default_banners
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


def test_doctor_missing_file(tmp_path: Path):
    report = run_doctor(tmp_path / "nope.db")
    assert not report.db_exists
    assert not report.mvp_hard_ok
    text = format_doctor_report(report)
    assert "missing" in text


def test_doctor_fixture_ok(tmp_path: Path):
    db = build_mvp_fixture(tmp_path / "mvp.db")
    report = run_doctor(db)
    assert report.db_exists
    assert report.mvp_hard_ok
    assert report.mvp.status in {"ok", "partial"}
    assert len(report.universe_tickers) >= 2
    assert "BBCA" in report.universe_tickers


def test_doctor_fixture_empty_fails_hard(tmp_path: Path):
    db = build_mvp_fixture(tmp_path / "empty.db", with_hard=False)
    report = run_doctor(db)
    assert report.db_exists
    assert not report.mvp_hard_ok


def test_loaders_and_universe(tmp_path: Path):
    db = build_mvp_fixture(tmp_path / "mvp.db")
    with connect(db) as conn:
        assert has_ihsg(conn)
        candles = load_candles(conn, ["BBCA"])
        assert len(candles) >= 60
        fundies = load_latest_fundamentals(conn, ["BBCA"])
        assert fundies and fundies[0]["ticker"] == "BBCA"
        uni = default_universe(conn, min_bars=60)
        assert "BBCA" in uni
        assert "IHSG" not in uni


def test_scoreboard_banners():
    b = default_banners()
    text = b.render()
    assert "long-only vs IHSG" in text
    assert DISCLAIMER_ID in text
    assert text.startswith("⚠")


def test_doctor_cli_exit_codes(tmp_path: Path):
    missing = runner.invoke(app, ["--db", str(tmp_path / "x.db"), "doctor"])
    assert missing.exit_code == 1

    db = build_mvp_fixture(tmp_path / "mvp.db")
    ok = runner.invoke(app, ["--db", str(db), "doctor"])
    assert ok.exit_code == 0
    assert "MVP data:" in ok.stdout
    assert "Universe default:" in ok.stdout

    empty = build_mvp_fixture(tmp_path / "empty.db", with_hard=False)
    bad = runner.invoke(app, ["--db", str(empty), "doctor"])
    assert bad.exit_code == 1
