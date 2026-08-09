# ML-OOS-02 — session floors from fold-geometry simulation (2026-08-09)

## Goal

Choose **minimum train/test unique-session counts** for challenge fold
acceptance without inventing free statistical parameters (IC power, daily IC,
holdout size, etc.).

## Method

Module: `ml_saham.challenge.fold_geometry_sim`.

1. Simulate the **same** session chunking and full-embargo rules as
   `time_purged_folds` (no row floors, no scores).
2. Sweep calendars `n_sessions = 1..400`.
3. **Hard floors** = min train-session and min test-session counts on the
   **first calendar that forms ≥ 1 fold**.
   - Rationale: single-fold OOS remains a valid provisional / INCONCLUSIVE path
     (`min_folds_for_win` is a WIN bar, not a fold-existence bar).
4. **Informational multi-fold readiness** = first calendar that forms
   ≥ `min_folds_for_win` folds, and the min train/test session counts on that
   calendar. Recorded for operators; **not** wired as hard floors.

No free knobs: inputs are only existing Protocol fields
(`n_folds`, `embargo_sessions`, `min_folds_for_win`).

## Results (live sim at implementation)

| Protocol | embargo | n_folds | first 1-fold n | hard min_train / min_test | multi-fold (≥2) first n | multi min_train / min_test |
|---|---:|---:|---:|---|---:|---|
| `accum_path_v1` | 20 | 3 | 28 | **1 / 7** | 44 | 2 / 11 |
| `pre_open_session_v1` | 1 | 3 | 4 | **1 / 1** | 4 | 1 / 1 |

## Wired into Protocol

```text
min_train_sessions
min_test_sessions
min_train_rows = 15   # pre-existing multi-fold row floor (unchanged)
```

Enforced in `time_purged_folds` and promote reopen
(`validate_fold_geometry_evidence`).

## Explicit non-goals (still deferred)

- Changing `n_folds`, `embargo_sessions`, or `min_folds_for_win`
- Daily IC / CI / multiplicity
- Making one-fold LOSE → INCONCLUSIVE
- Raising hard floors to multi-fold readiness mins (would reclassify many
  single-fold provisional runs as `BLOCKED_DATA`)

## Protocol identity

Still **`accum_path_v1` / `pre_open_session_v1`**. Session floors are
geometry-derived constraints on the same splitter, not a new success law.
Promote-evidence remains schema **v5** + `session_native_purged.v1`.
