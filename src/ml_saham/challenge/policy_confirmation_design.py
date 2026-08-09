"""ML-OOS-02 design study machinery (measurement only).

This module supports **vetting** policy-grade confirmation design. It must not
select or write Protocol thresholds. No values here enter
``POLICY_CONFIRMATION_CONTRACTS`` or promote eligibility.

Covered study axes:

1. Structural geometry depth profiles (via fold_geometry_sim)
2. Fixed vs learned challenger sample-pressure descriptors
3. Session-aware (daily) rank-IC series + descriptive uncertainty summaries
4. Final untouched holdout placement relative to purged folds
5. Multiplicity bookkeeping for multi-challenger searches

Semantic classification: PROTOCOL_CONTRACT design research (not product law yet).
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from ml_saham.challenge.fold_geometry_sim import (
    GeometryMinimaRecommendation,
    recommend_geometry_minima,
    simulate_session_folds,
    sweep_session_geometry,
)
from ml_saham.challenge.metrics import ic_safe

# Draft identity for future confirmation contracts. NOT registered for promote.
POLICY_CONFIRMATION_CONTRACT_DRAFT_ID = "policy_confirmation.accum_oos.design.v0"

# Axes a future POLICY_GRADE contract must bind (documentation + checklist).
POLICY_CONFIRMATION_REQUIRED_AXES: tuple[str, ...] = (
    "challenger_class",  # fixed | learned
    "geometry_minima_ref",  # structural baseline (not the policy floor)
    "policy_min_train_sessions",  # TBD — study output, not guessed here
    "policy_min_test_sessions",  # TBD
    "session_ic_method",  # e.g. mean daily IC + reported dispersion
    "ic_uncertainty_method",  # TBD — bootstrap/session-block; not selected
    "final_holdout_sessions",  # TBD — untouched after last OOS fold
    "multiplicity_rule",  # TBD — search set + selection discipline
    "min_folds_for_verdict",  # already product: symmetric directional
    "verdict_semantics_contract_id",
    "fold_geometry_contract_id",
)


# ---------------------------------------------------------------------------
# 1) Geometry depth profiles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeometryDepthProfile:
    """How train/test session depths evolve with calendar length."""

    n_folds: int
    embargo_sessions: int
    min_folds_for_verdict: int
    structural_minima: GeometryMinimaRecommendation
    # Sparse points: n_sessions → (min_train, min_test, n_folds_formed)
    depth_points: tuple[tuple[int, int | None, int | None, int], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_folds": self.n_folds,
            "embargo_sessions": self.embargo_sessions,
            "min_folds_for_verdict": self.min_folds_for_verdict,
            "structural_minima": asdict(self.structural_minima),
            "depth_points": [
                {
                    "n_sessions": n,
                    "geometry_min_train_sessions": tr,
                    "geometry_min_test_sessions": te,
                    "n_folds_formed": nf,
                }
                for n, tr, te, nf in self.depth_points
            ],
        }


def build_geometry_depth_profile(
    *,
    n_folds: int,
    embargo_sessions: int,
    min_folds_for_verdict: int,
    session_grid: Sequence[int] | None = None,
) -> GeometryDepthProfile:
    grid = tuple(
        session_grid
        if session_grid is not None
        else (
            1,
            3,
            10,
            20,
            28,
            40,
            44,
            60,
            80,
            84,
            100,
            120,
            160,
            200,
            252,
            300,
        )
    )
    points = sweep_session_geometry(
        n_folds=n_folds,
        embargo_sessions=embargo_sessions,
        session_counts=grid,
    )
    minima = recommend_geometry_minima(
        n_folds=n_folds,
        embargo_sessions=embargo_sessions,
        min_folds_for_verdict=min_folds_for_verdict,
    )
    depth = tuple(
        (
            p.n_sessions,
            p.geometry_min_train_sessions,
            p.geometry_min_test_sessions,
            p.n_folds_formed,
        )
        for p in points
    )
    return GeometryDepthProfile(
        n_folds=n_folds,
        embargo_sessions=embargo_sessions,
        min_folds_for_verdict=min_folds_for_verdict,
        structural_minima=minima,
        depth_points=depth,
    )


# ---------------------------------------------------------------------------
# 2) Challenger class sample pressure (descriptive, not a floor)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChallengerClassProfile:
    """Describes sample pressure for a challenger class — not a selected N."""

    challenger_class: str  # "fixed" | "learned"
    example_ids: tuple[str, ...]
    # Free parameters fit on train (0 for pure fixed scorers).
    n_fit_parameters: int
    # Descriptive ratios at a candidate train-session depth (study input only).
    # sessions_per_parameter = train_sessions / max(n_fit_parameters, 1)
    notes: str


def fixed_challenger_profiles() -> tuple[ChallengerClassProfile, ...]:
    return (
        ChallengerClassProfile(
            challenger_class="fixed",
            example_ids=("equal_sleeves", "production", "gate_off"),
            n_fit_parameters=0,
            notes=(
                "No train fit; session depth still matters for OOS IC stability "
                "and regime coverage, not for parameter estimation."
            ),
        ),
    )


def learned_challenger_profiles() -> tuple[ChallengerClassProfile, ...]:
    return (
        ChallengerClassProfile(
            challenger_class="learned",
            example_ids=("ridge_reweight", "elastic_net_reweight"),
            n_fit_parameters=5,  # typical sleeve/factor count; descriptive
            notes=(
                "Linear reweight over ~K sleeves/factors. Policy floors must "
                "consider train sessions relative to K and collinearity — "
                "not selected in this module."
            ),
        ),
        ChallengerClassProfile(
            challenger_class="learned",
            example_ids=("lgbm_reweight",),
            n_fit_parameters=-1,  # effective capacity unknown / path-dependent
            notes=(
                "Tree ensemble capacity is path-dependent (depth, leaves, "
                "regularization). Policy floors cannot reuse linear K heuristics."
            ),
        ),
    )


def sessions_per_parameter(
    train_sessions: int, *, n_fit_parameters: int
) -> float | None:
    """Descriptive ratio only; None when parameters unknown (e.g. LGBM)."""
    if n_fit_parameters < 0:
        return None
    if n_fit_parameters == 0:
        return float("inf")
    if train_sessions < 1:
        return 0.0
    return float(train_sessions) / float(n_fit_parameters)


# ---------------------------------------------------------------------------
# 3) Session-aware IC + descriptive uncertainty (no CI method chosen)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionICPoint:
    session: str
    rank_ic: float | None
    n_names: int


@dataclass(frozen=True)
class SessionICSummary:
    """Descriptive summaries only — not a product CI / significance law."""

    n_sessions: int
    n_sessions_with_ic: int
    mean_session_ic: float | None
    median_session_ic: float | None
    stdev_session_ic: float | None
    # Fraction of sessions with defined IC > 0 (descriptive hit rate).
    frac_session_ic_positive: float | None
    pooled_rank_ic: float | None
    notes: tuple[str, ...] = ()


def session_rank_ics(
    session_scores_returns: Mapping[str, Sequence[tuple[float, float]]],
) -> list[SessionICPoint]:
    """Per-session rank IC. Keys are session dates (or session ids)."""
    points: list[SessionICPoint] = []
    for session in sorted(session_scores_returns.keys()):
        pairs = list(session_scores_returns[session])
        scores = [p[0] for p in pairs]
        rets = [p[1] for p in pairs]
        ic = ic_safe(scores, rets)
        points.append(SessionICPoint(session=session, rank_ic=ic, n_names=len(pairs)))
    return points


def summarize_session_ics(
    points: Sequence[SessionICPoint],
    *,
    pooled_scores: Sequence[float] | None = None,
    pooled_returns: Sequence[float] | None = None,
) -> SessionICSummary:
    defined = [p.rank_ic for p in points if p.rank_ic is not None]
    n_def = len(defined)
    mean_ic = statistics.fmean(defined) if n_def else None
    med_ic = statistics.median(defined) if n_def else None
    stdev_ic = statistics.pstdev(defined) if n_def >= 2 else (0.0 if n_def == 1 else None)
    frac_pos = (
        sum(1 for x in defined if x > 0.0) / n_def if n_def else None
    )
    pooled: float | None = None
    notes: list[str] = [
        "stdev is population stdev of session ICs (descriptive dispersion)",
        "no bootstrap / block-bootstrap / Newey-West chosen as product law",
        "pooled_rank_ic is cross-sectional pool over all rows if provided",
    ]
    if pooled_scores is not None and pooled_returns is not None:
        pooled = ic_safe(pooled_scores, pooled_returns)
    return SessionICSummary(
        n_sessions=len(points),
        n_sessions_with_ic=n_def,
        mean_session_ic=mean_ic,
        median_session_ic=med_ic,
        stdev_session_ic=stdev_ic,
        frac_session_ic_positive=frac_pos,
        pooled_rank_ic=pooled,
        notes=tuple(notes),
    )


def group_pairs_by_session(
    rows: Iterable[tuple[str, float, float]],
) -> dict[str, list[tuple[float, float]]]:
    """Group (session, score, return) rows into session → [(score, return)]."""
    out: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for session, score, ret in rows:
        out[str(session)].append((float(score), float(ret)))
    return dict(out)


# ---------------------------------------------------------------------------
# 4) Final untouched holdout placement (geometry only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HoldoutGeometryCandidate:
    """Where a final holdout would sit — candidate parameter, not selected."""

    n_sessions_total: int
    holdout_sessions_candidate: int
    n_sessions_for_folds: int
    folds_formed: int
    # Last fold test end index exclusive in the fold region [0, n_for_folds).
    last_test_end_i: int | None
    # Holdout occupies the final H sessions of the full calendar.
    holdout_start_i: int
    holdout_end_i: int  # exclusive
    # True if holdout is strictly after all fold test sessions.
    holdout_after_all_fold_tests: bool
    notes: str


def holdout_geometry_candidate(
    n_sessions_total: int,
    *,
    n_folds: int,
    embargo_sessions: int,
    holdout_sessions_candidate: int,
) -> HoldoutGeometryCandidate:
    """Pure placement study for a *candidate* holdout length.

    Does not choose the holdout length for Protocol. Fail-soft: empty folds
    still report geometry.
    """
    h = max(0, int(holdout_sessions_candidate))
    n = max(0, int(n_sessions_total))
    n_fold_region = max(0, n - h)
    folds = simulate_session_folds(
        n_fold_region, n_folds=n_folds, embargo_sessions=embargo_sessions
    )
    last_end = max((f.test_end_i for f in folds), default=None)
    holdout_start = n_fold_region
    holdout_end = n
    after = True
    if last_end is not None and last_end > holdout_start:
        after = False
    if h <= 0:
        after = False
        note = "candidate holdout_sessions=0 (no final holdout)"
    elif n_fold_region < n_folds + 1:
        note = "fold region too short for any fold under n_folds+1 rule"
    elif not folds:
        note = "no folds formed in fold region (embargo/depth)"
    elif after:
        note = "holdout strictly after all fold test blocks (geometry OK for study)"
    else:
        note = "holdout overlaps fold test region (invalid placement)"
    return HoldoutGeometryCandidate(
        n_sessions_total=n,
        holdout_sessions_candidate=h,
        n_sessions_for_folds=n_fold_region,
        folds_formed=len(folds),
        last_test_end_i=last_end,
        holdout_start_i=holdout_start,
        holdout_end_i=holdout_end,
        holdout_after_all_fold_tests=after,
        notes=note,
    )


def sweep_holdout_candidates(
    n_sessions_total: int,
    *,
    n_folds: int,
    embargo_sessions: int,
    holdout_candidates: Sequence[int],
) -> list[HoldoutGeometryCandidate]:
    return [
        holdout_geometry_candidate(
            n_sessions_total,
            n_folds=n_folds,
            embargo_sessions=embargo_sessions,
            holdout_sessions_candidate=h,
        )
        for h in holdout_candidates
    ]


# ---------------------------------------------------------------------------
# 5) Multiplicity bookkeeping (record search; no correction applied)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiplicitySearchRecord:
    """Audit record for a multi-challenger search — no p-value correction.

    Product law must later name which correction (if any) is required. This
    only forces the search set and selection rule to be explicit.
    """

    search_id: str
    challenger_ids: tuple[str, ...]
    selection_rule: str  # e.g. "pre_registered_primary" | "max_mean_ic_unadjusted"
    primary_metric: str
    n_comparisons: int
    notes: str = ""

    def __post_init__(self) -> None:
        # frozen dataclass: validate via object.__setattr__ not needed if we check
        if len(self.challenger_ids) != self.n_comparisons:
            raise ValueError(
                "n_comparisons must equal len(challenger_ids) "
                f"({self.n_comparisons} vs {len(self.challenger_ids)})"
            )


def multiplicity_search_record(
    *,
    search_id: str,
    challenger_ids: Sequence[str],
    selection_rule: str,
    primary_metric: str = "mean_fold_ic_edge",
    notes: str = "",
) -> MultiplicitySearchRecord:
    ids = tuple(str(c) for c in challenger_ids)
    return MultiplicitySearchRecord(
        search_id=search_id,
        challenger_ids=ids,
        selection_rule=selection_rule,
        primary_metric=primary_metric,
        n_comparisons=len(ids),
        notes=notes
        or (
            "no multiplicity correction applied in design module; "
            "policy contract must name the rule before POLICY_GRADE"
        ),
    )


# ---------------------------------------------------------------------------
# Design study bundle (reportable, non-authoritative)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MLOOS02DesignStudyBundle:
    """Non-authoritative design study snapshot for human vetting."""

    draft_contract_id: str
    required_axes: tuple[str, ...]
    geometry: GeometryDepthProfile
    fixed_profiles: tuple[ChallengerClassProfile, ...]
    learned_profiles: tuple[ChallengerClassProfile, ...]
    holdout_sweep: tuple[HoldoutGeometryCandidate, ...]
    open_decisions: tuple[str, ...]
    explicit_non_selections: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_contract_id": self.draft_contract_id,
            "required_axes": list(self.required_axes),
            "geometry": self.geometry.to_dict(),
            "fixed_profiles": [asdict(p) for p in self.fixed_profiles],
            "learned_profiles": [asdict(p) for p in self.learned_profiles],
            "holdout_sweep": [asdict(h) for h in self.holdout_sweep],
            "open_decisions": list(self.open_decisions),
            "explicit_non_selections": list(self.explicit_non_selections),
            "policy_confirmation_contracts_registered": [],  # always empty here
        }


def build_ml_oos_02_design_study(
    *,
    n_folds: int = 3,
    embargo_sessions: int = 20,
    min_folds_for_verdict: int = 2,
    n_sessions_total_for_holdout: int = 120,
    holdout_candidates: Sequence[int] | None = None,
) -> MLOOS02DesignStudyBundle:
    """Assemble a design-study bundle. Does not mutate Protocol or registries."""
    holdouts = tuple(
        holdout_candidates
        if holdout_candidates is not None
        else (0, 5, 10, 20, 40)
    )
    geometry = build_geometry_depth_profile(
        n_folds=n_folds,
        embargo_sessions=embargo_sessions,
        min_folds_for_verdict=min_folds_for_verdict,
    )
    holdout_sweep = tuple(
        sweep_holdout_candidates(
            n_sessions_total_for_holdout,
            n_folds=n_folds,
            embargo_sessions=embargo_sessions,
            holdout_candidates=holdouts,
        )
    )
    open_decisions = (
        "Select policy_min_train_sessions / policy_min_test_sessions separately "
        "for fixed vs learned challenger classes (not geometry minima).",
        "Choose session-IC primary metric (mean daily IC vs pooled) and an "
        "uncertainty method with session dependence handled explicitly.",
        "Choose final_holdout_sessions and whether holdout is confirmatory-only "
        "or also gates WIN/LOSE.",
        "Choose multiplicity rule for multi-challenger searches "
        "(pre-registration vs adjusted selection).",
        "Define regime-coverage requirements (if any) before POLICY_GRADE.",
        "Register a non-empty POLICY_CONFIRMATION_CONTRACTS entry only after "
        "the above are frozen in a versioned contract document.",
    )
    non_selections = (
        "No policy_min_* written into Protocol by this study module.",
        "No CI method adopted as product law.",
        "No holdout length adopted as product law.",
        "No multiplicity correction applied.",
        f"Draft id {POLICY_CONFIRMATION_CONTRACT_DRAFT_ID} is not promote-eligible.",
    )
    return MLOOS02DesignStudyBundle(
        draft_contract_id=POLICY_CONFIRMATION_CONTRACT_DRAFT_ID,
        required_axes=POLICY_CONFIRMATION_REQUIRED_AXES,
        geometry=geometry,
        fixed_profiles=fixed_challenger_profiles(),
        learned_profiles=learned_challenger_profiles(),
        holdout_sweep=holdout_sweep,
        open_decisions=open_decisions,
        explicit_non_selections=non_selections,
    )


def format_design_study_report(bundle: MLOOS02DesignStudyBundle) -> str:
    """Human-readable report for CLI / docs regeneration."""
    lines: list[str] = [
        "ML-OOS-02 design study (non-authoritative)",
        f"draft_contract_id={bundle.draft_contract_id}",
        "",
        "== Structural geometry minima (NOT policy floors) ==",
        bundle.geometry.structural_minima.rationale,
        "",
        f"{'n_sess':>7}  {'folds':>5}  {'min_tr':>6}  {'min_te':>6}",
        "-" * 32,
    ]
    for n, tr, te, nf in bundle.geometry.depth_points:
        lines.append(
            f"{n:7d}  {nf:5d}  {tr if tr is not None else 0:6d}  "
            f"{te if te is not None else 0:6d}"
        )
    lines.extend(
        [
            "",
            "== Challenger class profiles (descriptive) ==",
        ]
    )
    for p in (*bundle.fixed_profiles, *bundle.learned_profiles):
        lines.append(
            f"- {p.challenger_class}: {', '.join(p.example_ids)} "
            f"n_fit_parameters={p.n_fit_parameters}"
        )
        lines.append(f"  {p.notes}")
    lines.extend(["", "== Holdout placement candidates =="])
    for h in bundle.holdout_sweep:
        lines.append(
            f"- holdout={h.holdout_sessions_candidate}: "
            f"folds_formed={h.folds_formed} "
            f"after_tests={h.holdout_after_all_fold_tests} "
            f"({h.notes})"
        )
    lines.extend(["", "== Open decisions =="])
    for d in bundle.open_decisions:
        lines.append(f"- {d}")
    lines.extend(["", "== Explicit non-selections =="])
    for d in bundle.explicit_non_selections:
        lines.append(f"- {d}")
    return "\n".join(lines)
