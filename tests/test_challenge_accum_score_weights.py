"""ADR-002: screener.accum.score_weights policy tournament."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.metrics import time_purged_folds
from ml_saham.challenge.panel import PanelRow, build_panel, extract_components
from ml_saham.challenge.policies.registry import list_policy_ids, load_policy
from ml_saham.challenge.protocols import ACCUM_PATH_V1
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.scorers import score_equal_sleeves, score_production
from ml_saham.challenge.types import ChallengeStatus
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    # Need depth for H=20 + folds
    return build_mvp_fixture(tmp_path / "accum.db", min_bars=120)


def test_policy_registry_loads():
    ids = list_policy_ids()
    assert "screener.accum.score_weights" in ids
    pol = load_policy("screener.accum.score_weights")
    assert pol.hash == ""
    assert pol.source == "ML adapter fixture; not production authority"
    assert any(c.key == "consistency" and c.enabled for c in pol.components)
    assert any(
        c.key == "bci" and c.enabled and abs(c.weight - 12.5) < 1e-9
        for c in pol.components
    )
    assert any(c.key == "bb_squeeze" and not c.enabled for c in pol.components)
    assert abs(pol.max_score - 100.0) < 1e-9


def test_production_scorer_sums_components():
    pol = load_policy("screener.accum.score_weights")
    row = PanelRow(
        ticker="BBCA",
        date="2024-02-01",
        components={c.key: c.weight for c in pol.enabled_components()},
        excess={10: 0.01},
    )
    s = score_production([row], pol)[0]
    assert abs(s - sum(c.weight for c in pol.enabled_components())) < 1e-6
    eq = score_equal_sleeves([row], pol)[0]
    assert abs(eq - 1.0) < 1e-6


def test_extract_components_from_flow_signals():
    pol = load_policy("screener.accum.score_weights")
    payload = {
        "signal": {
            "flow_evidence": {
                "flow_signals": [
                    {"key": "cons", "score": 10.0},
                    {"key": "streak", "score": 8.0},
                    {"key": "vwap", "score": 5.0},
                    {"key": "flow", "score": 3.0},
                    {"key": "rsi", "score": 2.0},
                    {"key": "inst", "score": 4.0},
                ]
            }
        },
        "sub_signal_fingerprint": {
            "sector_breadth": 0.7,
        },
    }
    comps = extract_components(payload, pol)
    assert comps is not None
    assert comps["consistency"] == 10.0
    assert comps["bci"] == 4.0
    assert comps["sector_breadth"] == pytest.approx(0.7 * 10.0)
    assert (
        "bb_squeeze" not in comps
    )  # disabled not required in output keys of enabled only
    assert "consistency" in comps


def test_extract_components_from_adr056_features_by_window():
    """Regression: live ai-saham payloads use features_by_window + score_points."""
    pol = load_policy("screener.accum.score_weights")
    payload = {
        "ticker": "BBCA",
        "session_date": "2026-07-23T00:00:00",
        "canonical_window": 7,
        "features_by_window": {
            "7": {
                "candidate": {
                    "accum_score_breakdown": {
                        "components": [
                            {"key": "cons", "score_points": 9.5, "max_points": 33.3},
                            {"key": "streak", "score_points": 3.3, "max_points": 25.0},
                            {"key": "vwap", "score_points": 4.0, "max_points": 16.7},
                            {"key": "flow", "score_points": 2.0, "max_points": 12.5},
                            {"key": "rsi", "score_points": 1.7, "max_points": 12.5},
                            {"key": "inst", "score_points": 5.0, "max_points": 8.3},
                            {
                                "key": "sector_breadth",
                                "score_points": 10.0,
                                "max_points": 10.0,
                            },
                        ],
                        "breakdown": {
                            "cons": 9.5,
                            "streak": 3.3,
                            "vwap": 4.0,
                            "flow": 2.0,
                            "rsi": 1.7,
                            "inst": 5.0,
                            "sector_breadth": 10.0,
                            "bb": None,
                        },
                    }
                }
            },
            "30": {"candidate": {}},
        },
    }
    comps = extract_components(payload, pol)
    assert comps is not None
    assert comps["consistency"] == 9.5
    assert comps["streak"] == 3.3
    assert comps["vwap_discount"] == 4.0
    assert comps["foreign_flow_ratio"] == 2.0
    assert comps["rsi_headroom"] == 1.7
    assert comps["bci"] == 5.0
    assert comps["sector_breadth"] == 10.0
    assert "bb_squeeze" not in comps


def test_extract_prefers_canonical_window_over_other_lookbacks():
    pol = load_policy("screener.accum.score_weights")
    payload = {
        "canonical_window": "7",
        "features_by_window": {
            "30": {
                "candidate": {
                    "accum_score_breakdown": {
                        "components": [
                            {"key": "cons", "score_points": 99.0},
                            {"key": "streak", "score_points": 99.0},
                            {"key": "vwap", "score_points": 99.0},
                        ]
                    }
                }
            },
            "7": {
                "candidate": {
                    "accum_score_breakdown": {
                        "components": [
                            {"key": "cons", "score_points": 1.0},
                            {"key": "streak", "score_points": 2.0},
                            {"key": "vwap", "score_points": 3.0},
                        ]
                    }
                }
            },
        },
    }
    comps = extract_components(payload, pol)
    assert comps is not None
    assert comps["consistency"] == 1.0
    assert comps["streak"] == 2.0
    assert comps["vwap_discount"] == 3.0


def test_panel_and_folds(fixture_db: Path):
    pol = load_policy("screener.accum.score_weights")
    rows, notes = build_panel(
        fixture_db,
        pol,
        horizons=ACCUM_PATH_V1.horizons_report,
        primary_horizon=ACCUM_PATH_V1.primary_horizon,
    )
    assert len(rows) >= ACCUM_PATH_V1.min_n_total, notes
    assert all(10 in r.excess for r in rows)
    folds = time_purged_folds(rows, ACCUM_PATH_V1)
    assert folds


def test_run_policy_challenge_fixture(fixture_db: Path, tmp_path: Path):
    result = run_policy_challenge(
        fixture_db,
        "screener.accum.score_weights",
        against="equal_sleeves",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert result.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
    }
    assert result.n_rows >= ACCUM_PATH_V1.min_n_total
    assert result.primary_horizon == 10
    assert "10" in (result.horizon_metrics.get("baseline") or {})
    assert result.artifact_dir is not None
    assert (result.artifact_dir / "manifest.json").is_file()
    manifest = (result.artifact_dir / "manifest.json").read_text(encoding="utf-8")
    for expected in (
        result.observation_compatibility_id,
        result.production_snapshot_id,
        result.production_snapshot_digest,
        result.production_policy_id,
        result.production_semantic_engine_contract_id,
        result.challenge_adapter_id,
        result.challenge_adapter_version,
        result.protocol_id,
    ):
        assert expected and expected in manifest
    assert result.exit_code() == 0


def test_run_ridge_challenger(fixture_db: Path, tmp_path: Path):
    result = run_policy_challenge(
        fixture_db,
        against="ridge_reweight",
        write_artifact=False,
        artifacts_dir=tmp_path / "arts",
    )
    assert result.status != ChallengeStatus.BLOCKED_POLICY
    assert result.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
        ChallengeStatus.BLOCKED_DATA,
    }


def test_cli_challenge_list_and_run(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(app, ["--db", str(fixture_db), "challenge", "list"])
    assert r.exit_code == 0, r.stdout
    assert "screener.accum.score_weights" in r.stdout

    r2 = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "run",
            "screener.accum.score_weights",
            "--against",
            "equal_sleeves",
            "--no-artifact",
        ],
    )
    assert r2.exit_code in (0, 2), r2.stdout
    assert "POLICY CHALLENGE" in r2.stdout or "BLOCKED" in r2.stdout


def test_blocked_without_db(tmp_path: Path):
    missing = tmp_path / "nope.db"
    result = run_policy_challenge(missing, write_artifact=False)
    assert result.status == ChallengeStatus.BLOCKED_DATA
    assert result.exit_code() == 2
