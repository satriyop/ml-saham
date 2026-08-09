# ML-OOS-02 — policy confirmation design study (vet, not adopt)

**Status: OPEN / IN PROGRESS** — design machinery and decision framework only.  
**No policy-grade thresholds are written into Protocol.**

## Product question

What must a **policy-grade** confirmation contract bind before an exploratory
challenge result may be treated as confirmatory promote evidence?

Related authority (already shipped):

- `evidence_grade=EXPLORATORY` on current protocols
- empty `POLICY_CONFIRMATION_CONTRACTS` registry
- structural `geometry_min_*_sessions` ≠ sample floors
- `verdict_semantics.symmetric_directional.v1`

## Draft contract identity (not registered)

```text
policy_confirmation.accum_oos.design.v0
```

Module: `ml_saham.challenge.policy_confirmation_design`.  
Script: `scripts/report_ml_oos_02_design.py`.

This draft id is **explicitly excluded** from promote eligibility.

## Required axes (must be frozen before registration)

| Axis | Role | Status |
|---|---|---|
| `challenger_class` | fixed vs learned sample pressure | profiles described |
| `geometry_minima_ref` | structural baseline from sim | measured |
| `policy_min_train_sessions` | policy-grade floor | **OPEN — not selected** |
| `policy_min_test_sessions` | policy-grade floor | **OPEN — not selected** |
| `session_ic_method` | mean daily IC vs pooled | measurement ready; method **OPEN** |
| `ic_uncertainty_method` | session dependence / CI | **OPEN** |
| `final_holdout_sessions` | untouched tail after folds | placement geometry ready; length **OPEN** |
| `multiplicity_rule` | multi-challenger search discipline | bookkeeping ready; rule **OPEN** |
| `min_folds_for_verdict` | already product (symmetric) | shipped |
| `verdict_semantics_contract_id` | already product | shipped |
| `fold_geometry_contract_id` | already product | shipped |

## Measurement shipped (no thresholds adopted)

### 1. Geometry depth profile

`build_geometry_depth_profile` / existing `fold_geometry_sim` report train/test
session depths vs calendar length under live chunking + embargo.

Structural minima (reference only):

| Protocol knobs | Structural geometry min train / test |
|---|---|
| n_folds=3, embargo=20, min_folds_for_verdict=2 | 1 / 7 |
| n_folds=3, embargo=1, min_folds_for_verdict=2 | 1 / 1 |

### 2. Challenger class sample pressure

Descriptive profiles:

- **fixed** (`equal_sleeves`, `production`, `gate_off`): 0 fit parameters
- **learned linear** (`ridge_reweight`, …): ~K sleeves/factors
- **learned trees** (`lgbm_reweight`): path-dependent capacity

`sessions_per_parameter` is a **descriptor**, not a floor selector.

### 3. Session-aware IC

`session_rank_ics` + `summarize_session_ics` produce:

- per-session rank IC
- mean / median / dispersion of session ICs
- fraction of sessions with IC > 0
- optional pooled rank IC

**Explicitly not chosen:** bootstrap, block-bootstrap, Newey–West, or any
product significance threshold.

### 4. Final untouched holdout

`holdout_geometry_candidate` / sweep: for a *candidate* holdout length H,
reserve the last H sessions and form folds only on the prefix.

Reports whether holdout sits strictly after all fold tests. **H not selected.**

### 5. Multiplicity

`multiplicity_search_record` forces an explicit challenger search set and
selection rule string. **No correction applied.**

## How to run the report

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_design.py
PYTHONPATH=src python scripts/report_ml_oos_02_design.py --json
# pre-open geometry knobs:
PYTHONPATH=src python scripts/report_ml_oos_02_design.py \
  --embargo-sessions 1 --min-folds-for-verdict 2
```

## What “done” means for policy-grade ML-OOS-02

1. Written decision for each open axis (with rationale + literature/ops basis).  
2. Versioned confirmation contract document (not just a draft id).  
3. Registry entry in `POLICY_CONFIRMATION_CONTRACTS` with exact field schema.  
4. Protocol or adapter stamp of `policy_confirmation_contract_id` only after (1–3).  
5. Promote reopen accepts that contract id and re-validates bound fields.  
6. Historical exploratory artifacts remain display-only / non-eligible.

## Explicit non-goals of this slice

- Planting `policy_min_*` into `accum_path_v1`
- Marking ML-OOS-02 complete
- Softening exploratory promote blocks
- Inventing CI / holdout / multiplicity constants in code
