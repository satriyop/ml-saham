# C2 hard-filter decision-law vet

**Status:** metric form vetted; numerical authority blocked.

Scope: `screener.accum.hard_filters` only. This review did not rank discovery
variants, inspect a new confirmation result, register a PolicySpec, or change a
verdict.

## Objective conclusion

The repository can lock the shape of the C2 decision law before more data
arrives, but it cannot honestly lock the three numerical limits from current
code or data alone.

The missing authority is operational, not statistical:

- there is no accepted mapping from one filtered candidate to capital,
  execution, or review value;
- `accum_path_v1.win_margin=0.01` is a rank-IC margin, not an H10-return margin,
  and cannot be reused for a gate;
- the shipped bottom-decile tail proxy compares ranked scores, not allowed and
  rejected gate books;
- the discovery quantiles describe candidate thresholds; they do not justify a
  maximum acceptable decision change;
- `gate_decision_quality.v1` reports descriptive books but does not define
  portfolio positions or transaction turnover.

Choosing `10 bps`, `25%`, or another convenient constant would therefore be a
maintainer preference disguised as methodology. It would also make later power
or non-inferiority claims circular. Smallest-effect and non-inferiority bounds
must be fixed from practical relevance before confirmatory inspection, not from
the effect that the available sample can detect.

## Vetted metric form

For session `s`, ticker `i`, strict H10 excess `y[i,s]`, verified production
decision `a0[i,s]` and frozen challenger decision `a1[i,s]`, where allow is one
and reject is zero:

```text
book_utility[k,s] = mean_i(a[k,i,s] * y[i,s])
utility_delta[s]  = book_utility[1,s] - book_utility[0,s]
decision_change[s] = mean_i(abs(a1[i,s] - a0[i,s]))
```

This is the narrowest honest candidate estimand because it:

- keeps calendar sessions as the time-series unit;
- gives a rejected opportunity zero excess contribution instead of deleting it
  and mechanically improving the allowed-book mean;
- compares challenger and production on the same ticker/session population;
- directly counts both harmful allows and costly false blocks;
- distinguishes decision disagreement from actual portfolio turnover.

The three future gates should use this form:

| Gate | Vetted form | Still requires authority |
|---|---|---|
| Material improvement | Session-native mean `utility_delta` must clear a predeclared positive smallest useful effect, with the later confirmation uncertainty rule also passing | `minimum_useful_h10_excess` in fraction units and its business/cost justification |
| Tail non-inferiority | A predeclared lower-tail statistic of session `book_utility[1] - book_utility[0]` must not cross a predeclared negative margin | tail probability/statistic, margin, and minimum tail-session support |
| Decision churn | Session-native `decision_change` must stay below a predeclared limit in every contributing fold | maximum decision-change rate; actual portfolio turnover requires a separate position/allocation contract |

Fold-wise values and denominators remain mandatory. Pooled ticker/session rows
must not become the inferential sample, and allowed-book mean alone must not be
the primary success metric.

## Authority matrix

| Boundary | Owner/source | Missing state | Invalid/conflicting state | May contribute when |
|---|---|---|---|---|
| Production decisions | Verified ai-saham snapshot v4 plus adapter v2 replay on the explicit cohort | `BLOCKED_POLICY` | Snapshot, cohort, adapter, or conformance mismatch fails closed | Exact production decision is reproduced for every unit |
| Candidate decisions | One frozen C2 proposal chosen before confirmation outcomes | No candidate; discovery only | Multiple candidates or changed threshold invalidates confirmation | Candidate identity and decision vector are immutable |
| H10 target | Same-session stock/IHSG target from the strict discovery panel | Horizon unavailable | Missing, duplicate, non-finite, or mismatched endpoints fail closed | Exact common population reconciles |
| Decision-law constants | Maintainer-approved utility/capacity contract | `BLOCKED_DECISION_AUTHORITY` | Constants inferred from discovery/confirmation outcomes are leakage | Units, rationale, and approval predate confirmation inspection |
| Confirmation inference | Later versioned C2 Protocol | `INCONCLUSIVE`/`BLOCKED_DATA` | Pooled-row inference, insufficient folds/support, or reused discovery sessions fails closed | Every materiality, tail, churn, fold, and uncertainty gate passes |

## Required maintainer decisions

Before a verdict Protocol can be implemented, one short decision record must
state all of the following in operational terms:

1. the smallest H10 excess improvement per evaluated opportunity worth a human
   production review;
2. the maximum acceptable lower-tail degradation and the chosen tail statistic;
3. the maximum acceptable production-versus-candidate decision-change rate;
4. whether the zero-return treatment for a rejected opportunity matches the
   intended equal-notional decision book;
5. the later uncertainty/confirmation rule, which remains dependent on the
   unfinished policy-confirmation methodology.

Until then, `screen_accum_hard_filters.preregistration.v1` remains correctly
discovery-only, all three numerical fields remain `None`, and
`engine_registration_authorized=false` remains mandatory.

## Sources used for the methodological judgment

- Lakens, *Equivalence Tests: A Practical Primer*:
  <https://doi.org/10.1177/1948550617697177> — practical-equivalence bounds
  require a smallest effect of interest rather than a post-hoc convenient
  threshold.
- Acerbi and Tasche, *Expected Shortfall: a natural coherent alternative to
  Value at Risk*: <https://arxiv.org/abs/cond-mat/0105191> — supports a
  lower-tail mean family, but does not determine this product's tail probability
  or non-inferiority margin.
