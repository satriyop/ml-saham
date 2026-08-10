# ML-OOS-02 — nested studentized interval vet (2026-08-10)

**Status: IMPLEMENTED AND SCREENED / NOT ADOPTED**

## Scope and authority

This slice evaluates a nested studentized stationary-bootstrap interval for the
synthetic session-level mean on complete calendars. It does not inspect live
outcomes, select a block or session floor, support missing calendars, register
`POLICY_CONFIRMATION_CONTRACTS`, or unblock Task 06.

Clean-break identities:

- calibration: `policy_confirmation_calibration.synthetic.v5`;
- acceptance study: `policy_confirmation_acceptance.synthetic.v4`.

## Why naive bootstrap-t was rejected

For dependent data, dividing by the ordinary sample standard deviation ignores
serial dependence. Davison showed that a naively implemented percentile-t
method need not improve materially on a normal approximation, while an
appropriately adjusted variance estimator can improve it
([paper](https://doi.org/10.1111/j.1467-842X.1993.tb01327.x)).

The automatic block selector already present in this repository targets
stationary-bootstrap variance estimation. It is not silently reused here:
Hall, Horowitz, and Jing show that optimal block-size order depends on whether
the objective is variance, one-sided distribution, or two-sided distribution
estimation
([paper](https://doi.org/10.1093/biomet/82.3.561)).

## Implemented candidate

For one complete finite calendar series and one explicit block length:

1. draw `B` outer stationary-bootstrap samples;
2. calculate each outer sample mean;
3. for every outer sample, draw `R` inner stationary-bootstrap samples using
   the same explicit block length;
4. use the dispersion of its inner means as that outer replicate's standard
   error;
5. form roots `(outer_mean - original_mean) / inner_standard_error`;
6. use the dispersion of outer means as the original-scale standard error;
7. invert the equal-tailed root quantiles to obtain the interval.

Any missing calendar position is rejected before resampling. A zero,
non-finite, or numerically unusable studentizer returns
`DEGENERATE_STUDENTIZER`; it does not fall back to percentile or HAC output.
Outer resamples, inner resamples, and block length are material method identity.

The structure matches the nested studentization path independently exposed by
`arch.bootstrap.StationaryBootstrap`: its outer replicate standard errors come
from cloned inner bootstraps and its final scale comes from outer-estimate
dispersion. `arch` remains a development cross-check, not a runtime dependency.

On a seeded AR(1)=0.6 series with 120 observations, block 5, 100 outer and 50
inner resamples:

| Implementation | 95% interval |
|---|---|
| Local | `[-0.0854, 0.4498]` |
| `arch` independent run | `[-0.1339, 0.4010]` |

Different bootstrap RNG streams prevent bound equality; both intervals have
nearly identical width and overlap strongly. Deterministic local golden tests
lock the shipped implementation itself.

## Executable screen

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_acceptance.py \
  --higher-grid --studentized-only --complete-calendar-only \
  --replications 20 --bootstrap-resamples 30 \
  --studentize-resamples 20 --json
```

The explicit block grid is 3/5/10. It is a sensitivity grid, not a search whose
best cell can be reported as confirmatory. The complete-calendar scope contains
paired moderate and strong-dependence null/alternative cells at 360/504/756
sessions. Thin/missing support remains excluded by the separate missing-calendar
contract.

All nine method/calendar candidates passed **0 of 4** required cells. The run
is too small for the candidate Monte Carlo error criterion, but the substantive
pattern also remains unfavorable:

| Sessions | Block | Moderate power / width-effect | Strong power / width-effect |
|---:|---:|---:|---:|
| 360 | 3 / 5 / 10 | 0.60/2.08 · 0.65/1.83 · 0.55/2.12 | 0.35/4.11 · 0.35/4.61 · 0.20/5.28 |
| 504 | 3 / 5 / 10 | 0.65/1.73 · 0.75/1.68 · 0.65/1.82 | 0.05/3.47 · 0.10/3.36 · 0.10/3.81 |
| 756 | 3 / 5 / 10 | 0.75/1.26 · 0.75/1.36 · 0.80/1.31 | 0.30/3.21 · 0.40/2.81 · 0.25/3.50 |

At 20 replications these point rates have substantial Monte Carlo uncertainty
and cannot select a block. They are sufficient to reject immediate adoption:
strong-dependence power and width remain far from the candidate requirements,
and every candidate fails the formal law.

## Objective conclusion

- Nested studentization is implemented correctly enough for further synthetic
  measurement, with explicit failure behavior and no runtime dependency.
- No block length, inner-resample count, interval method, session count, or
  floor is adopted.
- Studentization does not rescue strong-dependence operating characteristics in
  the current DGP screen.
- Historical artifacts are not upgraded.
- Confirmation registry remains empty and Task 06 remains blocked.

The next methodology question is whether a calibrated/basic stationary
bootstrap interval should be screened, or whether the acceptance DGP/effect
definition needs independent scientific review before adding more methods.
