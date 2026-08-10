# ML-OOS-02 — live ACCUM cohort feasibility (2026-08-10)

**Status: NOT READY — GEOMETRY**
**Scope: read-only feasibility audit; no IC/verdict threshold selection.**

Executable audit:

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_feasibility.py
PYTHONPATH=src python scripts/report_ml_oos_02_feasibility.py --json
```

Audit contract: `policy_confirmation_feasibility.accum.v1`.

## Authority and non-authority

- Source: canonical read-only `ai-saham` SQLite connector (`mode=ro`).
- Population: each explicit ACCUM `compatibility_id` independently; no pooling
  and no largest/latest selection.
- Policy/application path: `screener.accum.score_weights` through shipped
  production snapshot verification and panel builder.
- Protocol: `accum_path_v1`, primary H10, 3 folds, embargo 20 sessions,
  `min_folds_for_verdict=2`.
- Outcomes/IC were **not inspected**.
- This audit does **not** authorize `POLICY_GRADE`, promotion, a session floor,
  a holdout length, an uncertainty method, or a multiplicity rule.

## Live evidence

Explicit cohort:

```text
sha256:355e5b59600dbdc9f762f7b373e8879b7cda9a1e55e18bd590461315cfe1e091
```

| Measure | Current evidence |
|---|---:|
| Observation rows | 1,035 |
| Extractable / unique ticker-session rows | 1,035 / 1,035 |
| Raw sessions / tickers | 23 / 45 |
| Raw session range | 2026-07-08 .. 2026-08-07 |
| Names per raw session | min/median/max = 45/45/45 |
| Non-finite components | 0 |
| Primary-H10 eligible rows | 585 |
| Primary-H10 eligible sessions | 13 |
| Primary-H10 range | 2026-07-08 .. 2026-07-24 |
| Rows excluded for unavailable H10 | 450 (10 sessions × 45 names) |
| H20 available within H10 panel | 135 rows (3 sessions) |
| Valid post-embargo folds | **0** |

The 1,035 row count is not 1,035 independent time samples. The panel grain is
ticker/session and currently contains only 23 raw sessions; after H10 label
maturity it contains 13 eligible sessions.

With the shipped structural geometry, the first one-fold calendar is 28
eligible sessions and the first calendar capable of two folds is 44 eligible
sessions. Those are geometry facts, **not** policy-grade ML sample floors.

All tested holdout candidates (5/10/20/40 sessions) currently preserve zero
folds. Fixed and learned challengers are both `NOT_READY_GEOMETRY`. Learned
challengers additionally remain blocked on the still-open learned-model session
floor and uncertainty design even after geometry eventually becomes possible.

`screener.accum.hard_filters` remains separately `BLOCKED_POLICY`: its adapter
lacks counterfactual conformance evidence. It must not inherit readiness from
the score-weights panel.

## Read-only tripwire

Before/after audit evidence was identical:

| Field | Value |
|---|---:|
| DB size | 1,341,685,760 bytes |
| DB mtime ns | 1,786,201,897,042,044,860 |
| inode | 154,145,187 |
| page count | 327,560 |
| freelist count | 210,755 |
| schema version | 220 |
| `learning_observations` rows | 1,035 |
| `learning_outcome_labels` rows | 1,620 |
| `learning_policy_snapshots` rows | 9 |
| `candles` rows | 83,917 |

The executable audit repeats this tripwire and refuses to return a mixed-state
report if any recorded field changes during the run.

## Follow-up gate

Do not proceed to policy-grade threshold selection yet. Re-run this audit as
the cohort grows. Method selection may start separately, but the current OOS
outcomes must not be used both to choose the method and to claim confirmation.
