"""Fold-geometry simulation for ML-OOS-02 session floors.

Pure session-index simulation of the same chunking / embargo rules as
``time_purged_folds``, without panel rows or free-parameter thresholds.

Session floors are **derived** from existing protocol knobs
(``n_folds``, ``embargo_sessions``, ``min_folds_for_win``) by inspecting the
first calendar that yields enough folds under that geometry. No statistical
minima (IC power, daily IC, etc.) are invented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SimulatedFold:
    """One fold's session geometry (indices into a virtual calendar)."""

    fold_index: int
    train_session_end_i: int
    test_start_i: int
    test_end_i: int
    n_train_sessions: int
    n_test_sessions: int
    embargo_sessions_actual: int


@dataclass(frozen=True)
class GeometrySweepPoint:
    n_sessions: int
    n_folds_formed: int
    folds: tuple[SimulatedFold, ...]
    min_train_sessions: int | None
    min_test_sessions: int | None
    max_train_sessions: int | None
    max_test_sessions: int | None


@dataclass(frozen=True)
class GeometryMinimaRecommendation:
    """Structural geometry minima only — not policy-grade ML sample sizes.

    Values are the thinnest train/test unique-session blocks the splitter can
    emit on the first calendar that forms ≥1 fold. They prevent impossible
    geometry; they do **not** certify statistical power, dependence control,
    regime coverage, or policy-grade promote eligibility (ML-OOS-02 incomplete).
    """

    geometry_min_train_sessions: int
    geometry_min_test_sessions: int
    first_n_sessions_one_fold: int | None
    first_n_sessions_min_folds_for_win: int | None
    min_folds_for_win: int
    # Multi-fold readiness mins (informational only).
    multi_fold_min_train_sessions: int | None
    multi_fold_min_test_sessions: int | None
    embargo_sessions: int
    n_folds: int
    rationale: str


# Backward-compatible alias (name was too strong for authority).
SessionFloorRecommendation = GeometryMinimaRecommendation


