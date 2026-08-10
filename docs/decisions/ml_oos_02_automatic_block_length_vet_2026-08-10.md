# ML-OOS-02 — automatic stationary-bootstrap block-length vet (2026-08-10)

**Status: IMPLEMENTED AND MEASURED / NOT ADOPTED**

## Scope and authority

This slice implements a corrected Politis-White/Patton-Politis-White plug-in
selector for the stationary bootstrap of the session-level sample mean. It is
identified as `politis_white_patton.stationary_mean.v1` and is available only
inside synthetic `MEASUREMENT_ONLY` calibration.

It does not inspect live outcomes, modify `accum_path_v1`, select a session
floor, register `POLICY_CONFIRMATION_CONTRACTS`, or unblock Task 06.

## Vetted algorithm

For one finite ordered session series of length `n`, the selector:

1. centers the series and rejects fewer than 10 sessions, non-finite calendar
   positions, and degenerate variance;
2. finds the first run of `K_n=max(5, ceil(log10(n)))` autocorrelations inside
   `±2*sqrt(log10(n)/n)`;
3. uses twice that cutoff, capped by `ceil(sqrt(n))+K_n`, as the flat-top lag;
4. estimates the weighted autocovariance quantities `G` and long-run variance;
5. uses the corrected stationary-bootstrap variance constant
   `D_SB=2*(long_run_variance)^2`;
6. computes the plug-in block length, rounds upward, and caps it at
   `ceil(min(3*sqrt(n), n/3))`.

The corrected variance constant follows Patton, Politis, and White's correction
([paper](https://doi.org/10.1080/07474930802459016)) to Politis and White's
automatic selector
([paper](https://www.math.ucsd.edu/~politis/SBblock-revER.pdf)). The upward
integer rounding and minimum-10-session guard are explicit candidate
engineering choices, not claims from those papers.

## Independent numerical cross-check

The raw selector output was compared with `arch.bootstrap.optimal_block_length`
on fixed seeded vectors:

| Series | Raw stationary block, local | Raw stationary block, arch | Selected integer |
|---|---:|---:|---:|
| seeded IID, n=240 | 1.5144375859 | 1.5144375859 | 2 |
| AR(1)=0.85 over same innovations | 9.5859412179 | 9.5859412179 | 10 |

This cross-check verifies the corrected formula for the exercised range. The
local selector remains the executable implementation; `arch` is not called at
runtime and no new dependency was added.

## Fail-closed behavior

- Missing/non-finite session positions are not deleted or compressed. The
  selector returns `NONFINITE_CALENDAR_SERIES`; calibration becomes partial or
  `METHOD_NOT_MEASURABLE`.
- Constant series return `DEGENERATE_VARIANCE`.
- Unusable corrected long-run variance returns
  `DEGENERATE_LONG_RUN_VARIANCE`.
- Explicit regime-break cells remain `BLOCKED_REGIME`; an automatic block does
  not establish stationarity.
- Every successful calibration result records mean/min/max selected block
  length. The selector ID is serialized only for the automatic method, so
  existing explicit/HAC fit-calibration payloads are not silently widened.

## Higher-session grid

Executable command:

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_acceptance.py \
  --higher-grid --automatic-only --replications 100 \
  --bootstrap-resamples 50 --json
```

Grid: 360, 504, and 756 total sessions, each retaining the 20-session untouched
tail and exact shipped three-fold/20-session-embargo geometry.

Selected 100-replication evidence:

| Sessions | Stress | Mean block (min-max) | Null coverage lower | Null false-superiority upper | Alt coverage lower | Power lower | Width/effect |
|---:|---|---:|---:|---:|---:|---:|---:|
| 360 | moderate | 5.72 / 5.61 (2-17) | 0.779 | 0.137 | 0.802 | 0.553 | 1.722 |
| 504 | moderate | 6.28 / 6.80 (4-24) | 0.767 | 0.137 | 0.767 | 0.522 | 1.529 |
| 756 | moderate | 7.48 / 7.52 (4-18) | 0.863 | 0.070 | 0.814 | 0.779 | 1.232 |
| 360 | strong dependence | 10.49 / 10.75 (6-27) | 0.756 | 0.125 | 0.733 | 0.228 | 3.951 |
| 504 | strong dependence | 12.40 / 13.39 (8-27) | 0.790 | 0.162 | 0.802 | 0.167 | 3.469 |
| 756 | strong dependence | 15.06 / 14.75 (9-34) | 0.745 | 0.150 | 0.689 | 0.255 | 2.800 |

The two block means shown in each row are null/alternative, which use separate
seeded synthetic paths. All candidates passed **0 of 6** required stationary
cells at each calendar. Thin/missing null and alternative cells were
unmeasurable in all 100 replications because the selector correctly refused to
erase calendar gaps. Aggregate calibration and acceptance artifacts preserve
the typed selector-failure counts, so this reason is not collapsed into the
generic `METHOD_NOT_MEASURABLE` status.

## Objective conclusion

The selector adapts in the expected direction—stronger dependence selects
longer blocks—but it does not repair percentile-interval undercoverage,
low power under strong dependence, or gapped-session semantics. Therefore:

- no automatic method is adopted;
- 360/504/756 are not floors;
- no historical result is upgraded;
- the confirmation registry remains empty and Task 06 remains blocked.

The next methodology question is not “which of these calendars wins.” It is
whether to vet a different interval construction (for example, studentized or
calibrated bootstrap) and an explicit missing-calendar law while preserving the
same predeclared acceptance criteria.
