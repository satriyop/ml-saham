"""ADR-002 challenge product (policy tournaments + factor/diagnostic validity + engines)."""

from ml_saham.challenge.champion import is_champion_against
from ml_saham.challenge.diagnostic_validity import (
    list_diagnostic_catalog,
    list_enabled_diagnostic_features,
    run_diagnostic_challenge,
    run_diagnostic_challenge_batch,
    run_diagnostic_health,
)
from ml_saham.challenge.engines import list_engines, run_engine_portfolio
from ml_saham.challenge.factor_validity import (
    list_enabled_factors,
    run_factor_challenge,
    run_factor_challenge_batch,
)
from ml_saham.challenge.runner import list_policies, run_policy_challenge
from ml_saham.challenge.types import (
    BatchDiagnosticResult,
    BatchFactorResult,
    ChallengeResult,
    ChallengeStatus,
    DiagnosticChallengeResult,
    DiagnosticVerdict,
    EnginePortfolioResult,
    FactorChallengeResult,
    FactorVerdict,
)

__all__ = [
    "BatchDiagnosticResult",
    "BatchFactorResult",
    "ChallengeResult",
    "ChallengeStatus",
    "DiagnosticChallengeResult",
    "DiagnosticVerdict",
    "EnginePortfolioResult",
    "FactorChallengeResult",
    "FactorVerdict",
    "is_champion_against",
    "list_diagnostic_catalog",
    "list_enabled_diagnostic_features",
    "list_enabled_factors",
    "list_engines",
    "list_policies",
    "run_diagnostic_challenge",
    "run_diagnostic_challenge_batch",
    "run_diagnostic_health",
    "run_engine_portfolio",
    "run_factor_challenge",
    "run_factor_challenge_batch",
    "run_policy_challenge",
]
