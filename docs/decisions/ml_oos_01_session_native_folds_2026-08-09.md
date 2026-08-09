# ML-OOS-01 — session-native purged folds (2026-08-09)

## Bug

`time_purged_folds` fell back to a **row-index 70/30** split when
`len(unique dates) < n_folds + 1`. That allowed:

1. Train and test to share the same session (e.g. 100 rows / 1 date).
2. Zero realized embargo when the calendar had only a few dates (e.g. 90 rows /
   3 dates under `embargo_sessions=20`).

Diagnostic validity also fell back to a **full-sample** train=test fold.

## Fix (methodology-preserving)

- Remove row-based and full-sample fallbacks.
- Construct folds only from **unique ordered panel sessions**.
- Require full protocol embargo gap (unique sessions between last train and
  first test).
- Return `[]` → callers emit **`BLOCKED_DATA`** when geometry cannot be proven.
- Report `n_train_sessions`, `n_test_sessions`, `embargo_sessions_actual` on
  fold metrics.

**Unchanged:** `accum_path_v1` / `pre_open_session_v1` thresholds
(`n_folds`, `embargo_sessions`, `min_n_*`, `min_folds_for_verdict`).

## Protocol identity

This is a **correctness fix** of fold construction against the existing
protocol contract, not a new success law or threshold change. **No
`accum_path_v2` protocol ID** is introduced.

Existing challenge / diagnostic **artifacts written under the buggy splitter
are historical**. Re-run challenges to obtain session-honest folds; do not
treat pre-fix single-fold artifacts as promotion evidence.

## Enforce historical via promote artifact schema v5 (follow-up)

Documentation alone did not block reopen. Promote-evidence schema is now
**v5** with material ``fold_geometry_contract_id=session_native_purged.v1``
sealed into ``content_digest``. Schema **v4 and earlier** are
display-only / not promote-reopen eligible. Per-fold session geometry fields
are required and type-checked on reopen.

## Related

Session floors (ML-OOS-02): `docs/decisions/ml_oos_02_session_floors_2026-08-09.md`.

## Still deferred

Fold count, embargo value, daily IC, holdout size, multiplicity,
single-fold LOSE→INCONCLUSIVE policy.
