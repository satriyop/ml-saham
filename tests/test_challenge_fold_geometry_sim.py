"""ML-OOS-02: fold-geometry simulation and derived session floors."""

from __future__ import annotations

from ml_saham.challenge.fold_geometry_sim import (
    recommend_session_floors,
    simulate_session_folds,
    sweep_session_geometry,
)
from ml_saham.challenge.metrics import time_purged_folds
from ml_saham.challenge.protocols import ACCUM_PATH_V1, PRE_OPEN_SESSION_V1
from ml_saham.challenge.types import Protocol
from tests.test_challenge_fold_geometry import _dates, _panel_from_sessions


def test_simulate_matches_time_purged_session_counts():
    """Pure sim bounds match live time_purged_folds session counts."""
    sessions = _dates(100)
    rows = _panel_from_sessions(sessions, rows_per_session=5)
    proto = Protocol(
        protocol_id="t",
        primary_horizon=10,
        horizons_report=(10,),
        min_n_total=80,
        min_n_test=20,
        n_folds=3,
        embargo_sessions=20,
        win_margin=0.01,
        min_fold_agree=2 / 3,
        min_folds_for_win=2,
        min_train_sessions=1,
        min_test_sessions=1,
        min_train_rows=15,
    )
    live = time_purged_folds(rows, proto)
    sim = simulate_session_folds(100, n_folds=3, embargo_sessions=20)
    assert len(live) == len(sim)
    for lf, sf in zip(live, sim, strict=True):
        assert lf.n_train_sessions == sf.n_train_sessions
        assert lf.n_test_sessions == sf.n_test_sessions
        assert lf.embargo_sessions_actual == sf.embargo_sessions_actual


def test_recommend_accum_floors_from_first_one_fold_calendar():
    rec = recommend_session_floors(
        n_folds=3, embargo_sessions=20, min_folds_for_win=2
    )
    assert rec.min_train_sessions == 1
    assert rec.min_test_sessions == 7
    assert rec.first_n_sessions_one_fold == 28
    assert rec.first_n_sessions_min_folds_for_win == 44
    assert rec.multi_fold_min_train_sessions == 2
    assert rec.multi_fold_min_test_sessions == 11
    assert ACCUM_PATH_V1.min_train_sessions == rec.min_train_sessions
    assert ACCUM_PATH_V1.min_test_sessions == rec.min_test_sessions


def test_recommend_pre_open_floors():
    rec = recommend_session_floors(
        n_folds=3, embargo_sessions=1, min_folds_for_win=2
    )
    assert rec.min_train_sessions == 1
    assert rec.min_test_sessions == 1
    assert PRE_OPEN_SESSION_V1.min_train_sessions == 1
    assert PRE_OPEN_SESSION_V1.min_test_sessions == 1


def test_hard_floor_rejects_thinner_test_block_than_first_viable():
    """Below first 1-fold geometry, no folds; at first 1-fold mins, folds ok."""
    # n=27: no fold under embargo=20 / n_folds=3
    rows_thin = _panel_from_sessions(_dates(27), rows_per_session=20)
    assert time_purged_folds(rows_thin, ACCUM_PATH_V1) == []

    # n=28: first 1-fold calendar → train=1, test=7 meets floors 1/7
    # rows/session high enough for min_train_rows=15 and min_n_test=20
    rows_ok = _panel_from_sessions(_dates(28), rows_per_session=20)
    folds = time_purged_folds(rows_ok, ACCUM_PATH_V1)
    assert folds
    assert all(f.n_test_sessions >= ACCUM_PATH_V1.min_test_sessions for f in folds)
    assert all(f.n_train_sessions >= ACCUM_PATH_V1.min_train_sessions for f in folds)


def test_sweep_includes_pathological_zeros():
    pts = sweep_session_geometry(
        n_folds=3, embargo_sessions=20, session_counts=[1, 3, 10, 20]
    )
    assert all(p.n_folds_formed == 0 for p in pts)
