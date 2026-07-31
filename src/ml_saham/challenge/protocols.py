"""Versioned evaluation protocols."""

from __future__ import annotations

from ml_saham.challenge.types import Protocol

# Accum path: primary H=10 (ai-saham accum_10d); report tactical 3d + accum 20d.
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
    min_folds_for_win=2,  # single post-embargo fold cannot be promotion WIN
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
    min_folds_for_win=2,
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
