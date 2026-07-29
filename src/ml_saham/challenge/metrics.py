"""Challenge metrics and time folds."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.types import Protocol
from ml_saham.eval.metrics import rank_ic


@dataclass
class Fold:
    train_idx: list[int]
    test_idx: list[int]


def time_purged_folds(rows: Sequence[PanelRow], protocol: Protocol) -> list[Fold]:
    """Sort by date; split into n_folds test blocks with embargo after each train end."""
    order = sorted(range(len(rows)), key=lambda i: (rows[i].date, rows[i].ticker))
    n = len(order)
    if n < protocol.min_n_total:
        return []

    # unique dates for fold boundaries
    dates = sorted({rows[i].date for i in order})
    if len(dates) < protocol.n_folds + 1:
        # single fold: first 70% train, rest test (with embargo cut)
        cut = int(n * 0.7)
        train_idx = order[: max(cut - protocol.embargo_sessions, 1)]
        test_idx = order[cut:]
        if len(test_idx) < protocol.min_n_test or len(train_idx) < 10:
            return []
        return [Fold(train_idx=train_idx, test_idx=test_idx)]

    folds: list[Fold] = []
    # divide dates into n_folds contiguous test segments (later segments)
    chunk = max(1, len(dates) // (protocol.n_folds + 1))
    for f in range(protocol.n_folds):
        # test = later chunks
        test_start_date_i = chunk * (f + 1)
        test_end_date_i = chunk * (f + 2) if f < protocol.n_folds - 1 else len(dates)
        if test_start_date_i >= len(dates):
            break
        test_dates = set(dates[test_start_date_i:test_end_date_i])
        # train = dates strictly before test_start, minus embargo sessions by date index
        embargo_start = max(0, test_start_date_i - protocol.embargo_sessions)
        train_dates = set(dates[:embargo_start])
        train_idx = [i for i in order if rows[i].date in train_dates]
        test_idx = [i for i in order if rows[i].date in test_dates]
        if len(test_idx) < protocol.min_n_test or len(train_idx) < 15:
            continue
        folds.append(Fold(train_idx=train_idx, test_idx=test_idx))
    return folds


def ic_safe(scores: Sequence[float], returns: Sequence[float]) -> float | None:
    """Rank IC or None if undefined (constant scores, empty, non-finite)."""
    try:
        if len(scores) < 2 or len(scores) != len(returns):
            return None
        s = [float(x) for x in scores]
        r = [float(x) for x in returns]
        if max(s) - min(s) < 1e-12:
            return None
        if max(r) - min(r) < 1e-12:
            return None
        v = float(rank_ic(s, r))
        if not math.isfinite(v):
            return None
        return v
    except Exception:
        return None


def bottom_decile_mean(scores: Sequence[float], returns: Sequence[float]) -> float | None:
    if len(scores) < 10:
        return None
    pairs = sorted(zip(scores, returns, strict=True), key=lambda x: x[0])
    k = max(1, len(pairs) // 10)
    return float(sum(r for _, r in pairs[:k]) / k)
