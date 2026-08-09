# ML-OOS-02 — structural geometry minima vs policy-grade floors (open)

**Status: INCOMPLETE** — geometry simulation and authority separation only.
Policy-grade minimum train/test sessions are **not** selected yet.

## What shipped (structural only)

Module: `ml_saham.challenge.fold_geometry_sim`.

1. Simulate the same session chunking / full-embargo rules as `time_purged_folds`.
2. **Structural geometry minima** = min train/test unique-session counts on the
   first calendar that forms ≥1 fold.
3. Multi-fold readiness (≥ `min_folds_for_verdict`) is **informational only**.

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
requirements (model complexity, power, dependence, IC uncertainty, regime
coverage are ignored by the simulator).

## Authority separation (required correction)

Geometry-valid folds must not be read as policy-grade promote evidence.

- Challenge runs stay **runnable** under `accum_path_v1` / `pre_open_session_v1`.
- Sealed artifacts stamp `evidence_grade=EXPLORATORY`.
- **Policy-grade promote / task-06 validation fails closed** unless:
  - `evidence_grade=POLICY_GRADE`, and
  - `policy_confirmation_contract_id` is a **registered** confirmation contract.

`POLICY_CONFIRMATION_CONTRACTS` is currently **empty**. No path can claim
policy-grade confirmation until the design study lands a contract id.

## Real ML-OOS-02 design study (still open)

Separate work, not free constants in code:

- fixed challengers (e.g. equal_sleeves) vs learned ridge/LightGBM;
- policy-grade min train/test **sessions**;
- daily/session-aware IC + uncertainty;
- final untouched holdout;
- multiple-challenger selection / multiplicity;
- regime coverage.

## Explicit non-goals for this slice

- Guessing statistical thresholds in Protocol
- Marking ML-OOS-02 complete
- Auto-promoting exploratory WIN into ai-saham
