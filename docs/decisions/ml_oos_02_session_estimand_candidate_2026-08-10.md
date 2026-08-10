# ML-OOS-02 — session-native fixed score estimand candidate (2026-08-10)

**Status: IMPLEMENTED FOR MEASUREMENT / NOT ADOPTED**

Contract identity:
`policy_confirmation_session_estimand.accum_score_weights.equal_sleeves.candidate.v1`.

## Scope

The candidate answers one narrow question:

> For a fixed `equal_sleeves` challenger against a caller-supplied production
> score series under
> `screener.accum.score_weights`, what is the unweighted calendar-session mean
> of `IC(equal_sleeves, H10 excess) - IC(production, H10 excess)`?

It uses the shipped `ic_safe` calculation separately within every session. It
does not change the current pooled-row runner, select a minimum-name floor,
select an effect floor, register a confirmation contract, or authorize Task 06.

## Candidate input and denominator contract

- The caller supplies the exact strictly increasing session calendar. Absence
  of an entire expected session is `MISSING_CALENDAR_SESSION`.
- The sample grain is one ticker/session observation with production score,
  equal-sleeves score, and primary H10 excess return.
- Duplicate ticker/session keys are contract errors.
- Missing, non-numeric, or non-finite name-level values invalidate that session;
  they are not deleted or imputed.
- Constant production rank, challenger rank, or target rank has a distinct
  typed status.
- The minimum-name value is mandatory input named
  `minimum_names_candidate`; there is deliberately no default. Recording it in
  one measurement does not adopt a product floor.
- The cross-session mean exists only when every expected session is measured.
  There is no calendar compaction.

## Why rank-IC difference

The score-weight policy is a ranking decision and the current runner already
uses rank IC at primary H10. Taking the challenger-minus-production difference
inside each session keeps the comparison paired and makes the calendar session,
not ticker/session row count, the time-series inferential unit.

This is still only an estimand candidate. Before adoption, further vetting must
decide:

- whether equal session weighting is appropriate;
- the minimum valid-name and population-completeness rule;
- whether H10 IC difference alone represents enough product value;
- the separate tail-risk and turnover constraints;
- fold aggregation and final-holdout behavior;
- the smallest effect that would justify human review.

## Historical and production boundary

Existing exploratory artifacts retain their pooled fold IC semantics and are
not reinterpreted. `accum_path_v1` remains `EXPLORATORY`, the confirmation
registry remains empty, no upstream database is read or written by this
measurement function, and Task 06 remains blocked.

The function does not resolve or verify a production snapshot. Its result is
therefore stamped `input_identity_binding_status=NOT_BOUND_MEASUREMENT_INPUT`
and `production_identity_verified=False`. A later application composition must
bind exact cohort, snapshot, adapter, protocol, and row lineage before this
estimand can contribute to confirmation authority.
