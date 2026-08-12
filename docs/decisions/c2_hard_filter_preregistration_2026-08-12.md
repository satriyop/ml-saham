# C2 hard-filter methodology preregistration v1

**Status:** discovery methodology locked; engine and verdict remain blocked.

Contract: `screen_accum_hard_filters.preregistration.v1`

Module: `ml_saham.challenge.screen_filter_preregistration`

## Decision

C2 uses two strictly separated stages:

```text
TRAIN-FOLD DISCOVERY                     FUTURE CONFIRMATION
--------------------                     -------------------
train-only q25/q50/q75                    exactly one frozen candidate
one gate at a time          proposal      sessions unseen by discovery
report every variant       --------->     >=2 post-embargo OOS folds
NO WIN / LOSE                            verdict only after open laws close
```

Discovery cannot grant a verdict or production recommendation. It may propose
one candidate for later confirmation. Confirmation cannot reuse discovery OOS
sessions, change the selected candidate, or evaluate several candidates and
keep the best.

## Locked axes

| Axis | v1 contract |
|---|---|
| Policy authority | Verified `screener.accum.hard_filters` snapshot + adapter v2 producer conformance |
| Population | One explicit ACCUM compatibility cohort; capture-evaluated rows only |
| Sample unit | Unique `(ticker, session_date)`, canonical window 7 |
| Primary outcome | H10 stock excess return versus IHSG over the same sessions |
| Discovery grid | Train-fold empirical quantiles 0.25 / 0.50 / 0.75 over finite numeric values per gate |
| Search shape | One gate at a time; no Cartesian combinations |
| Multiplicity | Report all discovery variants, name no winner, confirm exactly one frozen candidate |
| Split law | Ordered OOS, 20-session embargo, at least two valid folds |
| Per-side support | At least 20 labeled allowed and 20 labeled rejected rows in every contributing fold |
| Metrics | `gate_decision_quality.v1`: allowed/blocked books, false blocks, harmful allows, opportunity cost, first/overlap attribution |

The quantile grid is a discovery device, not a production floor. Quantiles are
fit inside each train fold only. Numeric thresholds observed during discovery
do not become production authority and are not silently reused as a verdict.
Missing inputs are not imputed into the quantile calculation; once a candidate
gate is applied, missing behavior remains the shipped live first-match semantic.

## Deliberately open gates

The following are not objectively determined by current code or data and are
therefore explicit blockers, not guessed constants:

- minimum improvement considered materially useful;
- tail-risk non-inferiority rule;
- turnover/churn constraint.

Until a later version closes all three, the contract states
`engine_registration_authorized=false`; no PolicySpec, CLI tournament, or
WIN/LOSE path may be registered.

## Live read-only vet snapshot (2026-08-12)

The current maintainer DB was inspected through existing read-only boundaries
with before/after file, SQLite, schema, and row-count fingerprints.

| Evidence | Observed |
|---|---:|
| Explicit ACCUM cohort | `sha256:355e5b59600dbdc9f762f7b373e8879b7cda9a1e55e18bd590461315cfe1e091` |
| Production snapshots | 9, verified |
| Selected / extracted / unextractable | 1,125 / 1,125 / 0 |
| Sessions / tickers | 25 / 45 |
| Corpus H10 availability only | 675 available / 450 unavailable |
| Hard-filter challenge preparation | `BLOCKED_POLICY` |
| Hard-filter folds formed | 0 |
| DB unchanged | `true` |

Corpus H10 availability is only a coverage check; it is not the tournament's
H10 excess-vs-IHSG target. With 25 sessions, the cohort is also below the
existing 44-session structural point where two post-embargo folds first become
possible. This snapshot may drift as ai-saham captures more sessions.

## Exit to implementation

The next C2 slice may implement the discovery measurement panel, but it must
remain proposal-only. Engine registration requires all of:

1. H10 excess panel and PIT lineage tests;
2. at least two valid post-embargo folds with per-side support;
3. exactly one candidate frozen before future confirmation outcomes;
4. versioned material-improvement, tail-risk, and turnover laws;
5. updated Protocol/artifact identities and acceptance tests.
