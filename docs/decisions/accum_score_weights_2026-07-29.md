# Decision memo — accum score weights (Path A)

**Date:** 2026-07-29  
**Policy:** `screener.accum.score_weights`  
**Policy hash:** `ac01f2a36342191f`  
**Protocol:** `accum_path_v1` (primary **H=10**, report 3 / 10 / 20)  
**DB:** maintainer `ai-saham` SQLite (`~/dev/ai-saham/data/db/data.db`, read-only)  
**Product rule:** decision support only — **never auto-promote** into ai-saham config.

Related: [challenge operator note](../challenge_accum_score_weights.md) · [factor track](../challenge_factor_validity.md) · [ADR-002](../adr/ADR-002-ideal-challenge-system.md)

---

## Executive decision

| Item | Decision |
|------|----------|
| **Production weights** | **KEEP as baseline** — real positive rank IC @ H=10; not empty noise |
| **Equal sleeves** | **Do not switch** — `INCONCLUSIVE` (within win margin) |
| **Ridge reweight** | **Reject** — `LOSE` hard on OOS fold |
| **Promotion to ai-saham** | **NO** |
| **Controlled experiment?** | Optional later only: lower `vwap_discount` and/or rebalance toward `consistency` + `rsi_headroom` — **after** more folds/history |

---

## Sample & coverage (limits first)

| Metric | Value |
|--------|--------|
| Panel rows (primary H=10 labeled) | **1 350** |
| Unique tickers | **45** |
| Session dates | **2026-06-02 → 2026-07-14** (**30** dates) |
| Dropped (no H=10 excess) | **450** rows |
| Protocol target folds | 3 (embargo 20 sessions) |
| **Folds formed** | **1** (calendar too short vs embargo) |
| OOS fold window | 2026-07-02 → 2026-07-14 · n_test=405 · n_train=45 |
| H=3 labeled | 100% of panel rows |
| H=10 labeled | 100% of panel rows |
| H=20 labeled | **66.7%** overall; **0% on OOS fold dates** (forward path not complete) |

**Why only one fold:** ~30 unique sessions with `embargo_sessions=20` cannot support three purged folds. Challenge status rules still apply; multi-fold agreement is **not** available yet.

**Why H=20 shows n/a on the official tournament table:** OOS dates are the most recent; 20-session forward excess is not available there. Full-panel diagnostics still see H=20 on earlier June dates (see § Supporting).

---

## Policy tournament (official)

Commands (2026-07-29 Path A run):

```bash
export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db
ml-saham challenge run screener.accum.score_weights --against equal_sleeves
ml-saham challenge run screener.accum.score_weights --against ridge_reweight
```

### Production vs equal_sleeves → **INCONCLUSIVE**

| Horizon | production IC | equal_sleeves IC |
|---------|---------------|------------------|
| H=3 | +0.1299 | +0.1114 |
| **H=10 (primary)** | **+0.1707** | **+0.1633** |
| H=20 (OOS) | n/a | n/a |

- Edge is tiny (+0.007 IC) and **inside** protocol `win_margin` (0.01).  
- **Do not** adopt equal weights.

### Production vs ridge_reweight → **LOSE** (for ridge)

| Horizon | production IC | ridge_reweight IC |
|---------|---------------|-------------------|
| H=3 | +0.1299 | −0.2142 |
| **H=10 (primary)** | **+0.1707** | **−0.3548** |
| H=20 (OOS) | n/a | n/a |

- Train size for ridge on the only fold is **n_train=45** — not credible for 5-factor reweight.  
- **Reject** ridge as a production alternative on this sample.

### Production weight snapshot (baseline)

| Sleeve | Weight |
|--------|--------|
| consistency | 33.3 |
| streak | 25.0 |
| vwap_discount | 16.7 |
| rsi_headroom | 8.3 |
| foreign_flow_ratio | 8.3 |

(Disabled / excluded from weighted sleeves: `bb_squeeze`, `bci` — not in this validity track.)

---

## Factor validity (official)

```bash
ml-saham challenge factor screener.accum.score_weights --all
# digs
ml-saham challenge factor screener.accum.score_weights --factor consistency
ml-saham challenge factor screener.accum.score_weights --factor rsi_headroom
ml-saham challenge factor screener.accum.score_weights --factor vwap_discount
ml-saham challenge factor screener.accum.score_weights --factor streak
ml-saham challenge factor screener.accum.score_weights --factor foreign_flow_ratio
```

