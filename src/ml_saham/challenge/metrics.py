"""Challenge metrics and session-native time folds.

ML-OOS-01: fold geometry is exclusively unique ordered sessions (dates present
on the panel). Row-based 70/30 fallback is removed. When session-native folds
cannot be constructed under the protocol's embargo and min-N thresholds, return
no folds so callers can emit BLOCKED_DATA.

Historical note: challenge artifacts produced under the former row-index
fallback may embed train/test session overlap or zero realized embargo. Treat
those as historical; this module does not rewrite protocol IDs
(``accum_path_v1`` thresholds unchanged — correctness fix, not methodology).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.types import Protocol
from ml_saham.eval.metrics import rank_ic


@dataclass
class Fold:
    """One purged expanding train / contiguous test fold.

    Indices refer to positions in the original ``rows`` sequence (not sorted
    order). Session counts are unique dates in each split.
    """

    train_idx: list[int]
    test_idx: list[int]
    n_train_sessions: int = 0
    n_test_sessions: int = 0
    # Unique panel sessions strictly after last train and before first test.
    embargo_sessions_actual: int = 0
    train_date_max: str | None = None
    test_date_min: str | None = None
    test_date_max: str | None = None


def _unique_ordered_sessions(rows: Sequence[PanelRow], order: list[int]) -> list[str]:
    """Unique dates in chronological order as they appear on the panel."""
    seen: set[str] = set()
    sessions: list[str] = []
    for i in order:
        d = rows[i].date
        if d not in seen:
            seen.add(d)
            sessions.append(d)
    return sessions


def _indices_for_sessions(
    rows: Sequence[PanelRow],
    order: list[int],
    session_set: set[str],
) -> list[int]:
    return [i for i in order if rows[i].date in session_set]


def _embargo_gap_sessions(
    sessions: Sequence[str],
    *,
    train_end_i: int,
    test_start_i: int,
) -> int:
    """Count unique sessions strictly between train_end_i and test_start_i."""
    if test_start_i <= train_end_i:
        return -1
    return test_start_i - train_end_i - 1


def fold_geometry_ok(
    rows: Sequence[PanelRow],
    fold: Fold,
    protocol: Protocol,
) -> tuple[bool, str]:
    """Prove session-ordering invariants for one fold. Fail closed on any breach."""
    if not fold.train_idx or not fold.test_idx:
        return False, "empty train or test indices"

    train_dates = {rows[i].date for i in fold.train_idx}
    test_dates = {rows[i].date for i in fold.test_idx}
    if not train_dates or not test_dates:
        return False, "empty train or test sessions"

    overlap = train_dates & test_dates
    if overlap:
        sample = sorted(overlap)[:3]
        return False, f"train/test session overlap: {sample}"

    train_max = max(train_dates)
    test_min = min(test_dates)
    test_max = max(test_dates)
    if train_max >= test_min:
        return False, f"train_date_max {train_max} does not precede test_date_min {test_min}"

    # Embargo: unique sessions strictly between last train and first test.
    all_sessions = sorted({rows[i].date for i in (*fold.train_idx, *fold.test_idx)})
    # Prefer global panel order if available via fold metadata path:
    # recompute from all row dates for a complete gap.
    panel_sessions = sorted({r.date for r in rows})
    try:
        train_end_i = panel_sessions.index(train_max)
        test_start_i = panel_sessions.index(test_min)
    except ValueError:
        return False, "fold sessions missing from panel calendar"
    gap = _embargo_gap_sessions(
        panel_sessions, train_end_i=train_end_i, test_start_i=test_start_i
    )
    if gap < 0:
        return False, "cannot prove session ordering between train and test"
    if gap < protocol.embargo_sessions:
        return (
            False,
            f"embargo gap {gap} < required {protocol.embargo_sessions}",
        )
    if fold.embargo_sessions_actual != gap:
        return (
            False,
            f"embargo_sessions_actual {fold.embargo_sessions_actual} != proven gap {gap}",
        )
    if fold.n_train_sessions != len(train_dates) or fold.n_test_sessions != len(test_dates):
        return False, "session counts disagree with index sets"
    if fold.train_date_max != train_max or fold.test_date_min != test_min:
        return False, "fold date bounds disagree with index sets"
    if fold.test_date_max != test_max:
        return False, "test_date_max disagree with index sets"
    del all_sessions  # silence unused if kept for clarity
    return True, "ok"


def _build_fold(
    rows: Sequence[PanelRow],
    order: list[int],
    sessions: Sequence[str],
    *,
    train_session_end_i: int,
    test_start_i: int,
    test_end_i: int,
    protocol: Protocol,
    min_train_rows: int,
) -> Fold | None:
    """Build one fold from session index bounds; None if geometry or min-N fails."""
    if train_session_end_i < 0:
        return None
    if test_start_i <= train_session_end_i:
        return None
    if test_start_i >= len(sessions) or test_end_i > len(sessions) or test_start_i >= test_end_i:
        return None

    gap = _embargo_gap_sessions(
        sessions, train_end_i=train_session_end_i, test_start_i=test_start_i
    )
    if gap < protocol.embargo_sessions:
        return None

    train_sessions = set(sessions[: train_session_end_i + 1])
    test_sessions = set(sessions[test_start_i:test_end_i])
    if train_sessions & test_sessions:
        return None

    train_idx = _indices_for_sessions(rows, order, train_sessions)
    test_idx = _indices_for_sessions(rows, order, test_sessions)
    n_train_sess = len(train_sessions)
    n_test_sess = len(test_sessions)
    # Structural geometry minima only (not policy-grade sample floors).
    min_train_sess = int(protocol.geometry_min_train_sessions)
    min_test_sess = int(protocol.geometry_min_test_sessions)
    if n_train_sess < min_train_sess or n_test_sess < min_test_sess:
        return None
    if len(test_idx) < protocol.min_n_test or len(train_idx) < min_train_rows:
        return None

    train_max = sessions[train_session_end_i]
    test_min = sessions[test_start_i]
    test_max = sessions[test_end_i - 1]
    if train_max >= test_min:
        return None

    fold = Fold(
        train_idx=train_idx,
        test_idx=test_idx,
        n_train_sessions=n_train_sess,
        n_test_sessions=n_test_sess,
        embargo_sessions_actual=gap,
        train_date_max=train_max,
        test_date_min=test_min,
        test_date_max=test_max,
    )
    ok, _reason = fold_geometry_ok(rows, fold, protocol)
    if not ok:
        return None
    return fold


def time_purged_folds(rows: Sequence[PanelRow], protocol: Protocol) -> list[Fold]:
    """Build purged expanding folds on unique ordered sessions only.

    - Boundaries and embargo are session counts (unique panel dates), never row
      indices.
    - No row-based 70/30 fallback: return ``[]`` when geometry cannot satisfy
      ``embargo_sessions``, ``n_folds`` chunking, and min train/test N.
    - Each returned fold has proven: no session overlap, all train dates
      precede all test dates, and embargo gap ≥ ``protocol.embargo_sessions``.
    - Structural geometry minima ``geometry_min_*_sessions`` (not policy-grade
      sample floors) come from fold-geometry simulation.
    """
    if len(rows) < protocol.min_n_total:
        return []

    order = sorted(range(len(rows)), key=lambda i: (rows[i].date, rows[i].ticker))
    sessions = _unique_ordered_sessions(rows, order)
    n_sess = len(sessions)

    # Need at least one train chunk before the first test chunk, plus n_folds
    # test segments, under a full embargo budget.
    # Fail closed on thin calendars (e.g. 1–3 sessions cannot form folds under
    # accum_path_v1 embargo=20 / n_folds=3).
    if n_sess < protocol.n_folds + 1:
        return []

    folds: list[Fold] = []
    # Divide unique sessions into n_folds+1 contiguous blocks; block 0 is the
    # initial train reservoir; later blocks are successive test windows.
    chunk = max(1, n_sess // (protocol.n_folds + 1))
    min_train_rows = int(getattr(protocol, "min_train_rows", 15) or 15)

    for f in range(protocol.n_folds):
        test_start_i = chunk * (f + 1)
        test_end_i = chunk * (f + 2) if f < protocol.n_folds - 1 else n_sess
        if test_start_i >= n_sess:
            break
        # Full embargo required: last train session index must leave ≥ embargo
        # unique sessions before test_start.
        train_end_i = test_start_i - protocol.embargo_sessions - 1
        if train_end_i < 0:
            continue
        fold = _build_fold(
            rows,
            order,
            sessions,
            train_session_end_i=train_end_i,
            test_start_i=test_start_i,
            test_end_i=test_end_i,
            protocol=protocol,
            min_train_rows=min_train_rows,
        )
        if fold is not None:
            folds.append(fold)
    return folds


def ic_safe(scores: Sequence[float], returns: Sequence[float]) -> float | None:
    """Rank IC or None if undefined (constant scores, empty, non-finite).

    Every score/return pair must be finite. A non-finite or non-numeric value
    invalidates the metric instead of silently shrinking the denominator.
    Callers that intentionally study a finite subset must filter explicitly,
    report both denominators, and re-apply their minimum-N rule before calling
    this function.
    """
    if len(scores) < 2 or len(scores) != len(returns):
        return None
    s: list[float] = []
    r: list[float] = []
    for a, b in zip(scores, returns, strict=True):
        try:
            fa = float(a)
            fb = float(b)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(fa) or not math.isfinite(fb):
            return None
        s.append(fa)
        r.append(fb)
    try:
        if max(s) - min(s) < 1e-12:
            return None
        if max(r) - min(r) < 1e-12:
            return None
        v = float(rank_ic(s, r))
        if not math.isfinite(v):
            return None
        return v
    except (ArithmeticError, TypeError, ValueError):
        return None


def bottom_decile_mean(scores: Sequence[float], returns: Sequence[float]) -> float | None:
    if len(scores) < 10:
        return None
    pairs = sorted(zip(scores, returns, strict=True), key=lambda x: x[0])
    k = max(1, len(pairs) // 10)
    return float(sum(r for _, r in pairs[:k]) / k)
