"""ADR-002 factor validity (univariate + drop ablation)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.factor_validity import (
    list_enabled_factors,
    resolve_factor_key,
    run_factor_challenge,
)
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.scorers import score_production, score_production_drop
from ml_saham.challenge.types import FactorVerdict
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "fac.db", min_bars=120)


def test_resolve_aliases():
    pol = load_policy("screener.accum.score_weights")
    assert resolve_factor_key(pol, "cons") == "consistency"
    assert resolve_factor_key(pol, "consistency") == "consistency"
    assert resolve_factor_key(pol, "streak") == "streak"
    assert resolve_factor_key(pol, "bb_squeeze") is None  # disabled
    assert resolve_factor_key(pol, "nope") is None


def test_list_enabled_factors():
    rows = list_enabled_factors()
    keys = {r["key"] for r in rows}
    assert "consistency" in keys
    assert "bb_squeeze" not in keys


def test_score_production_drop():
    pol = load_policy("screener.accum.score_weights")
    comps = {c.key: float(c.weight) for c in pol.enabled_components()}
    row = PanelRow(ticker="X", date="2024-01-01", components=comps, excess={10: 0.01})
    full = score_production([row], pol)[0]
    drop = score_production_drop([row], pol, "consistency")[0]
    assert abs(full - drop - comps["consistency"]) < 1e-6


def test_blocked_disabled_factor(fixture_db: Path):
    r = run_factor_challenge(fixture_db, factor="bb_squeeze", write_artifact=False)
    assert r.verdict == FactorVerdict.BLOCKED_POLICY
    assert r.exit_code() == 2


def test_blocked_unknown_factor(fixture_db: Path):
    r = run_factor_challenge(fixture_db, factor="not_a_factor", write_artifact=False)
    assert r.verdict == FactorVerdict.BLOCKED_POLICY


def test_run_factor_on_fixture(fixture_db: Path, tmp_path: Path):
    r = run_factor_challenge(
        fixture_db,
        factor="consistency",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert r.verdict in {
        FactorVerdict.KEEP,
        FactorVerdict.DEMOTE,
        FactorVerdict.DROP_CANDIDATE,
        FactorVerdict.INCONCLUSIVE,
        FactorVerdict.BLOCKED_DATA,
    }
    if r.verdict not in (FactorVerdict.BLOCKED_DATA, FactorVerdict.BLOCKED_POLICY):
        assert r.factor == "consistency"
        assert r.primary_horizon == 10
        assert r.artifact_dir is not None
        assert (r.artifact_dir / "manifest.json").is_file()
        assert r.exit_code() == 0


def test_cli_list_factors_and_run(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "challenge",
            "factor",
            "screener.accum.score_weights",
            "--list-factors",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "consistency" in r.stdout

    r2 = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "factor",
            "screener.accum.score_weights",
            "--factor",
            "cons",
            "--no-artifact",
        ],
    )
    assert r2.exit_code in (0, 2), r2.stdout
    assert "FACTOR VALIDITY" in r2.stdout or "BLOCKED" in r2.stdout