Primary @ H=10 (mean OOS fold metrics):

| Factor | w | Univariate IC | Δ IC (full − drop) | Fold agree Δ>0 | Verdict |
|--------|---|---------------|--------------------|----------------|---------|
| **consistency** | 33.3 | **+0.169** | **+0.137** | 100% | **KEEP** |
| **rsi_headroom** | 8.3 | **+0.222** | **+0.021** | 100% | **KEEP** |
| **vwap_discount** | 16.7 | +0.011 | −0.003 | 0% | **DEMOTE** |
| streak | 25.0 | −0.024 | −0.021 | 0% | **INCONCLUSIVE** |
| foreign_flow_ratio | 8.3 | +0.063 | −0.011 | 0% | **INCONCLUSIVE** |

### Dig notes (OOS fold)

- **consistency:** Dropping it collapses H=10 full IC **0.171 → 0.034**. Core sleeve; production weight is justified on this window.  
- **rsi_headroom:** Strongest univariate IC; ablation help is smaller but positive. Low weight (8.3) vs signal quality → **candidate to upweight later**, not a ship decision now.  
- **vwap_discount:** Full IC slightly **better** when dropped (0.171 → 0.173). Weak uni IC. **First demote candidate** for a future controlled experiment — **not drop** and **not config change today**.  
- **streak:** Negative uni + negative ablation on OOS; heavy weight (25). Flag for re-check with more folds; **do not demote/drop on one fold alone**.  
- **foreign_flow_ratio:** Sparse nonzero (~28% of rows); mixed uni vs ablation. **Need data**.

---

## Supporting diagnostics (not protocol win/lose)

These use **all 30 panel dates** (mean cross-sectional daily rank IC). They are **not** the official tournament status; they stress-test whether the short OOS fold is an outlier.

| Score | Mean daily IC @ H=10 | Days IC>0 | Pooled IC @ H=10 | Mean daily IC @ H=20 |
|-------|----------------------|-----------|------------------|----------------------|
| production | **+0.104** | **73%** (22/30) | +0.092 | +0.057 (20 days; only earlier dates) |
| equal_sleeves | +0.097 | 70% | +0.101 | (similar order) |

Interpretation:

- Production is **positive more days than not** over the full panel, not only on the July OOS slice.  
- Equal is close again — consistent with `INCONCLUSIVE`.  
- H=20 signal is weaker and only measurable where labels exist (pre-OOS dates).

**Tension to record:** full-sample daily ablation ranks **vwap** more helpful than the July OOS fold ablation. Official factor verdict remains **DEMOTE** (fold protocol). Treat demote as **“watch / experiment candidate”**, not “proven useless.”

Exports: `/tmp/ml-saham-path-a/extra_evidence.json` (local, not committed).

---

## Human checklist (ai-saham)

- [x] Keep production `AccumScorePolicy` weights as live baseline  
- [ ] **Do not** switch to equal sleeves  
- [ ] **Do not** ship ridge-learned weights  
- [ ] **Do not** remove factors from production on this memo alone  
- [ ] Optional research queue (human-only, later):  
  - re-run when panel has **≥ ~60+ sessions** so 3 purged folds form  
  - experiment: lower `vwap_discount` weight  
  - experiment: modest lift `rsi_headroom` / protect `consistency`  
  - re-audit `streak` (high weight, weak OOS)  
- [ ] Promotion to ai-saham YAML/code: **NO**

---

## Artifact pointers

| Kind | Path |
|------|------|
| Path A JSON/MD pack | `/tmp/ml-saham-path-a/` (`run_equal`, `run_ridge`, `factors_all`, per-factor digs) |
| Challenge artifacts (local, gitignored) | `artifacts/challenge/screener.accum.score_weights/20260729_*` |
| Factor batch artifact | `artifacts/challenge/factor/screener.accum.score_weights/_all/20260729_165150` |
| Extra diagnostics | `/tmp/ml-saham-path-a/extra_evidence.json` |

---

## One-line summary

> **Keep production accum weights; reject ridge; do not switch to equal; KEEP consistency + rsi_headroom; watch DEMOTE vwap and weak streak/flow — no ai-saham promotion until more folds and longer history.**
