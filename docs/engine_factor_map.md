# Engine → tables → challenge slugs

Living map between **`ai-saham` engines / evidence**, SQLite surfaces, and **`ml-saham` challenge** factors.  
Product: [ADR-001](./adr/ADR-001-challenge-first-product-axis.md) · Challenge SSOT: `src/ml_saham/eval/challenge.py` · Curriculum: `src/ml_saham/chapters/registry.py`

**Rule:** new `ai-saham` factor/evidence → decide: (a) existing slug covers it, (b) extend compare, or (c) new challenge slug (+ optional learning `explore`).  
Do **not** invent curriculum for pure plumbing.

---

## Engines (ai-saham)

| Engine / surface | Role | Primary tables / artifacts | Challenge group | Challenge slugs (today) |
|------------------|------|----------------------------|-----------------|-------------------------|
| **Screener (accum)** | Rank accumulation candidates | `broker_summaries`, `foreign_flow_points`, `broker_daily_flow`, `bandar_detector`, `learning_observations` (ACCUM…), `candles` | `screener` | **ADR-002 policy:** `screener.accum.score_weights` (`challenge run`). Legacy chapter slugs: `broker-flow`, `broker-accumulation`, `bandar-detector`, `accum-policy`, `accum-macro`, `accum-deep` |
| **Screener (pre-open)** | Opening auction / IEV rank | `iev_snapshots` / `iev_snapshot_history`, `learning_observations` (PRE_OPEN…), `candles` | `screener` | **ADR-002 policy:** `screener.pre_open.iev_rank` (`challenge run`, protocol `pre_open_session_v1`). Legacy chapter slugs: `pre-open-rank`, `pre-open-heuristic`, `pre-open-direction`, `pre-open-participation`, `pre-open-auction`, `pre-open-macro` |
| **SignalEngine** | Alpha / evidence groups → raw score | observations + fundamentals + flow fingerprints | `signal_engine` | `meta-ensemble`, `factor-score`, `relative-strength`, `ichimoku-cloud`, `pattern-fail`, `earnings-surprise`, `financial-quality`, `forward-valuation`, `analyst-consensus`, `seasonality-drift` |
| **RiskEngine** | Gates, sizing, block/allow | notations, financials, vol fingerprints in observations | `risk_engine` | `volatility-sizing`, `portfolio-small`, `special-monitoring`, `financial-distress` |
| **MarketContextEngine** | Regime / breadth / macro inputs | `market_context_snapshots`, `regime_observations`, `candles` (IHSG) | `market_context` | `market-regime`, `sector-breadth`, `nowcasting`, `microstructure-impact` |
| **Data plane / DQ** | Trust of caches & observations | all tiers + `learning_observations` | `other_aspects` | **`data-integrity`** (new) |
| Supporting labs | Hygiene / honesty | various | `other_aspects` | `cluster-peers`, `broker-network`, `volume-anomaly`, `walk-forward`, `research-pipeline`, `rl-sandbox`, `corp-events`, `survival-analysis` |

Signal evidence groups commonly seen in payloads (challenge baselines):

| Evidence / group | ai-saham concept | Closest challenge slug |
|------------------|------------------|------------------------|
| `institutional_flow` / flow confirmation | Flow sleeve | `broker-flow`, `meta-ensemble` |
| `setup_quality` | Setup / TA sleeve | `pattern-fail`, `ichimoku-cloud`, `volatility-squeeze` |
| `sector_context` (peer L2a) | Peer relative sector | `sector-breadth`, `cluster-peers` |
| `company_quality_context` | Quality sleeve | `financial-quality`, `earnings-quality` |
| Risk gates (bandar, liquidity, freefloat, fundamental) | RiskEngine gates | `special-monitoring`, `bandar-detector`, `financial-distress` |
| Volatility size multiplier | Risk sizing | `volatility-sizing` |
| Accum score policy components | Screener policy | `accum-policy` → `accum-macro` → `accum-deep` |

---

## Curriculum coverage gaps (from ai-saham factors)

Factors / evidence that exist or are growing in **ai-saham** but are **thin or missing** as dedicated challenge/curriculum units:

| ai-saham factor / evidence | Status in ml-saham | Recommendation |
|----------------------------|--------------------|----------------|
| **Sector macro context** (ADR-053, `SectorMacroContextEvidence`, routed macros per sector group) | **No dedicated slug.** Peer `sector-breadth` ≠ macro drivers (oil, rates, FX per sector). DIAGNOSTIC in v1 on ai-saham. | **New challenge slug** when scoring starts using it, or earlier as diagnostic compare: `sector-macro` under `market_context`. Optional ID `explore` later. |
| **Sector context (peer-relative)** (`SectorContextEvidence`: peer breadth/returns) | Partially via `sector-breadth` / `cluster-peers` | Extend `sector-breadth` compare with peer-panel metrics; no new chapter unless product needs it |
| **Company quality context** (dedicated VO) | Partial via `financial-quality` / F-score | Keep under signal quality; deepdive only |
| **Setup phase / readiness / swing setup lens** | Not a first-class challenge | Park under pattern-fail / walk-forward deepdive until labels are dense |
| **Source availability / field contracts / reconciliation** (DQ use cases) | **data-integrity** + doctor | Prefer command/`data-integrity`, not a long curriculum chapter |
| **Sentiment pipeline** (live headlines) | `headline-tone` synthetic OK | Real table path when soft headlines hard-fail policy changes |
| **Strategy plugins** (bb-squeeze, rs-momentum, ichimoku, …) | Partial (`volatility-squeeze`, `relative-strength`, `ichimoku-cloud`) | Map 1:1 only when strategy is an engine input; else deepdive |
| **Insider selling flags** (signal config penalties) | `insider` chapter exists | Ensure challenge map includes `insider` if used as gate input (currently not in ENGINE_FACTORS) |
| **Corporate action event risk** | `corp-events` | Covered |
| **Policy rate / macro calendar events** | Thin | Bundle into future `sector-macro` or market-context lab |
| **Opening track / paper outcomes** | Pre-open slugs | Covered by pre-open suite |

### Insider gap note

`insider` is a **curriculum** chapter (v1.1) but **not** in `ENGINE_FACTORS`. If SignalEngine penalties use insider heavily, add `insider` to `signal_engine` or `risk_engine` when you want batch audits.

---

## Decision checklist (new ai-saham factor)

1. Which **engine** owns it?  
2. Which **tables / observation fields**?  
3. Existing **challenge slug** that already measures the same decision?  
4. If no → new slug under the right `ENGINE_FACTORS` group + `run_compare`.  
5. Learning `explore` only if the problem is non-obvious (ID); challenge report always **English**.

---

## Related commands

| Command | Role |
|---------|------|
| `ml-saham doctor` / `doctor --deep` | Data coverage + integrity gates |
| `ml-saham vet` | English data-integrity audit (challenge factor) |
| `ml-saham challenge …` | Engine batch audit |
| `ml-saham compare <slug> …` | Single-factor vs ai-saham-style baseline |
