# ML-OOS-02 — candidate operating-characteristic acceptance law (2026-08-10)

**Status: EXECUTABLE CANDIDATE / NOT ADOPTED**

Executable study:

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_acceptance.py
PYTHONPATH=src python scripts/report_ml_oos_02_acceptance.py --json
```

Study identity: `policy_confirmation_acceptance.synthetic.v2`. Version 2 adds
selected-block metadata and the automatic selector candidate. The candidate
law has a version plus a SHA-256 digest over every material tolerance and
policy field. Evidence grade remains `MEASUREMENT_ONLY`.

## Question and authority boundary

The study asks whether a fixed, preregistered challenger and one uncertainty
method have acceptable synthetic operating characteristics over a predeclared
stress grid. It does not inspect the live cohort, select a production floor,
register `POLICY_CONFIRMATION_CONTRACTS`, or authorize Task 06.

The simulator follows ADEMP-style discipline: aims, data-generating processes,
estimand, methods, and performance measures are explicit. Monte Carlo error is
reported because a simulation point estimate is itself uncertain. See Morris,
White, and Crowther,
[Using simulation studies to evaluate statistical methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC6492164/).

## Candidate law requiring human vetting

These are explicit engineering tolerances for evaluating the machinery. They
are not literature-mandated constants and are not adopted product law.

| Field | Candidate value | Meaning |
|---|---:|---|
| Monte Carlo confidence | 95% | Wilson bounds around binomial performance rates |
| Coverage lower bound | at least 92.5% | nominal 95% minus a 2.5-point tolerance |
| False-superiority upper bound | at most 7.5% | one-sided `lower > 0` claim plus a conservative tolerance |
| Directional-detection lower bound | at least 80% | prospective sensitivity target |
| Valid-replication rate | at least 99% | numerical failures cannot disappear |
| Observed-session fraction | at least 90% | missing sessions remain in the denominator |
| Maximum Monte Carlo SE | 2.5 percentage points | thin simulation runs cannot pass |
| Interval width / true effect | at most 2.0 | precision relative to the synthetic effect |
| Required outer folds | 3 | policy-grade candidate, not the exploratory two-fold minimum |
| Search | one preregistered challenger | unadjusted best-of-family is ineligible |
| Regime break | blocks confirmation | a numerical interval cannot cure nonstationarity |

The 80% sensitivity and width/effect tolerances are product-value choices that
still require maintainer acceptance. They must not be inferred from live OOS
effect sizes.

Acceptance uses the v2 one-sided false-superiority rate. The v1 base report's
two-sided false-rejection diagnostic is retained separately and must not be
substituted for the directional claim error rate.

## Predeclared grid

Calendars: 120, 180, and 252 total sessions, each with a 20-session untouched
tail. Every calendar contains paired null and `effect=0.05` alternative cells
for:

- moderate AR(1), heteroskedasticity, and missingness;
- strong dependence and heteroskedasticity;
- thin cross-sections with heavy name missingness.

Sensitivity methods are stationary-bootstrap block lengths 3/5/10 and
Newey-West lags 3/5/10. These are tuning probes, not adopted choices. Automatic
block-length selection remains a separate implementation; Politis and White
provide the candidate direction for a data-adaptive rule
([paper](https://www.math.ucsd.edu/~politis/SBblock-revER.pdf)).

An unadjusted best-of-five probe always returns `INELIGIBLE_MULTIPLICITY`.
Romano-Wolf-style stepdown is relevant when simultaneous candidate-level
claims are required, because it targets familywise error while using the joint
dependence structure
([paper](https://doi.org/10.1111/j.1468-0262.2005.00615.x)). It is not
implemented by this slice. A late regime-break probe always returns
`BLOCKED_REGIME`.

Eligible null/alternative pairs must match on all DGP material other than the
known effect and scenario identity. Hidden search width or a regime shift in an
eligible cell fails validation rather than becoming another favorable result.

## Executed evidence

The post-v2 evidence runs used 200 replications for HAC lag 3/5/10 across the
full grid, and 100 replications with 50 resamples for stationary-bootstrap
block 5. Every method/calendar candidate failed all six required stationary
cells at 120, 180, and 252 total sessions. The quick block-5 run also failed
the Monte Carlo precision criterion, as expected; however, failure was not only
a thin-run artifact. HAC cells also failed coverage, one-sided
false-superiority, power, and interval-width/effect criteria.

Selected moderate-stress evidence:

| Method | Sessions | Null coverage lower | Null false-superiority upper | Alternative coverage lower | Power lower | Width/effect |
|---|---:|---:|---:|---:|---:|---:|
| Bootstrap block 5 | 120 | 0.756 | 0.137 | 0.700 | 0.319 | 2.877 |
| Bootstrap block 5 | 180 | 0.850 | 0.112 | 0.756 | 0.366 | 2.394 |
| Bootstrap block 5 | 252 | 0.767 | 0.162 | 0.826 | 0.413 | 2.082 |
| Newey-West lag 5 | 120 | 0.828 | 0.096 | 0.833 | 0.227 | 3.284 |
| Newey-West lag 5 | 180 | 0.892 | 0.090 | 0.874 | 0.335 | 2.726 |
| Newey-West lag 5 | 252 | 0.833 | 0.114 | 0.868 | 0.378 | 2.293 |

These are seeded synthetic measurements, not monotonic sample-size laws or
market-performance estimates. The non-monotonic cells reinforce why a single
simulation point must not be converted into a floor.

## Automatic selector and higher grid follow-up

Implemented and vetted in
[`ml_oos_02_automatic_block_length_vet_2026-08-10.md`](./ml_oos_02_automatic_block_length_vet_2026-08-10.md).
The report supports `--higher-grid --automatic-only`, which evaluates
360/504/756 total sessions without making any count a floor.

## Interpretation and operational limit

The default 100-replication command is a quick diagnostic. The acceptance law
will often reject it for excessive Monte Carlo uncertainty. A 500-replication,
200-bootstrap-resample full grid was benchmarked but intentionally interrupted
after more than seven minutes; the reference bootstrap implementation is
correctness-oriented and emits JSON only after all cells finish. A future batch
run may use:

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_acceptance.py \
  --replications 500 --bootstrap-resamples 200 --json
```

Do not lower the Monte Carlo precision criterion merely to make the interactive
command pass. Optimizing the seeded bootstrap implementation would change the
measurement stream and therefore requires an explicit contract-version review.

## Objective status

- Candidate acceptance schema and fail-closed evaluator: implemented.
- Wider fixed-challenger DGP and method-tuning grid: implemented.
- Learned linear/tree acceptance: still blocked; current fitted study has no
  nested tuning algorithm and cannot share the fixed-challenger law.
- Multiplicity correction: not implemented; search remains ineligible.
- Automatic block-length selection: implemented as measurement-only; no method
  adoption.
- Numerical candidate law: explicit but still requires human vetting.
- Confirmation registry and Task 06: unchanged and blocked.
