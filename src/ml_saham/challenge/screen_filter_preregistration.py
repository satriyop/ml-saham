"""C2 hard-filter discovery/confirmation preregistration.

This contract freezes the parts of the methodology that can be selected
without inspecting OOS outcomes.  It deliberately does not register a
Protocol, challenger, engine row, or verdict law while materiality, tail-risk,
and turnover decisions remain open.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

from ml_saham.challenge.panel_screen_filters import (
    GATE_ORDER,
    SCREEN_FILTER_CONFORMANCE_CONTRACT_ID,
)
from ml_saham.challenge.protocols import ACCUM_PATH_V1
from ml_saham.challenge.scorers import GATE_DECISION_QUALITY_CONTRACT_ID

SCREEN_FILTER_PREREGISTRATION_CONTRACT_ID = (
    "screen_accum_hard_filters.preregistration.v1"
)
SCREEN_FILTER_PREREGISTRATION_STATUS = "DISCOVERY_ONLY_ENGINE_BLOCKED"


@dataclass(frozen=True)
class ScreenFilterPreregistration:
    """Immutable C2 methodology contract; not an executable tournament."""

    contract_id: str
    status: str
    policy_id: str
    adapter_version: str
    producer_conformance_contract_id: str
    base_protocol_id: str
    sample_unit: str
    population: str
    canonical_window: int
    primary_target: str
    benchmark: str
    primary_horizon: int
    gate_order: tuple[str, ...]
    discovery_threshold_rule: str
    discovery_quantile_population: str
    discovery_quantile_grid: tuple[float, ...]
    discovery_search_shape: str
    discovery_outcome: str
    confirmation_candidate_limit: int
    confirmation_candidate_freeze: str
    confirmation_data_rule: str
    multiplicity_rule: str
    min_valid_oos_folds: int
    embargo_sessions: int
    min_per_side_labeled_rows_per_fold: int
    decision_quality_contract_id: str
    material_improvement_rule: str | None
    tail_risk_rule: str | None
    turnover_rule: str | None
    engine_registration_authorized: bool

    @property
    def open_decisions(self) -> tuple[str, ...]:
        decisions = (
            ("material_improvement_rule", self.material_improvement_rule),
            ("tail_risk_rule", self.tail_risk_rule),
            ("turnover_rule", self.turnover_rule),
        )
        return tuple(name for name, value in decisions if value is None)

    @property
    def methodology_digest(self) -> str:
        canonical = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_screen_filter_preregistration() -> ScreenFilterPreregistration:
    """Return the sealed discovery-only v1 contract."""

    contract = ScreenFilterPreregistration(
        contract_id=SCREEN_FILTER_PREREGISTRATION_CONTRACT_ID,
        status=SCREEN_FILTER_PREREGISTRATION_STATUS,
        policy_id="screener.accum.hard_filters",
        adapter_version="v2",
        producer_conformance_contract_id=SCREEN_FILTER_CONFORMANCE_CONTRACT_ID,
        base_protocol_id=ACCUM_PATH_V1.protocol_id,
        sample_unit="unique_ticker_session",
        population="explicit_accum_compatibility_cohort_capture_evaluated",
        canonical_window=7,
        primary_target="h10_excess_return",
        benchmark="ihsg_same_h10_sessions",
        primary_horizon=10,
        gate_order=GATE_ORDER,
        discovery_threshold_rule="train_fold_empirical_quantiles_only",
        discovery_quantile_population="finite_numeric_train_values_per_gate",
        discovery_quantile_grid=(0.25, 0.50, 0.75),
        discovery_search_shape="one_gate_at_a_time_no_cartesian_combinations",
        discovery_outcome="proposal_only_no_win_lose",
        confirmation_candidate_limit=1,
        confirmation_candidate_freeze="before_any_confirmation_outcome",
        confirmation_data_rule="future_sessions_unseen_by_discovery",
        multiplicity_rule=(
            "report_all_discovery_variants_no_winner_then_confirm_exactly_one"
        ),
        min_valid_oos_folds=ACCUM_PATH_V1.min_folds_for_verdict,
        embargo_sessions=ACCUM_PATH_V1.embargo_sessions,
        min_per_side_labeled_rows_per_fold=ACCUM_PATH_V1.min_n_test,
        decision_quality_contract_id=GATE_DECISION_QUALITY_CONTRACT_ID,
        material_improvement_rule=None,
        tail_risk_rule=None,
        turnover_rule=None,
        engine_registration_authorized=False,
    )
    validate_screen_filter_preregistration(contract)
    return contract


def validate_screen_filter_preregistration(
    contract: ScreenFilterPreregistration,
) -> None:
    """Fail closed if the preregistration weakens leakage or authority gates."""

    exact = {
        "contract_id": SCREEN_FILTER_PREREGISTRATION_CONTRACT_ID,
        "status": SCREEN_FILTER_PREREGISTRATION_STATUS,
        "policy_id": "screener.accum.hard_filters",
        "adapter_version": "v2",
        "producer_conformance_contract_id": SCREEN_FILTER_CONFORMANCE_CONTRACT_ID,
        "base_protocol_id": ACCUM_PATH_V1.protocol_id,
        "sample_unit": "unique_ticker_session",
        "population": "explicit_accum_compatibility_cohort_capture_evaluated",
        "canonical_window": 7,
        "primary_target": "h10_excess_return",
        "benchmark": "ihsg_same_h10_sessions",
        "primary_horizon": ACCUM_PATH_V1.primary_horizon,
        "gate_order": GATE_ORDER,
        "discovery_threshold_rule": "train_fold_empirical_quantiles_only",
        "discovery_quantile_population": "finite_numeric_train_values_per_gate",
        "discovery_search_shape": "one_gate_at_a_time_no_cartesian_combinations",
        "discovery_outcome": "proposal_only_no_win_lose",
        "confirmation_candidate_limit": 1,
        "confirmation_candidate_freeze": "before_any_confirmation_outcome",
        "confirmation_data_rule": "future_sessions_unseen_by_discovery",
        "multiplicity_rule": (
            "report_all_discovery_variants_no_winner_then_confirm_exactly_one"
        ),
        "min_valid_oos_folds": ACCUM_PATH_V1.min_folds_for_verdict,
        "embargo_sessions": ACCUM_PATH_V1.embargo_sessions,
        "min_per_side_labeled_rows_per_fold": ACCUM_PATH_V1.min_n_test,
        "decision_quality_contract_id": GATE_DECISION_QUALITY_CONTRACT_ID,
    }
    for field, expected in exact.items():
        actual = getattr(contract, field)
        if actual != expected:
            raise ValueError(
                f"screen-filter preregistration {field} mismatch: "
                f"expected={expected!r} actual={actual!r}"
            )

    grid = contract.discovery_quantile_grid
    if (
        not grid
        or any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(float(value))
            or not 0.0 < float(value) < 1.0
            for value in grid
        )
    ):
        raise ValueError(
            "screen-filter preregistration discovery_quantile_grid must be "
            "unique, increasing, and strictly inside (0, 1)"
        )
    if tuple(sorted(set(grid))) != grid:
        raise ValueError(
            "screen-filter preregistration discovery_quantile_grid must be "
            "unique, increasing, and strictly inside (0, 1)"
        )
    if grid != (0.25, 0.50, 0.75):
        raise ValueError(
            "screen-filter preregistration discovery_quantile_grid mismatch"
        )

    if contract.open_decisions != (
        "material_improvement_rule",
        "tail_risk_rule",
        "turnover_rule",
    ):
        raise ValueError(
            "screen-filter preregistration v1 must preserve all open decision gates"
        )
    if contract.engine_registration_authorized:
        raise ValueError(
            "screen-filter engine registration is forbidden while decisions are open"
        )