def simulate_session_folds(
    n_sessions: int,
    *,
    n_folds: int,
    embargo_sessions: int,
) -> list[SimulatedFold]:
    """Mirror ``time_purged_folds`` session bounds (row floors ignored)."""
    if n_sessions < n_folds + 1:
        return []
    if n_sessions < 1 or n_folds < 1 or embargo_sessions < 0:
        return []

    chunk = max(1, n_sessions // (n_folds + 1))
    folds: list[SimulatedFold] = []
    for f in range(n_folds):
        test_start_i = chunk * (f + 1)
        test_end_i = chunk * (f + 2) if f < n_folds - 1 else n_sessions
        if test_start_i >= n_sessions or test_start_i >= test_end_i:
            break
        train_end_i = test_start_i - embargo_sessions - 1
        if train_end_i < 0:
            continue
        gap = test_start_i - train_end_i - 1
        if gap < embargo_sessions:
            continue
        n_train = train_end_i + 1
        n_test = test_end_i - test_start_i
        if n_train < 1 or n_test < 1:
            continue
        folds.append(
            SimulatedFold(
                fold_index=f,
                train_session_end_i=train_end_i,
                test_start_i=test_start_i,
                test_end_i=test_end_i,
                n_train_sessions=n_train,
                n_test_sessions=n_test,
                embargo_sessions_actual=gap,
            )
        )
    return folds


def sweep_session_geometry(
    *,
    n_folds: int,
    embargo_sessions: int,
    session_counts: Sequence[int],
) -> list[GeometrySweepPoint]:
    """Sweep calendars and summarize formed-fold session counts."""
    out: list[GeometrySweepPoint] = []
    for n in session_counts:
        folds = simulate_session_folds(
            int(n), n_folds=n_folds, embargo_sessions=embargo_sessions
        )
        trains = [f.n_train_sessions for f in folds]
        tests = [f.n_test_sessions for f in folds]
        out.append(
            GeometrySweepPoint(
                n_sessions=int(n),
                n_folds_formed=len(folds),
                folds=tuple(folds),
                min_train_sessions=min(trains) if trains else None,
                min_test_sessions=min(tests) if tests else None,
                max_train_sessions=max(trains) if trains else None,
                max_test_sessions=max(tests) if tests else None,
            )
        )
    return out


def recommend_geometry_minima(
    *,
    n_folds: int,
    embargo_sessions: int,
    min_folds_for_win: int,
    max_sessions: int = 400,
) -> GeometryMinimaRecommendation:
    """Derive structural geometry minima from protocol knobs only.

    Procedure:
    1. Sweep unique-session calendars 1..max_sessions under the live chunking
       and full-embargo rules.
    2. **Geometry minima** come from the smallest calendar that forms **≥ 1**
       fold. Take min train and min test session counts among folds there.
    3. **Informational multi-fold readiness** uses the first calendar that
       forms ≥ ``min_folds_for_win`` folds — reported, not policy-grade floors.

    These minima are not statistical sample-size requirements. Policy-grade
    session floors require a separate confirmation contract (ML-OOS-02 open).
    """
    win_bar = max(1, int(min_folds_for_win))
    points = sweep_session_geometry(
        n_folds=n_folds,
        embargo_sessions=embargo_sessions,
        session_counts=range(1, max_sessions + 1),
    )
    first_one = next((p for p in points if p.n_folds_formed >= 1), None)
    first_win = next((p for p in points if p.n_folds_formed >= win_bar), None)

    if first_one is None or first_one.min_train_sessions is None:
        rationale = (
            f"no calendar ≤ {max_sessions} sessions formed any fold "
            f"(n_folds={n_folds}, embargo={embargo_sessions}); "
            "using identity geometry minima train=1, test=1"
        )
        return GeometryMinimaRecommendation(
            geometry_min_train_sessions=1,
            geometry_min_test_sessions=1,
            first_n_sessions_one_fold=None,
            first_n_sessions_min_folds_for_win=None,
            min_folds_for_win=win_bar,
            multi_fold_min_train_sessions=None,
            multi_fold_min_test_sessions=None,
            embargo_sessions=embargo_sessions,
            n_folds=n_folds,
            rationale=rationale,
        )

    min_train = max(1, int(first_one.min_train_sessions))
    min_test = max(1, int(first_one.min_test_sessions or 1))
    multi_tr = (
        int(first_win.min_train_sessions)
        if first_win is not None and first_win.min_train_sessions is not None
        else None
    )
    multi_te = (
        int(first_win.min_test_sessions)
        if first_win is not None and first_win.min_test_sessions is not None
        else None
    )

    rationale = (
        f"structural geometry minima from first 1-fold calendar "
        f"(n_sessions={first_one.n_sessions}, n_folds={n_folds}, "
        f"embargo={embargo_sessions}): "
        f"geometry_min_train_sessions={min_train}, "
        f"geometry_min_test_sessions={min_test}; "
        f"multi-fold readiness (≥{win_bar} folds) first at "
        f"n_sessions={first_win.n_sessions if first_win else None} "
        f"(min_train={multi_tr}, min_test={multi_te}) — informational only; "
        "not policy-grade sample floors"
    )
    return GeometryMinimaRecommendation(
        geometry_min_train_sessions=min_train,
        geometry_min_test_sessions=min_test,
        first_n_sessions_one_fold=first_one.n_sessions,
        first_n_sessions_min_folds_for_win=(
            first_win.n_sessions if first_win is not None else None
        ),
        min_folds_for_win=win_bar,
        multi_fold_min_train_sessions=multi_tr,
        multi_fold_min_test_sessions=multi_te,
        embargo_sessions=embargo_sessions,
        n_folds=n_folds,
        rationale=rationale,
    )


# Backward-compatible name.
recommend_session_floors = recommend_geometry_minima


def format_sweep_table(points: Sequence[GeometrySweepPoint], *, limit: int = 30) -> str:
    """Human-readable sweep excerpt for decision docs / CLI."""
    lines = [
        f"{'n_sess':>7}  {'folds':>5}  {'min_tr':>6}  {'min_te':>6}  "
        f"{'max_tr':>6}  {'max_te':>6}",
        "-" * 48,
    ]
    interesting = [
        p
        for p in points
        if p.n_folds_formed > 0
        or p.n_sessions in {1, 3, 10, 20, 40, 80, 84, 100, 120, 200}
    ]
    for p in interesting[:limit]:
        lines.append(
            f"{p.n_sessions:7d}  {p.n_folds_formed:5d}  "
            f"{p.min_train_sessions or 0:6d}  {p.min_test_sessions or 0:6d}  "
            f"{p.max_train_sessions or 0:6d}  {p.max_test_sessions or 0:6d}"
        )
    return "\n".join(lines)
