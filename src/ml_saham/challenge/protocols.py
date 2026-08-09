"""Versioned evaluation protocols."""

from __future__ import annotations

from ml_saham.challenge.fold_geometry_sim import recommend_geometry_minima
from ml_saham.challenge.types import (
    EVIDENCE_GRADE_EXPLORATORY,
    Protocol,
)

# Structural geometry minima only (ML-OOS-02 incomplete for policy-grade floors).
# See docs/decisions/ml_oos_02_session_floors_2026-08-09.md.
_ACCUM_GEOM = recommend_geometry_minima(
    n_folds=3,
    embargo_sessions=20,
    min_folds_for_verdict=2,
)
_PRE_OPEN_GEOM = recommend_geometry_minima(
    n_folds=3,
    embargo_sessions=1,
    min_folds_for_verdict=2,
)

# Accum path: primary H=10 (ai-saham accum_10d); report tactical 3d + accum 20d.
# evidence_grade=EXPLORATORY: runnable challenge, not policy-grade promote.
ACCUM_PATH_V1 = Protocol(
    protocol_id="accum_path_v1",
    primary_horizon=10,
    horizons_report=(3, 10, 20),
    min_n_total=80,
    min_n_test=20,
    n_folds=3,
    embargo_sessions=20,
    win_margin=0.01,
    min_fold_agree=2 / 3,
    label="excess_vs_ihsg",
    costs="gross_banner",
    min_folds_for_verdict=2,  # WIN and LOSE both need multi-fold evidence
    geometry_min_train_sessions=_ACCUM_GEOM.geometry_min_train_sessions,
    geometry_min_test_sessions=_ACCUM_GEOM.geometry_min_test_sessions,
    min_train_rows=15,
    evidence_grade=EVIDENCE_GRADE_EXPLORATORY,
    policy_confirmation_contract_id="",  # none until ML-OOS-02 confirmation study
)

# Pre-open session: primary horizon 0 = same-session open→close (not multi-day).
PRE_OPEN_SESSION_V1 = Protocol(
    protocol_id="pre_open_session_v1",
    primary_horizon=0,
    horizons_report=(0,),
    min_n_total=80,
    min_n_test=20,
    n_folds=3,
    embargo_sessions=1,
    win_margin=0.01,
    min_fold_agree=2 / 3,
    label="open_to_close_excess_vs_ihsg",
    costs="gross_banner",
    min_folds_for_verdict=2,
    geometry_min_train_sessions=_PRE_OPEN_GEOM.geometry_min_train_sessions,
    geometry_min_test_sessions=_PRE_OPEN_GEOM.geometry_min_test_sessions,
    min_train_rows=15,
    evidence_grade=EVIDENCE_GRADE_EXPLORATORY,
    policy_confirmation_contract_id="",
)

PROTOCOLS: dict[str, Protocol] = {
    ACCUM_PATH_V1.protocol_id: ACCUM_PATH_V1,
    PRE_OPEN_SESSION_V1.protocol_id: PRE_OPEN_SESSION_V1,
}


def get_protocol(protocol_id: str) -> Protocol:
    try:
        return PROTOCOLS[protocol_id]
    except KeyError as exc:
        known = ", ".join(sorted(PROTOCOLS))
        raise KeyError(f"Unknown protocol {protocol_id!r}. Known: {known}") from exc
