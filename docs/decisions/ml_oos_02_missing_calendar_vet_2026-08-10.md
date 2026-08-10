# ML-OOS-02 — missing-calendar methodology vet (2026-08-10)

**Status: FAIL-CLOSED CONTRACT IMPLEMENTED / NO FLOOR OR IMPUTATION ADOPTED**

## Scope and authority

This vet covers the ordered session-estimand series used only by synthetic
ML-OOS-02 confirmation-method calibration. It does not change an upstream
extractor, inspect a live cohort, select a session or missingness floor,
register `POLICY_CONFIRMATION_CONTRACTS`, or unblock Task 06.

Clean-break identities:

- calibration at this decision: `policy_confirmation_calibration.synthetic.v4`;
- acceptance study at this decision: `policy_confirmation_acceptance.synthetic.v3`.

## Code-truth finding

Before this slice, three nominally comparable candidates treated the same gap
differently:

- automatic stationary bootstrap rejected every non-finite calendar position;
- explicit stationary bootstrap resampled the full index sequence but deleted
  missing values inside each resample before taking its mean;
- Newey-West deleted missing values for the mean and used a different set of
  finite pairs at each lag.

The acceptance layer then checked only the aggregate observed-session fraction.
Consequently, methods could use different effective calendars and dependence
structures under one candidate law. This was wrong methodology, not merely a
documentation discrepancy.

## Vetted contract

1. Fold geometry defines the full ordered eligible-session calendar. Missing
   positions are never removed before dependence estimation.
2. A finite numeric session estimand is `OBSERVED`.
3. An expected session whose estimand cannot be formed is explicit `None` and
   is classified `MISSING_CALENDAR_SESSION_UNSUPPORTED` by current methods.
4. NaN, infinity, booleans, strings, and other invalid numeric inputs are
   `INVALID_NONFINITE_ESTIMAND`, not expected missingness.
5. The assessment records calendar count, observed count, missing count,
   invalid count, observed fraction, and longest consecutive missing run.
6. Every currently implemented interval candidate requires a complete calendar
   and fails closed on any unavailable position. No deletion, compaction, or
   imputation fallback is allowed.
7. Aggregate calibration and acceptance output records typed method-failure
   counts. `METHOD_NOT_MEASURABLE` therefore retains its causal audit trail.

The `minimum_observed_session_fraction=0.90` candidate tolerance remains
measurement-only. It is neither permission to delete gaps nor an adopted
missingness floor. It can become operational only if a separately identified
missing-data method is preregistered and calibrated.

## Methodological basis

Ignoring a missingness process requires assumptions such as missing at random
and parameter distinctness; those assumptions do not follow from a high
observed fraction. See Rubin,
[Inference and missing data](https://doi.org/10.1093/biomet/63.3.581).

The synthetic gap here is triggered by insufficient cross-sectional breadth.
That mechanism can co-move with market state and the unobserved estimand, so
MCAR/MAR is not established. Recent time-series work on underreporting also
shows why ordinary permutation or block bootstrap can reproduce the wrong
autocovariance pattern when reporting rates vary over time: Li et al.,
[Testing serial dependence or cross dependence for time series with
underreporting](https://doi.org/10.1093/biomet/asae027).

Therefore complete-case and pairwise deletion are not defensible defaults.
Model-based imputation, inverse-probability weighting, or a bootstrap that
jointly models availability and estimands would introduce material assumptions
and requires its own preregistered DGP and operating-characteristic study.

## Objective consequences

- Existing v1-v3 calibration artifacts remain historical and are not
  reinterpreted.
- Thin/missing cells are now uniformly unmeasurable for automatic bootstrap,
  explicit bootstrap, and Newey-West.
- Fully observed cells retain their existing deterministic calculations.
- No session count, missingness percentage, interval method, or imputation
  scheme is selected.
- Confirmation registry remains empty and Task 06 remains blocked.

The studentized interval is vetted separately in
[`ml_oos_02_studentized_interval_vet_2026-08-10.md`](./ml_oos_02_studentized_interval_vet_2026-08-10.md).
Missing-calendar support remains a separate research track so its assumptions
cannot silently enter that interval comparison.
