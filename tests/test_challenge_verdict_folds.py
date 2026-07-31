"""WIN requires multi-fold evidence; single-fold edge is provisional only."""

from __future__ import annotations

from ml_saham.challenge.protocols import ACCUM_PATH_V1
from ml_saham.challenge.runner import _verdict
from ml_saham.challenge.types import ChallengeStatus, Protocol


def _fold(ic_b: float, ic_a: float, *, tail_b: float = 0.0, tail_a: float = 0.0) -> dict:
    return {
        "ic_baseline": ic_b,
        "ic_against": ic_a,
        "tail_baseline": tail_b,
        "tail_against": tail_a,
    }


def test_single_fold_edge_is_inconclusive_not_win():
    """Live accum often has 1 OOS fold after embargo — must not be promotion WIN."""
    status, mean_b, mean_a, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.02, 0.08)],  # clear edge, agree=100%
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.INCONCLUSIVE
    assert mean_b == 0.02 and mean_a == 0.08
    joined = " ".join(notes).lower()
    assert "provisional" in joined or "only 1" in joined
    assert "win" in joined  # explains need ≥2 for WIN


def test_two_folds_agreeing_can_win():
    status, _, _, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.02, 0.08), _fold(0.01, 0.05)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.WIN
    assert not any("provisional" in n.lower() for n in notes)


def test_two_folds_disagree_inconclusive():
    # mean edge exists but only 1/2 folds win → agree 50% < 2/3
    status, _, _, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.0, 0.10), _fold(0.05, 0.0)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.INCONCLUSIVE
    assert any("fold agree" in n.lower() for n in notes)


def test_single_fold_clear_lose_still_lose():
    """LOSE remains honest on one fold — do not promote challenger."""
    status, _, _, _ = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.08, 0.01)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.LOSE


def test_min_folds_for_win_override():
    proto = Protocol(
        protocol_id="t",
        primary_horizon=10,
        horizons_report=(10,),
        min_n_total=10,
        min_n_test=5,
        n_folds=3,
        embargo_sessions=1,
        win_margin=0.01,
        min_fold_agree=1.0,
        min_folds_for_win=1,  # explicit single-fold WIN allowed
    )
    status, _, _, _ = _verdict(
        proto,
        [_fold(0.0, 0.05)],
        baseline_id="production",
        against_id="x",
    )
    assert status == ChallengeStatus.WIN
