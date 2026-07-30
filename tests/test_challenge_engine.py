"""ADR-002 engine portfolio (screener + --scenario)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.engines import (
    list_engines,
    normalize_scenario,
    resolve_engine_policies,
    run_engine_portfolio,
)
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "engine.db", min_bars=120)


def test_list_engines():
    engines = list_engines()
    ids = {e["engine_id"] for e in engines}
    assert {"screener", "signal", "risk"} <= ids
    scr = next(e for e in engines if e["engine_id"] == "screener")
    assert "accum" in scr["scenarios"]
    assert "pre-open" in scr["scenarios"]
    assert scr["n_policies"] == 3
    sig = next(e for e in engines if e["engine_id"] == "signal")
    assert "signal.accum.raw_score" in sig["policies"]["accum"]
    assert "signal.accum.flags" in sig["policies"]["accum"]
    assert "signal.accum.classification" in sig["policies"]["accum"]
    assert "signal.accum.evidence_group_weights" in sig["policies"]["accum"]
    assert sig["n_policies"] == 4
    risk = next(e for e in engines if e["engine_id"] == "risk")
    assert "risk.accum.hard_gates" in risk["policies"]["accum"]


def test_normalize_scenario():
    assert normalize_scenario(None) is None
    assert normalize_scenario("accum") == "accum"
    assert normalize_scenario("pre_open") == "pre-open"
    assert normalize_scenario("pre-open") == "pre-open"
    assert normalize_scenario("PREOPEN") == "pre-open"


def test_resolve_policies():
    all_p, err = resolve_engine_policies("screener", None)
    assert err is None
    assert len(all_p) == 3
    assert {p for _, p in all_p} == {
        "screener.accum.score_weights",
        "screener.pre_open.iev_rank",
        "screener.pre_open.directional_score",
    }

    accum, err = resolve_engine_policies("screener", "accum")
    assert err is None
    assert len(accum) == 1
    assert accum[0][1] == "screener.accum.score_weights"

    pre, err = resolve_engine_policies("screener", "pre-open")
    assert err is None
    assert len(pre) == 2
    assert all(s == "pre-open" for s, _ in pre)

    _, err = resolve_engine_policies("screener", "swing")
    assert err is not None
    _, err = resolve_engine_policies("nope", None)
    assert err is not None


def test_portfolio_fixture(fixture_db: Path, tmp_path: Path):
    result = run_engine_portfolio(
        fixture_db,
        "screener",
        against="equal_sleeves",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert result.exit_code() == 0
    assert result.resolve_error is None
    assert len(result.rows) == 3
    assert "ENGINE PORTFOLIO" in "\n".join(result.lines)
    pids = {r.policy_id for r in result.rows}
    assert "screener.accum.score_weights" in pids
    for r in result.rows:
        assert r.status in {
            "WIN",
            "LOSE",
            "INCONCLUSIVE",
            "BLOCKED_DATA",
            "BLOCKED_POLICY",
            "ERROR",
        }
    assert result.artifact_dir is not None
    assert (result.artifact_dir / "rollup.json").is_file()


def test_scenario_filter_pre_open(fixture_db: Path):
    result = run_engine_portfolio(
        fixture_db,
        "screener",
        scenario="pre-open",
        write_artifact=False,
    )
    assert result.exit_code() == 0
    assert len(result.rows) == 2
    assert all(r.scenario == "pre-open" for r in result.rows)
    assert all("accum" not in r.policy_id or "pre_open" in r.policy_id for r in result.rows)
    assert not any(r.policy_id == "screener.accum.score_weights" for r in result.rows)


def test_cli_list_and_run(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(app, ["challenge", "engine", "list"])
    assert r.exit_code == 0, r.stdout
    assert "screener" in r.stdout

    out_json = tmp_path / "eng.json"
    r2 = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "engine",
            "screener",
            "--scenario",
            "accum",
            "--against",
            "equal_sleeves",
            "--no-artifact",
            "--export-json",
            str(out_json),
        ],
    )
    assert r2.exit_code == 0, r2.stdout
    assert "ENGINE PORTFOLIO" in r2.stdout
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["engine_id"] == "screener"
    assert data["scenario_filter"] == "accum"
    assert len(data["rows"]) == 1


def test_cli_bad_scenario(fixture_db: Path):
    r = runner.invoke(
        app,
        ["--db", str(fixture_db), "challenge", "engine", "screener", "--scenario", "xyz"],
    )
    assert r.exit_code == 2


def test_engine_champion_against_opt_in(fixture_db: Path):
    """Engine may opt into champion against without changing default equal_sleeves."""
    result = run_engine_portfolio(
        fixture_db,
        "screener",
        scenario="accum",
        against="lgbm_reweight",
        write_artifact=False,
    )
    assert result.exit_code() == 0
    assert result.against_id == "lgbm_reweight"
    assert len(result.rows) == 1
    assert result.rows[0].against_id == "lgbm_reweight"
