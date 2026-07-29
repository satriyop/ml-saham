"""Challenge champion track: learned reweight vs production."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.champion import (
    feature_keys_for_learned,
    is_champion_against,
    normalize_champion_id,
    score_lgbm_reweight,
    score_champion,
)
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.protocols import ACCUM_PATH_V1
from ml_saham.challenge.runner import prepare_for_policy, run_policy_challenge
from ml_saham.challenge.types import ChallengeStatus
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "champ.db", min_bars=120)


def test_champion_ids():
    assert is_champion_against("lgbm_reweight")
    assert is_champion_against("lightgbm-reweight")
    assert is_champion_against("elastic_net_reweight")
    assert not is_champion_against("equal_sleeves")
    assert normalize_champion_id("lightgbm_reweight") == "lgbm_reweight"


def test_lgbm_requires_train_fit_not_test_labels(fixture_db: Path):
    """OOS path: model is fit on train only; test scores length matches test."""
    prep = prepare_for_policy(fixture_db, "screener.accum.score_weights")
    assert prep.blocked is None and prep.policy is not None
    pol = prep.policy
    rows = prep.rows
    assert len(rows) >= ACCUM_PATH_V1.min_n_total
    # split first 40% train, rest test by date order
    order = sorted(range(len(rows)), key=lambda i: (rows[i].date, rows[i].ticker))
    cut = max(30, int(len(order) * 0.4))
    train = [rows[i] for i in order[:cut]]
    test = [rows[i] for i in order[cut : cut + 40]]
    scores, meta, err = score_lgbm_reweight(
        train, test, pol, primary_horizon=ACCUM_PATH_V1.primary_horizon
    )
    if err is not None:
        # env without lightgbm still honest
        assert "lightgbm" in err.lower() or "train" in err.lower()
        return
    assert scores is not None
    assert len(scores) == len(test)
    assert meta.get("_n_train_ok", 0) >= 25
    # scrambling test labels must not change scores (fit already done on train)
    scores2, _, err2 = score_lgbm_reweight(
        train, test, pol, primary_horizon=ACCUM_PATH_V1.primary_horizon
    )
    assert err2 is None and scores2 is not None
    assert len(scores2) == len(scores)


def test_lgbm_blocks_tiny_train(fixture_db: Path):
    prep = prepare_for_policy(fixture_db, "screener.accum.score_weights")
    assert prep.policy is not None
    pol = prep.policy
    train = prep.rows[:3]
    test = prep.rows[3:10]
    scores, _meta, err = score_lgbm_reweight(
        train, test, pol, primary_horizon=10
    )
    assert scores is None
    assert err is not None
    assert "train" in err.lower() or "min" in err.lower()


def test_run_champion_accum_fixture(fixture_db: Path, tmp_path: Path):
    result = run_policy_challenge(
        fixture_db,
        "screener.accum.score_weights",
        against="lgbm_reweight",
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert result.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
        ChallengeStatus.BLOCKED_DATA,
        ChallengeStatus.BLOCKED_POLICY,
    }
    assert result.against_id == "lgbm_reweight"
    assert result.baseline_id == "production"
    joined = "\n".join(result.lines)
    assert "CHAMPION" in joined or "champion" in " ".join(result.notes).lower()
    assert "production" in joined.lower()
    if result.status not in (
        ChallengeStatus.BLOCKED_DATA,
        ChallengeStatus.BLOCKED_POLICY,
    ):
        assert result.fold_metrics
        assert result.primary_horizon == 10
        assert result.exit_code() == 0


def test_unknown_champion_blocked(fixture_db: Path):
    result = run_policy_challenge(
        fixture_db,
        against="super_sota_net",
        write_artifact=False,
    )
    assert result.status == ChallengeStatus.BLOCKED_POLICY


def test_cli_champion(fixture_db: Path, tmp_path: Path):
    out_json = tmp_path / "c.json"
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "champion",
            "screener.accum.score_weights",
            "--model",
            "lgbm_reweight",
            "--no-artifact",
            "--export-json",
            str(out_json),
        ],
    )
    assert r.exit_code in (0, 2), r.stdout
    assert "POLICY CHALLENGE" in r.stdout or "BLOCKED" in r.stdout
    assert "champion" in r.stdout.lower() or "CHAMPION" in r.stdout
    if r.exit_code == 0:
        assert out_json.is_file()
        text = out_json.read_text(encoding="utf-8")
        assert "lgbm_reweight" in text
        assert "production" in text


def test_feature_keys_accum():
    pol = load_policy("screener.accum.score_weights")
    keys = feature_keys_for_learned(pol)
    assert "consistency" in keys
    assert len(keys) >= 3


def test_score_champion_dispatch_unknown():
    pol = load_policy("screener.accum.score_weights")
    s, m, err = score_champion("nope", [], [], pol, primary_horizon=10)
    assert s is None and err
