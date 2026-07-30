# Discovery: “SOTA” vocabulary vs literature (ml-saham)

**Date:** 2026-07-29  
**Status:** Discovery / vocabulary — not a promotion decision  
**Question:** Are chapter and challenge “SOTA” models literature state-of-the-art? Should chapters cite papers?

---

## Short answer

**No.** Neither curriculum “SOTA” arms nor production **challenge** models claim peer-reviewed frontier SOTA for 2025–2026 equity/tabular ML.

| Surface | What “SOTA” / preferred arm means here | Literature SOTA? |
|---------|----------------------------------------|------------------|
| **Curriculum** (`learn explore` / `demo` / `compare`) | Preferred or default **demo path** (often LightGBM, Ridge, HRP, even Polars vs pandas) | **No** — product UI language |
| **Challenge** (`challenge run` / `engine`) | Does **not** use “SOTA” as a verdict. Baseline = frozen **production** policy; challengers = equal / ridge ablations | **No** — ablation tournament, not a model bake-off |

**Do not** treat curriculum `compare` LightGBM as authority for `screener.accum.score_weights` promotion (Path A memo + ADR-002).

---

## Chapter vs challenge (different products)

### Curriculum (e.g. Ch.37 `accum-policy`)

- **Preferred arm** (often labeled SOTA in module copy): LightGBM (or similar) on accum components.  
- **Baseline arm:** manual / DB `raw_score` / equal-style weights.  
- Language: Indonesian pedagogy; **not** ADR-002 authority.

### Production challenge (`screener.accum.score_weights`)

| Role | Identity |
|------|----------|
| Baseline | Frozen production sleeve weights (policy JSON hash) |
| Challengers | `equal_sleeves`, `ridge_reweight` |
| Metric | Rank IC (Spearman of score ranks vs return ranks) under `accum_path_v1` |

Path A (2026-07-29): keep production; equal INCONCLUSIVE; ridge LOSE; no auto-promote.  
See [decisions/accum_score_weights_2026-07-29.md](./decisions/accum_score_weights_2026-07-29.md).

Engine portfolio default against is **`equal_sleeves`**; single `challenge run` CLI default is still `ridge_reweight` — both are **challengers**, not production baselines.

---

## What is actually shipped (algorithm classes)

| Class | Role in repo | Literature note |
|-------|----------------|-----------------|
| LightGBM / GBDTs | Default tabular arm in many chapters | Strong 2017+ workhorse; still a common RankIC **baseline** in research, not a unique 2026 novelty claim |
| Ridge / Elastic Net | Linear / regularized baselines; challenge reweight | Classical regularization, not frontier |
| Isolation Forest / LOF | Anomaly chapters | Classical outlier methods |
| HRP, Piotroski, Altman, Sloan, Amihud-style, PageRank | Named classical finance/ML methods | Eponymous; cite sources in curriculum SSOT |
| Production weight sum / equal sleeves / drop ablation | Challenge scorers | **Product heuristics**, not named research models |
| Mock FinBERT / mock CNN-RNN Ichimoku / fake OFI | Some demos | **Not real models** — do not cite as implemented SOTA |

TabNet / XGBoost often appear as optional later tools, not product “frontier SOTA.”

### Literature context (class-level, not product claims)

- **Gu, Kelly, Xiu (RFS 2020)** — *Empirical Asset Pricing via Machine Learning*: trees/GBRT competitive; NNs strong nonlinear class on cross-section panels.  
- **Tabular ML (2025)** — GBDTs still the long-dominant default class; tabular foundation models (e.g. TabPFN, Nature 2025) claim strong results on small/medium tables — transfer to large, low-SNR, PIT equity panels is **not** established for this stack.  
- **Rank IC** — standard quant cross-sectional metric (Spearman of ranks), not proprietary.

There is **no** peer-reviewed paper evaluating this exact IDX broker-accumulation sleeve product; product SOTA for that stack is undefined in the literature.

---

## Informal “SOTA” gaps (inventory)

These support **vocabulary cleanup** later, not paper citations as “we ship SOTA”:

| Pattern | Example |
|---------|---------|
| Preferred arm labeled SOTA | LightGBM vs Piotroski sum; HRP vs equal weight |
| Mock / hardcoded “advanced” arm | Ichimoku CNN/RNN metrics; mock FinBERT scores |
| Non-ML labeled SOTA | Polars pipeline vs pandas loops (Ch.19) |
| Historical chapter-loop CLI | `sota_metrics` keys (retired with `challenge legacy`) |

**Phase A done (2026-07-29):** curriculum UI copy uses **Default** (preferred arm) vs **Baseline**; metrics keys prefer `against_*` / `against_metrics`. Chapter compare may still accept `sota_metrics` as a transitional alias. Discovery wording below kept for history.

---

## Citations policy

| Doc | Role |
|-----|------|
| [chapters.md](../chapters.md) | Curriculum SSOT: **method names + optional paper/journal pointers** for classical methods |
| This file | Discovery: SOTA ≠ literature; chapter vs challenge split |
| ADR-002 / challenge operator notes | Production baseline vocabulary — **no** “SOTA model” claim |

---

## One-line summary

> **“SOTA” in ml-saham is mostly curriculum demo language; challenge is production-vs-ablation under protocols. LightGBM/Ridge/etc. are solid classical tools with citable papers — not a claim of 2025–2026 frontier SOTA for IDX production scoring.**
