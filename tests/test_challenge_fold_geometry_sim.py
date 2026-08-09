"""ML-OOS-02: fold-geometry simulation and derived session floors."""

from __future__ import annotations

from ml_saham.challenge.fold_geometry_sim import (
    recommend_geometry_minima,
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
        geometry_min_train_sessions=1,
        geometry_min_test_sessions=1,
        min_train_rows=15,
    )
    live = time_purged_folds(rows, proto)
    sim = simulate_session_folds(100, n_folds=3, embargo_sessions=20)
    assert len(live) == len(sim)
    for lf, sf in zip(live, sim, strict=True):
        assert lf.n_train_sessions == sf.n_train_sessions
        assert lf.n_test_sessions == sf.n_test_sessions
        assert lf.embargo_sessions_actual == sf.embargo_sessions_actual


def test_recommend_accum_geometry_minima_from_first_one_fold_calendar():
    rec = recommend_geometry_minima(
        n_folds=3, embargo_sessions=20, min_folds_for_win=2
    )
    assert rec.geometry_min_train_sessions == 1
    assert rec.geometry_min_test_sessions == 7
    assert rec.first_n_sessions_one_fold == 28
    assert rec.first_n_sessions_min_folds_for_win == 44
    assert rec.multi_fold_geometry_min_train_sessions == 2
    assert rec.multi_fold_geometry_min_test_sessions == 11
    assert ACCUM_PATH_V1.geometry_min_train_sessions == rec.geometry_min_train_sessions
    assert ACCUM_PATH_V1.geometry_min_test_sessions == rec.geometry_min_test_sessions
    assert ACCUM_PATH_V1.evidence_grade == "EXPLORATORY"
    assert ACCUM_PATH_V1.policy_confirmation_contract_id == ""


def test_recommend_pre_open_geometry_minima():
    rec = recommend_geometry_minima(
        n_folds=3, embargo_sessions=1, min_folds_for_win=2
    )
    assert rec.geometry_min_train_sessions == 1
    assert rec.geometry_min_test_sessions == 1
    assert PRE_OPEN_SESSION_V1.geometry_min_train_sessions == 1
    assert PRE_OPEN_SESSION_V1.geometry_min_test_sessions == 1
    assert PRE_OPEN_SESSION_V1.evidence_grade == "EXPLORATORY"


def test_geometry_minima_reject_thinner_than_first_viable():
    """Below first 1-fold geometry, no folds; at first 1-fold mins, folds ok."""
    # n=27: no fold under embargo=20 / n_folds=3
    rows_thin = _panel_from_sessions(_dates(27), rows_per_session=20)
    assert time_purged_folds(rows_thin, ACCUM_PATH_V1) == []

    # n=28: first 1-fold calendar → train=1, test=7 meets geometry minima 1/7
    rows_ok = _panel_from_sessions(_dates(28), rows_per_session=20)
    folds = time_purged_folds(rows_ok, ACCUM_PATH_V1)
    assert folds
    assert all(
        f.n_test_sessions >= ACCUM_PATH_V1.geometry_min_test_sessions for f in folds
    )
    assert all(
        f.n_train_sessions >= ACCUM_PATH_V1.geometry_min_train_sessions for f in folds
    )


def test_sweep_includes_pathological_zeros():
    pts = sweep_session_geometry(
        n_folds=3, embargo_sessions=20, session_counts=[1, 3, 10, 20]
    )
    assert all(p.n_folds_formed == 0 for p in pts)


def test_obsolete_session_floor_names_are_absent():
    """Clean break: no statistical-sounding aliases or Protocol fields."""
    import ml_saham.challenge.fold_geometry_sim as sim
    import ml_saham.challenge.metrics as metrics_mod
    import ml_saham.challenge.promote as promote_mod
    import ml_saham.challenge.types as types_mod

    # Module-level aliases removed.
    assert not hasattr(sim, "SessionFloorRecommendation")
    assert not hasattr(sim, "recommend_session_floors")

    # Protocol has geometry_* only for session minima.
    assert hasattr(types_mod.Protocol, "__dataclass_fields__")
    fields = types_mod.Protocol.__dataclass_fields__
    assert "geometry_min_train_sessions" in fields
    assert "geometry_min_test_sessions" in fields
    assert "min_train_sessions" not in fields
    assert "min_test_sessions" not in fields

    # No fallback readers of obsolete field names in product code.
    for mod in (metrics_mod, promote_mod, sim):
        src = open(mod.__file__, encoding="utf-8").read()
        assert 'getattr(protocol, "min_train_sessions"' not in src
        assert 'getattr(protocol, "min_test_sessions"' not in src
        assert "recommend_session_floors" not in src or mod is not sim
        assert "SessionFloorRecommendation" not in src

    # GeometrySweepPoint uses geometry_* names only.
    sweep_fields = sim.GeometrySweepPoint.__dataclass_fields__
    assert "geometry_min_train_sessions" in sweep_fields
    assert "min_train_sessions" not in sweep_fields
    assert "min_test_sessions" not in sweep_fields
