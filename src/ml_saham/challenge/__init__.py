"""ADR-002 challenge product (policy tournaments + factor validity)."""

from ml_saham.challenge.factor_validity import list_enabled_factors, run_factor_challenge
from ml_saham.challenge.runner import list_policies, run_policy_challenge
from ml_saham.challenge.types import (
    ChallengeResult,
    ChallengeStatus,
    FactorChallengeResult,
    FactorVerdict,
)

__all__ = [
    "ChallengeResult",
    "ChallengeStatus",
    "FactorChallengeResult",
    "FactorVerdict",
    "list_enabled_factors",
    "list_policies",
    "run_factor_challenge",
    "run_policy_challenge",
]
