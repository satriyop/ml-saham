# Engine → tables → challenge policies

Living map between **`ai-saham` engines / evidence**, SQLite surfaces, and **`ml-saham` ADR-002** challenges.  
Product: [ADR-002](./adr/ADR-002-ideal-challenge-system.md) · SSOT: `src/ml_saham/challenge/` · Curriculum: `src/ml_saham/chapters/registry.py`

**Rule:** new `ai-saham` factor/evidence → decide: (a) existing **PolicySpec** covers it, (b) extend factor track / scorer, or (c) new policy (+ optional learning `explore` / `compare`).  
Do **not** invent curriculum for pure plumbing. Curriculum `compare` is **not** promotion authority.

---

## Engines (ai-saham) → product challenge

| Engine / surface | Role | Primary tables / artifacts | ADR-002 product | Curriculum labs (pedagogy only) |
|------------------|------|----------------------------|-----------------|----------------------------------|
| **Screener (accum)** | Rank accumulation candidates | `broker_summaries`, `foreign_flow_points`, `broker_daily_flow`, `bandar_detector`, `learning_observations` (ACCUM…), `candles` | `screener.accum.score_weights` (`challenge run` / engine) | `broker-flow`, `broker-accumulation`, `bandar-detector`, `accum-policy`, `accum-macro`, `accum-deep` |
| **Screener (pre-open)** | Opening auction / IEV rank | `iev_snapshots` / `iev_snapshot_history`, `learning_observations` (PRE_OPEN…), `candles` | `screener.pre_open.iev_rank` · `screener.pre_open.directional_score` | `pre-open-rank`, `pre-open-heuristic`, `pre-open-direction`, `pre-open-participation`, `pre-open-auction`, `pre-open-macro` |
| **SignalEngine** | Alpha / evidence groups → raw score | observations + fundamentals + flow fingerprints | *(no PolicySpec portfolio yet)* | `meta-ensemble`, `factor-score`, `relative-strength`, `ichimoku-cloud`, `pattern-fail`, `earnings-surprise`, `financial-quality`, `forward-valuation`, `analyst-consensus`, `seasonality-drift` |
| **RiskEngine** | Gates, sizing, block/allow | notations, financials, vol fingerprints | *(no PolicySpec portfolio yet)* | `volatility-sizing`, `portfolio-small`, `special-monitoring`, `financial-distress` |
| **MarketContextEngine** | Regime / breadth / macro inputs | `market_context_snapshots`, `regime_observations`, `candles` (IHSG) | *(no PolicySpec portfolio yet)* | `market-regime`, `sector-breadth`, `nowcasting`, `microstructure-impact` |
| **Data plane / DQ** | Trust of caches & observations | all tiers + `learning_observations` | `doctor` / `vet` | `data-integrity` |
| Supporting labs | Hygiene / honesty | various | — | `cluster-peers`, `broker-network`, `volume-anomaly`, `walk-forward`, `research-pipeline`, `rl-sandbox`, `corp-events`, `survival-analysis` |

---

## Curriculum coverage gaps (from ai-saham factors)

Factors / evidence that exist or are growing in **ai-saham** but are **thin or missing** as dedicated product policies or curriculum units:

| ai-saham factor / evidence | Status in ml-saham | Recommendation |
|----------------------------|--------------------|----------------|
| **Sector macro context** (ADR-053) | No dedicated policy | New PolicySpec or diagnostic when scoring uses it |
| **Sector context (peer-relative)** | Partial via curriculum `sector-breadth` / `cluster-peers` | Extend product later if gate input |
| **Insider selling flags** | Curriculum `insider` only | Policy/gate when heavily used in SignalEngine |
| **Corporate action event risk** | Curriculum `corp-events` | Covered for learning |
| **Opening track / paper outcomes** | Pre-open policies + curriculum pre-open suite | Product: IEV + directional |

---

## Decision checklist (new ai-saham factor)

1. Which **engine** owns it?  
2. Which **tables / observation fields**?  
3. Existing **PolicySpec** that already measures the same decision?  
4. If no → new policy under `challenge/policies/` + protocol + panel/scorer; register in engine portfolio when ready.  
5. Learning `explore` / `compare` only if the problem is non-obvious (ID explore; English compare); challenge report always **English**.

---

## Related commands

| Command | Role |
|---------|------|
| `ml-saham doctor` / `doctor --deep` | Data coverage + integrity gates |
| `ml-saham vet` | English data-integrity audit |
| `ml-saham challenge engine screener [--scenario …]` | ADR-002 PolicySpec portfolio rollup |
| `ml-saham challenge run / factor / health / champion` | Policy product surface |
| `ml-saham compare <slug> …` | Single-factor curriculum lab (not promotion) |
