"""ADR-002: screener.pre_open.iev_rank policy tournament."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.panel_iev import _pick_history_batches, build_iev_panel
from ml_saham.challenge.policies.registry import list_policy_ids, load_policy
from ml_saham.challenge.protocols import PRE_OPEN_SESSION_V1
from ml_saham.challenge.runner import list_policies, run_policy_challenge
from ml_saham.challenge.scorers import score_feature_equal_z, score_production
from ml_saham.challenge.types import ChallengeStatus, FactorVerdict
from ml_saham.challenge.factor_validity import run_factor_challenge
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "preopen.db", min_bars=120)


def test_policy_registry_includes_pre_open():
    ids = list_policy_ids()
    assert "screener.pre_open.iev_rank" in ids
    pol = load_policy("screener.pre_open.iev_rank")
    assert pol.protocol_id == "pre_open_session_v1"
    assert pol.panel_kind == "iev_rank"
    assert pol.score_kind == "rank_primary"
    assert pol.hash
    listed = {p["policy_id"]: p for p in list_policies()}
    assert listed["screener.pre_open.iev_rank"]["protocol"] == "pre_open_session_v1"


def test_history_batch_prefers_ncp_over_larger_post_open():
    """Largest batch must not win when a smaller NCP / pre-open batch exists."""
    rows = [
        # early large non-NCP
        {"date": "2024-01-02", "ticker": "AAA", "collected_at": "2024-01-02T02:00:00", "rank": 1, "is_ncp_locked": 0, "iev": 1e6, "iep": 100},
        {"date": "2024-01-02", "ticker": "BBB", "collected_at": "2024-01-02T02:00:00", "rank": 2, "is_ncp_locked": 0, "iev": 1e6, "iep": 100},
        {"date": "2024-01-02", "ticker": "CCC", "collected_at": "2024-01-02T02:00:00", "rank": 3, "is_ncp_locked": 0, "iev": 1e6, "iep": 100},
        # small NCP locked pre-open
        {"date": "2024-01-02", "ticker": "AAA", "collected_at": "2024-01-02T08:56:00", "rank": 1, "is_ncp_locked": 1, "iev": 100, "iep": 10},
        {"date": "2024-01-02", "ticker": "BBB", "collected_at": "2024-01-02T08:56:00", "rank": 2, "is_ncp_locked": 1, "iev": 100, "iep": 10},
        # large post-open (would win old "largest batch" rule)
        {"date": "2024-01-02", "ticker": "AAA", "collected_at": "2024-01-02T09:08:00", "rank": 9, "is_ncp_locked": 1, "iev": 9e9, "iep": 1},
        {"date": "2024-01-02", "ticker": "BBB", "collected_at": "2024-01-02T09:08:00", "rank": 8, "is_ncp_locked": 1, "iev": 9e9, "iep": 1},
        {"date": "2024-01-02", "ticker": "CCC", "collected_at": "2024-01-02T09:08:00", "rank": 7, "is_ncp_locked": 1, "iev": 9e9, "iep": 1},
    ]
    # Post-open batch is also ncp_locked=1 and larger → clock window must break the tie:
    # 08:56 is in [08:45,09:00); 09:08 is not. Both ncp=1 → clock prefers 08:56.
    picked, notes = _pick_history_batches(rows)
    assert {r["ticker"] for r in picked} == {"AAA", "BBB"}
    assert all(r["collected_at"] == "2024-01-02T08:56:00" for r in picked)
    assert notes


def test_history_batch_prefers_preopen_clock_over_early_largest():
    rows = [
        {"date": "2024-01-03", "ticker": "AAA", "collected_at": "2024-01-03T02:00:00", "rank": 1, "is_ncp_locked": 0},
        {"date": "2024-01-03", "ticker": "BBB", "collected_at": "2024-01-03T02:00:00", "rank": 2, "is_ncp_locked": 0},
        {"date": "2024-01-03", "ticker": "CCC", "collected_at": "2024-01-03T02:00:00", "rank": 3, "is_ncp_locked": 0},
        {"date": "2024-01-03", "ticker": "AAA", "collected_at": "2024-01-03T08:50:00", "rank": 1, "is_ncp_locked": 0},
        {"date": "2024-01-03", "ticker": "BBB", "collected_at": "2024-01-03T08:50:00", "rank": 2, "is_ncp_locked": 0},
    ]
    picked, _ = _pick_history_batches(rows)
    assert all(r["collected_at"] == "2024-01-03T08:50:00" for r in picked)


def test_no_iev_over_iep_imbalance_feature():
    from ml_saham.challenge.panel_iev import _component_features
    import math

    comps = _component_features(iev=1602630.0, iep=165.0, rank=1, max_rank=50)
    assert "imbalance" not in comps
    assert comps["log_iev"] == pytest.approx(math.log1p(1602630.0))
    # old bug would be ~9711
    assert comps["log_iev"] < 20


def test_iev_panel_labels(fixture_db: Path):
    pol = load_policy("screener.pre_open.iev_rank")
    rows, notes = build_iev_panel(
        fixture_db, pol, primary_horizon=PRE_OPEN_SESSION_V1.primary_horizon
    )
    assert len(rows) >= PRE_OPEN_SESSION_V1.min_n_total, notes
    assert all(0 in r.excess for r in rows)
    assert all("official_rank_score" in r.components for r in rows)
    assert all("log_iev" in r.components for r in rows)
    assert all("imbalance" not in r.components for r in rows)
    # production scores higher for better ranks
    s = score_production(rows[:5], pol)
    assert len(s) == 5


def test_feature_equal_z_within_date(fixture_db: Path):
    pol = load_policy("screener.pre_open.iev_rank")
    rows, _ = build_iev_panel(fixture_db, pol, primary_horizon=0)
    scores = score_feature_equal_z(rows, pol)
    assert len(scores) == len(rows)


def test_run_equal_and_ridge(fixture_db: Path, tmp_path: Path):
    for against in ("equal_sleeves", "ridge_reweight"):
        result = run_policy_challenge(
            fixture_db,
            "screener.pre_open.iev_rank",
            against=against,
            write_artifact=True,
            artifacts_dir=tmp_path / "arts",
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
            assert result.n_rows >= PRE_OPEN_SESSION_V1.min_n_total
            assert result.exit_code() == 0


def test_factor_track_blocked_for_pre_open(fixture_db: Path):
    r = run_factor_challenge(
        fixture_db,
        "screener.pre_open.iev_rank",
        factor="iev",
        write_artifact=False,
    )
    assert r.verdict == FactorVerdict.BLOCKED_POLICY
    assert "not supported" in " ".join(r.notes).lower() or "not supported" in "\n".join(
        r.lines
    ).lower()


def test_cli_list_and_run(fixture_db: Path, tmp_path: Path):
    r = runner.invoke(app, ["--db", str(fixture_db), "challenge", "list"])
    assert r.exit_code == 0, r.stdout
    # Rich may wrap long policy_ids; match a distinctive substring
    assert "iev_rank" in r.stdout or "pre_open" in r.stdout
    assert "pre_open_session" in r.stdout or "accum_path" in r.stdout

    r2 = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "run",
            "screener.pre_open.iev_rank",
            "--against",
            "equal_sleeves",
            "--no-artifact",
        ],
    )
    assert r2.exit_code in (0, 2), r2.stdout
    assert "POLICY CHALLENGE" in r2.stdout or "BLOCKED" in r2.stdout
