"""ML-OOS-01: session-native purged fold geometry and invariants."""

from __future__ import annotations

from datetime import date, timedelta

from ml_saham.challenge.metrics import fold_geometry_ok, time_purged_folds
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.protocols import ACCUM_PATH_V1, PRE_OPEN_SESSION_V1
from ml_saham.challenge.types import Protocol


def _row(d: str, ticker: str = "BBCA", *, excess: float = 0.01) -> PanelRow:
    return PanelRow(
        ticker=ticker,
        date=d,
        components={"a": 1.0},
        excess={10: excess, 3: excess, 20: excess, 0: excess},
    )


def _dates(n: int, *, start: date = date(2024, 1, 2)) -> list[str]:
    """n weekday-ish ISO dates (simple +1 day steps; uniqueness only matters)."""
    out: list[str] = []
    cur = start
    while len(out) < n:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _panel_from_sessions(
    sessions: list[str],
    *,
    rows_per_session: int = 5,
    tickers: list[str] | None = None,
) -> list[PanelRow]:
    tickers = tickers or [f"T{i:02d}" for i in range(rows_per_session)]
    rows: list[PanelRow] = []
    for d in sessions:
        for t in tickers[:rows_per_session]:
            rows.append(_row(d, t))
    return rows


def test_one_session_many_rows_yields_no_folds():
    """100 rows from one session must not invent a 70/30 row split."""
    rows = [_row("2026-07-01", f"T{i:03d}") for i in range(100)]
    assert len(rows) >= ACCUM_PATH_V1.min_n_total
    folds = time_purged_folds(rows, ACCUM_PATH_V1)
    assert folds == []


def test_three_sessions_under_accum_embargo_yield_no_folds():
    """90 rows / 3 dates cannot realize embargo=20 or n_folds=3."""
    sessions = ["2026-07-01", "2026-07-02", "2026-07-03"]
    rows = _panel_from_sessions(sessions, rows_per_session=30)
    assert len(rows) == 90
    folds = time_purged_folds(rows, ACCUM_PATH_V1)
    assert folds == []
    # Even with relaxed min_n, geometry must fail closed on thin calendar.
    soft = Protocol(
        protocol_id="soft",
        primary_horizon=10,
        horizons_report=(10,),
        min_n_total=10,
        min_n_test=5,
        n_folds=3,
        embargo_sessions=20,
        win_margin=0.01,
        min_fold_agree=2 / 3,
    )
    assert time_purged_folds(rows, soft) == []


def test_sufficient_sessions_form_folds_with_full_embargo_and_invariants():
    """Long enough unique session calendar produces valid purged folds."""
    # Need: chunk * (n_folds+1) roughly; embargo 20; min train rows 15; min_n_test 20.
    # Use 100 unique sessions × 5 tickers = 500 rows.
    sessions = _dates(100)
    rows = _panel_from_sessions(sessions, rows_per_session=5)
    folds = time_purged_folds(rows, ACCUM_PATH_V1)
    assert folds, "expected at least one session-native fold"
    for fold in folds:
        ok, reason = fold_geometry_ok(rows, fold, ACCUM_PATH_V1)
        assert ok, reason
        assert fold.n_train_sessions >= 1
        assert fold.n_test_sessions >= 1
        assert fold.embargo_sessions_actual >= ACCUM_PATH_V1.embargo_sessions
        assert fold.embargo_sessions_actual == ACCUM_PATH_V1.embargo_sessions
        train_dates = {rows[i].date for i in fold.train_idx}
        test_dates = {rows[i].date for i in fold.test_idx}
        assert not (train_dates & test_dates)
        assert max(train_dates) < min(test_dates)
        assert max(train_dates) == fold.train_date_max
        assert min(test_dates) == fold.test_date_min


def test_no_row_based_split_when_dates_equal_n_folds():
    """Exactly n_folds unique dates is still insufficient (need n_folds+1 blocks)."""
    sessions = _dates(ACCUM_PATH_V1.n_folds)  # 3
    rows = _panel_from_sessions(sessions, rows_per_session=40)
    assert time_purged_folds(rows, ACCUM_PATH_V1) == []


def test_interior_missing_sessions_order_still_respected():
    """Gaps in calendar dates: embargo counts unique present sessions only."""
    # 60 present sessions with holes in calendar space.
    base = _dates(60, start=date(2023, 1, 2))
    # Drop some interior ISO days already not included (weekdays only) — drop every 3rd session.
    sessions = [d for i, d in enumerate(base) if i % 3 != 1]
    assert len(sessions) >= 40
    rows = _panel_from_sessions(sessions, rows_per_session=8)
    proto = Protocol(
        protocol_id="t",
        primary_horizon=10,
        horizons_report=(10,),
        min_n_total=80,
        min_n_test=20,
        n_folds=2,
        embargo_sessions=5,
        win_margin=0.01,
        min_fold_agree=0.5,
        min_folds_for_win=1,
    )
    folds = time_purged_folds(rows, proto)
    assert folds
    for fold in folds:
        ok, reason = fold_geometry_ok(rows, fold, proto)
        assert ok, reason
        assert fold.embargo_sessions_actual >= 5


def test_uneven_ticker_coverage_across_sessions():
    """Sessions with 1 ticker vs many still form folds if min_n_test met on test block."""
    sessions = _dates(80)
    rows: list[PanelRow] = []
    for i, d in enumerate(sessions):
        n_tick = 2 if i < 40 else 10
        for t in range(n_tick):
            rows.append(_row(d, f"T{t:02d}"))
    proto = Protocol(
        protocol_id="uneven",
        primary_horizon=10,
        horizons_report=(10,),
        min_n_total=80,
        min_n_test=15,
        n_folds=2,
        embargo_sessions=5,
        win_margin=0.01,
        min_fold_agree=0.5,
        min_folds_for_win=1,
    )
    folds = time_purged_folds(rows, proto)
    assert folds
    for fold in folds:
        ok, reason = fold_geometry_ok(rows, fold, proto)
        assert ok, reason


def test_pre_open_protocol_embargo_one_session():
    sessions = _dates(40)
    rows = _panel_from_sessions(sessions, rows_per_session=5)
    folds = time_purged_folds(rows, PRE_OPEN_SESSION_V1)
    # May or may not form folds depending on min_n_test; if any, embargo actual >= 1.
    for fold in folds:
        ok, reason = fold_geometry_ok(rows, fold, PRE_OPEN_SESSION_V1)
        assert ok, reason
        assert fold.embargo_sessions_actual >= PRE_OPEN_SESSION_V1.embargo_sessions


def test_fold_geometry_ok_rejects_overlap():
    sessions = _dates(30)
    rows = _panel_from_sessions(sessions, rows_per_session=3)
    from ml_saham.challenge.metrics import Fold

    # Deliberately overlapping train/test on same indices.
    bad = Fold(
        train_idx=[0, 1, 2],
        test_idx=[0, 1, 2],
        n_train_sessions=1,
        n_test_sessions=1,
        embargo_sessions_actual=20,
        train_date_max=rows[0].date,
        test_date_min=rows[0].date,
        test_date_max=rows[0].date,
    )
    ok, reason = fold_geometry_ok(rows, bad, ACCUM_PATH_V1)
    assert not ok
    assert "overlap" in reason or "precede" in reason
