# ML-OOS-02 — structural geometry minima vs policy-grade floors (open)

**Status: OPEN** — structural geometry + authority separation shipped;  
**policy-grade floors not selected.**

See the design study:

→ [`ml_oos_02_policy_confirmation_design_study_2026-08-09.md`](./ml_oos_02_policy_confirmation_design_study_2026-08-09.md)

## What shipped (structural + authority)

Module: `ml_saham.challenge.fold_geometry_sim`.

| Protocol | Structural geometry min train / test | Meaning |
|---|---|---|
| `accum_path_v1` | **1 / 7** | First geometrically possible fold block sizes |
| `pre_open_session_v1` | **1 / 1** | Same for pre-open embargo=1 |

Protocol fields:

```text
geometry_min_train_sessions
geometry_min_test_sessions
evidence_grade = EXPLORATORY
policy_confirmation_contract_id = ""   # none registered
```

These minima **prevent impossible geometry**. They are **not** ML sample
requirements.

## Authority separation

- Challenge runs stay **runnable**.
- Sealed artifacts stamp `evidence_grade=EXPLORATORY`.
- Policy-grade promote fails closed until a **registered** confirmation contract
  exists (`POLICY_CONFIRMATION_CONTRACTS` currently empty).

## Design study machinery (measurement only)

Module: `ml_saham.challenge.policy_confirmation_design`  
Script: `scripts/report_ml_oos_02_design.py`

Provides: geometry depth profiles, fixed/learned class descriptors,
session-aware IC summaries, holdout placement candidates, multiplicity
bookkeeping. **Does not adopt thresholds.**

## Explicit non-goals until confirmation design is frozen

- Guessing statistical thresholds in Protocol  
- Marking ML-OOS-02 complete  
- Auto-promoting exploratory WIN into ai-saham  
