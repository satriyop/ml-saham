"""C2 hard-filter preregistration: locked discovery, blocked engine."""

from __future__ import annotations

from dataclasses import fields, replace

import pytest

from ml_saham.challenge.engines import ENGINE_POLICIES
from ml_saham.challenge.protocols import ACCUM_PATH_V1, PROTOCOLS
from ml_saham.challenge.screen_filter_preregistration import (
    SCREEN_FILTER_PREREGISTRATION_CONTRACT_ID,
    build_screen_filter_preregistration,
    validate_screen_filter_preregistration,
)


def test_preregistration_locks_discovery_without_authorizing_tournament():
    contract = build_screen_filter_preregistration()

    assert contract.contract_id == SCREEN_FILTER_PREREGISTRATION_CONTRACT_ID
    assert (
        contract.discovery_quantile_population
        == "finite_numeric_train_values_per_gate"
    )
    assert contract.discovery_quantile_grid == (0.25, 0.50, 0.75)
    assert contract.discovery_outcome == "proposal_only_no_win_lose"
    assert contract.confirmation_candidate_limit == 1
    assert contract.confirmation_data_rule == "future_sessions_unseen_by_discovery"
    assert contract.open_decisions == (
        "material_improvement_rule",
        "tail_risk_rule",
        "turnover_rule",
    )
    assert contract.engine_registration_authorized is False

    assert contract.min_valid_oos_folds == ACCUM_PATH_V1.min_folds_for_verdict
    assert contract.embargo_sessions == ACCUM_PATH_V1.embargo_sessions
    assert (
        contract.min_per_side_labeled_rows_per_fold == ACCUM_PATH_V1.min_n_test
    )
    assert contract.base_protocol_id in PROTOCOLS
    assert SCREEN_FILTER_PREREGISTRATION_CONTRACT_ID not in PROTOCOLS
    assert all(
        "screener.accum.hard_filters" not in policy_ids
        for scenarios in ENGINE_POLICIES.values()
        for policy_ids in scenarios.values()
    )


def test_preregistration_rejects_leakage_or_premature_engine_authority():
    contract = build_screen_filter_preregistration()

    mutations = (
        replace(contract, discovery_threshold_rule="full_panel_quantiles"),
        replace(contract, discovery_outcome="WIN"),
        replace(contract, confirmation_candidate_limit=2),
        replace(contract, confirmation_data_rule="reuse_discovery_oos"),
        replace(contract, min_valid_oos_folds=1),
        replace(contract, engine_registration_authorized=True),
    )
    for mutation in mutations:
        with pytest.raises(ValueError):
            validate_screen_filter_preregistration(mutation)


def test_preregistration_rejects_mutated_quantile_grid():
    contract = build_screen_filter_preregistration()
    for grid in (
        (),
        (0.25, 0.25),
        (0.0, 0.5),
        (0.75, 0.25),
        (0.2, 0.5, 0.8),
        (0.25, "bad", 0.75),
    ):
        with pytest.raises(ValueError, match="quantile_grid"):
            validate_screen_filter_preregistration(
                replace(contract, discovery_quantile_grid=grid)
            )


def test_methodology_digest_binds_every_contract_field():
    contract = build_screen_filter_preregistration()
    original = contract.methodology_digest

    for field in fields(contract):
        value = getattr(contract, field.name)
        if value is None:
            changed = "locked"
        elif isinstance(value, bool):
            changed = not value
        elif isinstance(value, int):
            changed = value + 1
        elif isinstance(value, str):
            changed = value + ".mutated"
        elif isinstance(value, tuple):
            changed = value + (("mutated" if value and isinstance(value[0], str) else 0.9),)
        else:  # pragma: no cover - closed dataclass field types above
            raise AssertionError(f"unhandled field type: {field.name}")
        assert replace(contract, **{field.name: changed}).methodology_digest != original
