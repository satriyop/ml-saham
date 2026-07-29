"""ADR-002: screener.pre_open.directional_score (observation / raw_score)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.factor_validity import run_factor_challenge
from ml_saham.challenge.panel_pre_open_obs import (
    extract_pre_open_components,
    build_pre_open_obs_panel,
)
from ml_saham.challenge.policies.registry import list_policy_ids, load_policy
from ml_saham.challenge.protocols import PRE_OPEN_SESSION_V1
from ml_saham.challenge.runner import list_policies, run_policy_challenge
from ml_saham.challenge.scorers import score_production
from ml_saham.challenge.types import ChallengeStatus, FactorVerdict
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "preopen_obs.db", min_bars=120)


def test_registry_loads_directional_score():
    assert "screener.pre_open.directional_score" in list_policy_ids()
    pol = load_policy("screener.pre_open.directional_score")
    assert pol.protocol_id == "pre_open_session_v1"
    assert pol.panel_kind == "pre_open_observations"
    assert pol.score_kind == "raw_score_primary"
    assert "production_raw_score" not in pol.feature_keys()
    assert "book_pressure" in pol.feature_keys()
    listed = {p["policy_id"]: p for p in list_policies()}
    assert listed["screener.pre_open.directional_score"]["protocol"] == "pre_open_session_v1"


def test_extract_requires_raw_score():
    pol = load_policy("screener.pre_open.directional_score")
    empty = {"ticker": "X", "signal": {}, "candidate": {}}
    assert extract_pre_open_components(empty, pol) is None

    partial = {
        "signal": {
            "raw_score": 55.0,
            "factors": {"book_pressure": 0.9},
        },
        "candidate": {},
    }
    assert extract_pre_open_components(partial, pol) is None  # <3 features

    good = {
        "signal": {
            "raw_score": 55.0,
            "factors": {
                "book_pressure": 0.9,
                "delta_iev_ratio": 0.1,
                "iep_gap_pct": 1.2,
                "iev_intensity": 0.02,
            },
        },
        "candidate": {"spread_pct": -30.0},
    }
    comps = extract_pre_open_components(good, pol)
    assert comps is not None
    assert comps["production_raw_score"] == 55.0
    assert comps["book_pressure"] == 0.9
    assert comps["delta_iev_ratio"] == 0.1


def test_extract_bid_offer_maps_to_book_pressure():
    pol = load_policy("screener.pre_open.directional_score")
    payload = {
        "signal": {
            "raw_score": 40.0,
            "factors": {
                "bid_offer_imbalance": 0.5,
                "delta_iev_ratio": 0.05,
                "iep_gap_pct": 0.2,
            },
        },
        "candidate": {},
    }
    comps = extract_pre_open_components(payload, pol)
    assert comps is not None
    assert comps["book_pressure"] == 0.5


def test_panel_and_tournament(fixture_db: Path, tmp_path: Path):
    pol = load_policy("screener.pre_open.directional_score")
    rows, notes = build_pre_open_obs_panel(
        fixture_db, pol, primary_horizon=PRE_OPEN_SESSION_V1.primary_horizon
    )
    assert len(rows) >= PRE_OPEN_SESSION_V1.min_n_total, notes
    assert all(0 in r.excess for r in rows)
    scores = score_production(rows[:3], pol)
    assert scores[0] == rows[0].components["production_raw_score"]

    for against in ("equal_sleeves", "ridge_reweight"):
        result = run_policy_challenge(
            fixture_db,
            "screener.pre_open.directional_score",
            against=against,
            write_artifact=False,
            artifacts_dir=tmp_path / "a",
        )
        assert result.status in {
            ChallengeStatus.WIN,
            ChallengeStatus.LOSE,
            ChallengeStatus.INCONCLUSIVE,
            ChallengeStatus.BLOCKED_DATA,
        }
        if result.status != ChallengeStatus.BLOCKED_DATA:
            assert result.primary_horizon == 0
            assert result.protocol_id == "pre_open_session_v1"
            assert result.exit_code() == 0


def test_factor_blocked(fixture_db: Path):
    r = run_factor_challenge(
        fixture_db,
        "screener.pre_open.directional_score",
        factor="book_pressure",
        write_artifact=False,
    )
    assert r.verdict == FactorVerdict.BLOCKED_POLICY


def test_cli(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(app, ["--db", str(fixture_db), "challenge", "list"])
    assert r.exit_code == 0, r.stdout
    assert "directional" in r.stdout or "pre_open" in r.stdout

    r2 = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "run",
            "screener.pre_open.directional_score",
            "--against",
            "equal_sleeves",
            "--no-artifact",
        ],
    )
    assert r2.exit_code in (0, 2), r2.stdout
    assert "POLICY CHALLENGE" in r2.stdout or "BLOCKED" in r2.stdout
