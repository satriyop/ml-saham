# ML-OOS-02 — synthetic session-estimand calibration (2026-08-10)

**Status: MEASUREMENT SHIPPED / NO METHOD OR FLOOR SELECTED**

Executable study:

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_calibration.py
PYTHONPATH=src python scripts/report_ml_oos_02_calibration.py --json
PYTHONPATH=src python scripts/report_ml_oos_02_fit_calibration.py
PYTHONPATH=src python scripts/report_ml_oos_02_fit_calibration.py --json
```

Measurement contract: `policy_confirmation_calibration.synthetic.v2`.
Fit-pipeline measurement contract:
`policy_confirmation_fit_calibration.synthetic.v1`.
Evidence grade: `MEASUREMENT_ONLY`.

Version 2 is a clean break from the original measurement payload: it separates
one-sided false-superiority (`lower > 0`) from diagnostic two-sided false
rejection (the interval excludes zero in either direction). The earlier v1
illustrative table reported the two-sided diagnostic rate and remains
historical measurement evidence; candidate superiority acceptance uses only
the v2 one-sided rate.

## What it measures

The harness creates synthetic ordered session-level challenger-minus-production
estimands and evaluates candidate interval operating characteristics on the
exact test-session union emitted by the shipped three-fold, 20-session-embargo
geometry. A configured final tail is excluded from the fold region and never
opened by the study.

The scenario grid makes these dimensions explicit:

- total sessions and final-tail length;
- AR(1) dependence and periodic heteroskedasticity;
- regime-level mean changes;
- names per session, name missingness, and the minimum valid-name rule;
- fixed, learned-linear, and learned-tree class labels;
- one preregistered challenger versus unadjusted best-of-five selection.

Candidate methods are a stationary-bootstrap percentile interval with explicit
block length 5 and a Newey-West normal interval with explicit lag 5. These
settings are stress inputs, not adopted policy.

## Reproducibility

- Default seed: `20260810`.
- Scenario and method RNG streams derive from stable SHA-256 identity parts;
  changing execution order does not silently change another scenario's stream.
- Every stochastic setting and scenario input is emitted in JSON.
- No current time, network, upstream SQLite, live cohort, or live outcome is
  read.

## Illustrative stress evidence

The higher-replication check used:

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_calibration.py \
  --replications 300 --bootstrap-resamples 300 --json
```

At 84 total sessions with a 20-session untouched tail, the fold region forms
two folds and contributes 32 synthetic OOS sessions. Selected results:

| Scenario | Stationary bootstrap | Newey-West |
|---|---:|---:|
| Dependent null false-positive rate | 18.3% | 15.3% |
| Dependent alternative directional detection (`effect=0.05`) | 24.3% | 20.3% |
| Unadjusted best-of-five null false-positive rate | 28.3% | 23.3% |
| Thin/missing null false-positive rate | 17.7% | 13.8% |
| Thin/missing mean observed sessions | 23.3 / 32 | 23.4 / 32 |

These scenario-specific results are not estimates of market performance. They
show that neither candidate setting delivered nominal 95% behavior in the
short dependent scenarios, and that unadjusted search materially increased
selection bias and false positives. More sessions improved some stress cells
but did not make one method uniformly calibrated across dependence, search,
missingness, and regime scenarios.

## Exact shipped-fit follow-up

The companion harness builds synthetic 45-name panels whose known reference
score is the data-generating ranking signal, then exercises the shipped ridge,
elastic-net, and LightGBM fit/predict functions separately inside every real
`accum_path_v1` fold. A second, deliberately strong alternative rotates the
signal weights by `0.60` so the harness measures directional detection as well
as false superiority under the reference null.

Default evidence used 30 replications and 100 bootstrap resamples. All three
fit pipelines completed every fold at the 84/120/180 total-session grid. Both
candidate intervals made zero false-superiority claims under this particular
reference null. Directional detection under the rotated alternative was:

| Total sessions / synthetic OOS sessions | Ridge | Elastic net | LightGBM stationary / HAC |
|---:|---:|---:|---:|
| 84 / 32 | 100% | 100% | 43.3% / 40.0% |
| 120 / 75 | 100% | 100% | 63.3% / 63.3% |
| 180 / 120 | 100% | 100% | 96.7% / 96.7% |

This is capacity-sensitive evidence: the tree pipeline needed substantially
more synthetic OOS depth than the regularized linear pipelines in this one
alternative. It is not a floor recommendation. The rotation, noise, feature
persistence, cross-sectional width, and model hyperparameters define an easy
or hard problem and require a wider preregistered stress grid before adoption.

## Fail-closed limits

- The base harness simulates the already-formed session estimand. Its learned
  labels therefore emit `fit_capacity_mode=FIT_CAPACITY_NOT_MODELED`; only the
  separate fit-pipeline harness exercises learned models.
- The fit-pipeline harness uses the current fixed ridge, elastic-net, and
  LightGBM parameters. It does not search hyperparameters or validate a future
  nested tuning procedure.
- Its local policy fixture and synthetic reference score are explicitly not a
  verified production snapshot or production baseline.
- Best-of-search is intentionally unadjusted. The reported inflation is a
  warning measurement, not an SPA or Romano-Wolf implementation.
- Missing sessions keep their calendar positions. The candidate HAC calculation
  uses finite lag pairs and may report partial invalid replications rather than
  silently forcing a variance estimate.
- A stationary bootstrap remains unsuitable as authority when a scenario has
  an unhandled regime break merely because it emits a numerical interval.

## Objective conclusion

The study rejects immediate adoption of block-5 stationary bootstrap, lag-5
Newey-West, the 84/120/180-session grid as policy floors, and unadjusted
best-of-family selection. `POLICY_CONFIRMATION_CONTRACTS` must remain empty.

The next statistical implementation, if pursued, is a wider predeclared DGP
and method-tuning grid with an operating-characteristic acceptance law. If any
challenger adds hyperparameter or feature selection, that complete algorithm
must also be simulated in an inner ordered/purged loop. The work must remain
synthetic or use permanently exploratory material; it must not tune against
the future confirmation cohort.

Implemented candidate follow-up (not adopted):
[`ml_oos_02_candidate_acceptance_law_2026-08-10.md`](./ml_oos_02_candidate_acceptance_law_2026-08-10.md).
