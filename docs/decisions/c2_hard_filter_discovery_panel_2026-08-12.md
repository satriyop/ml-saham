# C2 hard-filter proposal-only discovery panel

**Status:** shipped as measurement; not an engine tournament.

Contract: `screen_accum_hard_filters.discovery.v1`

Module: `ml_saham.challenge.screen_filter_discovery`

## Outcome

The discovery panel now executes the preregistered train-only grid without
granting policy authority:

```text
verified cohort + snapshot + adapter conformance
                       |
                       v
window-7 hard-filter inputs + strict same-session H10 excess
                       |
                       v
ordered/purged folds; train-only q25/q50/q75
                       |
                       v
all gate/fold/quantile evidence, no ranking, no winner
```

No PolicySpec, engine registry row, CLI command, challenge artifact, promote
packet, or production write is added.

## Authority matrix

| Boundary | Exact authority | Integrity/coverage proof | Missing or conflicting state | May contribute when |
|---|---|---|---|---|
| Observation population | ai-saham ACCUM `learning_observations`, explicit compatibility ID | Central cohort helper, exact purpose/contract, unique ticker/session reconciliation | `BLOCKED_POLICY` for missing/wrong cohort; `BLOCKED_DATA` for malformed/duplicate units | Every selected unit extracts under canonical window 7 |
| Production policy | ai-saham nine-row snapshot v4 set + ml-saham adapter v2 conformance | Existing canonical snapshot/digest checks and ADR-068 cohort binding | `BLOCKED_POLICY` | Exact selected cohort composes successfully |
| H10 target and benchmark | ai-saham candles read through the read-only adapter | Stock and IHSG share the identical start and H10 end trading sessions | Unit is label-unavailable; never substitute another end date or corpus SUCCESS/FAILURE | Both finite positive closes exist at the exact endpoints |
| Discovery folds | `accum_path_v1` session splitter | Ordered sessions, 20-session embargo, no overlap, at least two folds | `NOT_READY_GEOMETRY` | Existing fold geometry and row floors pass |
| Threshold proposal | Preregistration v1 | q25/q50/q75 from finite numeric train values only; OOS mutation tests | Incomplete matrix is `BLOCKED_DATA` | Every gate/quantile/fold threshold is enabled and evaluable |
| Decision evidence | `gate_decision_quality.v1` | Allowed/rejected denominators and attribution preserved per fold | `support_ok=false` when either side has fewer than 20 labeled rows | Descriptive proposal evidence only; never WIN/LOSE |

The result binds the exact consumed panel material in `panel_digest`, separately
from the cohort ID and methodology digest. It reports selected, labeled,
label-unavailable, malformed, and duplicate denominators.

## Live read-only result (2026-08-12)

Exact cohort:
`sha256:355e5b59600dbdc9f762f7b373e8879b7cda9a1e55e18bd590461315cfe1e091`.

| Evidence | Value |
|---|---:|
| Verified production snapshots | 9 |
| Selected / H10 unavailable | 1,170 / 450 |
| Strict H10 panel rows | 720 |
| H10-eligible sessions | 16 |
| Valid post-embargo folds | 0 |
| Discovery variants emitted | 0 |
| Status | `NOT_READY_GEOMETRY` |
| Selected candidate / winner | `None` / `None` |
| Upstream DB unchanged | `true` |

The strict panel count differs from the older generic/corpus-label coverage
counts because this contract requires the exact same stock/IHSG end session.
It is the discovery target denominator, not a reinterpretation of corpus path
labels.

## Remaining blockers

- More prospective captures and H10 maturation until at least two valid folds.
- Per-side support must pass for every contributing fold.
- One proposal must be frozen before future confirmation data is observed.
- Material improvement, tail-risk, and turnover laws remain open.
- Only a later Protocol/version may authorize engine registration or verdicts.
