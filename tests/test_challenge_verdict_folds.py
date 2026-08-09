"""Symmetric directional verdicts (VERDICT_SEMANTICS.symmetric_directional.v1)."""

from __future__ import annotations

from ml_saham.challenge.artifacts import VERDICT_SEMANTICS_CONTRACT_ID
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


def test_single_fold_positive_edge_is_inconclusive_not_win():
    """Thin calendar + positive edge must not be promotion WIN."""
    status, mean_b, mean_a, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.02, 0.08)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.INCONCLUSIVE
    assert mean_b == 0.02 and mean_a == 0.08
    joined = " ".join(notes).lower()
    assert "insufficient case to replace production" in joined
    assert "win" in joined


def test_single_fold_negative_edge_is_inconclusive_not_lose():
    """Thin calendar + negative edge is not a statistical LOSE."""
    status, mean_b, mean_a, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.08, 0.01)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.INCONCLUSIVE
    assert mean_b == 0.08 and mean_a == 0.01
    joined = " ".join(notes).lower()
    assert "insufficient case to replace production" in joined
    assert "lose" in joined
    assert "not a statistical lose" in joined


def test_two_folds_agreeing_can_win():
    status, _, _, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.02, 0.08), _fold(0.01, 0.05)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.WIN
    assert not any("insufficient case" in n.lower() for n in notes)


def test_two_folds_agreeing_can_lose():
    status, _, _, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.08, 0.01), _fold(0.06, 0.02)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.LOSE
    assert not any("insufficient case" in n.lower() for n in notes)


def test_two_folds_positive_disagree_inconclusive():
    # mean edge exists but only 1/2 folds favor challenger → agree 50% < 2/3
    status, _, _, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.0, 0.10), _fold(0.05, 0.0)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.INCONCLUSIVE
    assert any("fold agree" in n.lower() for n in notes)
    assert any("win" in n.lower() for n in notes)


def test_two_folds_negative_disagree_inconclusive():
    # mean baseline edge but only 1/2 folds favor baseline → lose_agree 50% < 2/3
    status, _, _, notes = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.10, 0.0), _fold(0.0, 0.05)],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.INCONCLUSIVE
    assert any("fold agree" in n.lower() for n in notes)
    assert any("lose" in n.lower() for n in notes)


def test_symmetric_positive_negative_single_fold_mutation():
    """Same single-fold magnitude: +edge and -edge both INCONCLUSIVE."""
    pos = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.0, 0.05)],
        baseline_id="production",
        against_id="x",
    )
    neg = _verdict(
        ACCUM_PATH_V1,
        [_fold(0.05, 0.0)],
        baseline_id="production",
        against_id="x",
    )
    assert pos[0] == ChallengeStatus.INCONCLUSIVE
    assert neg[0] == ChallengeStatus.INCONCLUSIVE
    assert "insufficient case to replace production" in " ".join(pos[3]).lower()
    assert "insufficient case to replace production" in " ".join(neg[3]).lower()


def test_min_folds_for_verdict_override_allows_single_fold_both_directions():
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
        min_folds_for_verdict=1,  # explicit single-fold directional verdicts
    )
    win_st, _, _, _ = _verdict(
        proto,
        [_fold(0.0, 0.05)],
        baseline_id="production",
        against_id="x",
    )
    lose_st, _, _, _ = _verdict(
        proto,
        [_fold(0.05, 0.0)],
        baseline_id="production",
        against_id="x",
    )
    assert win_st == ChallengeStatus.WIN
    assert lose_st == ChallengeStatus.LOSE


def test_product_protocols_use_symmetric_verdict_contract():
    assert ACCUM_PATH_V1.min_folds_for_verdict >= 2
    assert ACCUM_PATH_V1.verdict_semantics_contract_id == VERDICT_SEMANTICS_CONTRACT_ID
