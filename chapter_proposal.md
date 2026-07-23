# Chapter Proposal — ML Learning CLI (IDX Stock Trading)

Problem-centric curriculum for a terminal-based mini app. Each chapter starts from a quant pain point on the Indonesia market (IDX), then offers ML algorithm options, reasons/caveats, and implementation sketches. Terminology is introduced gradually as problems get harder.

Related: [specs.md](./specs.md)

---

## Product goals (why this app exists)

1. **Learn ML step by step** — problem-centric lessons on IDX data, not an algo textbook.
2. **Feed `ai-saham`** — lessons and artifacts (features, models, eval habits, score definitions) should be reusable to **tune / improve** the existing `ai-saham` app.
3. **Own store when needed** — prefer real data from `ai-saham` when the schema fits; if learning needs a different shape (e.g. proper panel/time-series tables, chapter-specific feature stores), **`ml-saham` may keep its own database** derived from provider extracts — not blocked by `ai-saham` schema limits.

---

## Design rules

1. **Problem first, algorithm second** — no “Chapter: Random Forest”.
2. **Always answer three questions** per problem:
   - Which ML approaches fit?
   - Why / caveats (data quality, bias, hardware, misreading results)?
   - How to implement (libs, high-level diagram, data flow)?
3. **Learning path** — plain language early; glossary terms unlock only when needed.
4. **IDX-only context** — IHSG, tickers, corporate actions, Bahasa/English news, broker net buy/sell, foreign vs local flow, insider activity, shareholding, earnings, **IEV / pre-open**, liquidity reality. Align with `ai-saham` ingest (`fetch market`, `fetch iev`, enrichment) and engines (flow score, Signal, Risk, MCE).
5. **Language** — CLI / learner-facing interaction is **ID-first**; code identifiers, library names, and core finance/ML terms stay **EN** (e.g. `rank IC`, `momentum`, `walk-forward`, command flags). Glossary can give a short ID gloss when a term first appears.
6. **Ch.6 vs Ch.8 split** — Ch.6 = *who* (broker / foreign–local flow → rank); Ch.8 = *how much* (volume–price magnitude → anomaly only). No overlapping “burst” story owned by both. **Bandar / accumulation** metrics are an **advanced lab inside Ch.6**, not a myth “smart money” chapter.
7. **Learner arc** — start **retail-curious**, finish with **aspiring quant habits** (honest evaluation, cross-section thinking, costs awareness) — not “get rich with ML” vibes.
8. **Scoreboard** — default **long-only vs IHSG**; optional long/short as “cara riset membaca faktor.”
9. **Generic problem first; `ai-saham` as deep-dive** — every chapter teaches a **common quant/ML problem** that would make sense even without `ai-saham`. Mentions of SignalEngine, RiskEngine, MCE, flow score, IEV screen, etc. belong in an optional **Deep-dive: kaitkan ke ai-saham** block *after* the generic lesson (approaches, caveats, demo). Never invert that order. Artifacts for tuning `ai-saham` are a **bonus outcome**, not the chapter headline.
10. **Bridge to `ai-saham`** — deep-dives may produce artifacts aimed at tuning real engines; production `ai-saham` stays rules-first until a lesson proves a change.

---

## Teaching shape per chapter (generic → deep-dive)

```text
1) Masalah umum (IDX)     ← chapter title lives here
2) Opsi algoritma + caveat
3) Demo pada data real
4) [Opsional] Deep-dive: kaitkan ke ai-saham
      - engine / YAML / tabel terkait
      - artifact yang bisa dipakai untuk tune
```

If step 4 were removed, the chapter must still be a complete ML lesson.

---

## Problem map (tied to chapters — not a second roadmap)

Every row either **maps to a chapter** or is **out of this product**. No vague parking lot.

### Mapped to the chapter path

| Problem | Where it lives | Algorithm / approach (summary) |
|---|---|---|
| Clean missing / odd OHLC + corporate-action breaks | **Ch.1** | z-score / IQR → Isolation Forest, LOF; change-point for breaks |
| Rule screening vs learned ranking + **risk-gate mindset** (fund/liquidity precursors) | **Ch.2** | Rules → decision tree, logistic; maps toward `ai-saham` RiskEngine gates |
| Next-day / pattern toys (failure lab) | **Ch.3** | k-NN, tree, forest vs coin-flip; then pointer onward |
| Factor score (value / momentum / quality) + relative strength vs IHSG + **shareholding / ownership sleeve** | **Ch.4** | Hand weights → elastic net → LightGBM; ownership from shareholding composition |
| Sector / peers / “bergerak mirip” (+ sector-context diagnostics) | **Ch.5** | k-means, hierarchical clustering, PCA |
| Broker net & foreign vs local flow (*who*) + **bandar / BCI / accum-score components lab** | **Ch.6** | Flow rules → elastic net / logistic → LightGBM + momentum; artifact → foreign-flow score weights |
| Insider / “orang dalam” activity | **Ch.7** | Event rules → logistic / GBDT on insider features; heavy delay & sample-size caveats |
| Unusual volume / price jump + multi-ticker magnitude anomaly (*how much*) | **Ch.8** | Isolation Forest, One-Class SVM (price/volume only) |
| Headline tone | **Ch.9** | TF-IDF + naive Bayes / logistic → small IndoBERT |
| Volatility, sizing, typical spread / liquidity | **Ch.10** | GARCH vs GBDT/RF; simple liquidity/spread as sizing input |
| IHSG / **market-context regime (MCE-style factors)** | **Ch.11** | HMM, GMM, change-point + classifier; breadth / foreign / macro-style features when available |
| Multi-feature prediction + walk-forward + **calibrate ai-saham flow/signal weights** | **Ch.12** | LightGBM / XGBoost; use `signal_forward_labels`-style outcomes; compare to rule scores |
| Portfolio under constraints + **risk funnel in sizing** | **Ch.13** | ML scores + mean-variance / constrained opt; RiskEngine-style gates as filters |
| Corporate events at scale | **Ch.14** | GBDT event models; intro causal forest |
| Earnings surprise → return | **Ch.15** | Linear / GBDT on surprise features; PIT consensus caveats |
| **Opening-session mover ranking** (IEV/pre-open as deep-dive) | **Ch.16** | Rank/classify open candidates; session/leakage caveats |
| End-to-end research pipeline | **Ch.17** | Ensemble / stacking + experiment tracking; export artifacts into ai-saham research loop |
| Sequential allocation sandbox (RL) | **Ch.18** optional appendix | Bandits → toy DQN/PPO — not core path |

### Out of this product (removed on purpose)

| Dropped | Why |
|---|---|
| Support / break probability as a main problem | Fights Ch.3 “wrong question”; OK only as anti-pattern inside Ch.3 |
| Alt-data fusion | No data commitment; revisit only if you acquire alt data |
| Market-wide stress / scenario generators | Niche vs learner arc; optional spice after Ch.11 someday |
| Near-real-time streaming feature store | Systems problem beyond session IEV/pre-open |
| Uneven-liquidity multi-task / transfer learning | Too niche for retail → aspiring quant CLI |
| Seasonality as a main ML chapter | Calendar superstition risk; Ch.3 anti-pattern at most |
| Analyst consensus as its own chapter | Easy herding misuse; optional aside inside Ch.4 / Ch.9 only |
| Full tick microstructure tape | Optional **extension inside Ch.16** later if/when richer tape exists — not a separate scheduled chapter |

---

## Proposed chapters

| # | Chapter (problem title) | Tier | Algorithms introduced |
|---|---|---|---|
| 0 | **Orientasi** — What this CLI is, IDX data we use, how we judge “good” without fooling ourselves | — | Baselines only (buy & hold, rules). No fancy ML yet. |
| 1 | **Membersihkan harga saham** — Missing bars, splits, weird spikes | Simple | z-score / IQR → Isolation Forest, LOF |
| 2 | **Saring saham dengan aturan** — Rule screens vs learned ranking (+ risk-gate precursors) | Simple | Rules → decision tree, logistic regression |
| 3 | **Mengenali pola harga sederhana** — Patterns / next-day toy prediction as a **failure lab** + pointer to better framing | Simple | k-NN, decision tree, random forest; beat/lose coin-flip; then point to cross-section / walk-forward later |
| 4 | **Skor faktor: value, momentum, quality** — Combine signals into a rank (+ optional ownership sleeve) | Medium | Linear model, elastic net, LightGBM |
| 5 | **Mengelompokkan saham yang “bergerak mirip”** — Clustering / peers | Medium | k-means, hierarchical clustering, PCA |
| 6 | **Aliran broker & asing** — *Who*: broker/foreign flow ranks (+ bandar / accum-component lab) | Medium | Flow rules → elastic net / logistic → LightGBM + price factors |
| 7 | **Aktivitas insider** — Reported insider buy/sell as sparse event signals | Medium | Rules → logistic / GBDT; delay & tiny-sample caveats |
| 8 | **Volume & lonjakan tidak biasa** — *How much*: volume–price magnitude anomaly vs that ticker’s past | Medium | Isolation Forest, One-Class SVM (price/volume only; not broker identity) |
| 9 | **Membaca berita singkat** — Headline → up / down / neutral | Medium | TF-IDF + naive Bayes / logistic → small IndoBERT |
| 10 | **Volatilitas & ukuran posisi** — Forecast risk, not just return | Medium | GARCH vs GBDT / RF on vol features |
| 11 | **Rezim pasar IHSG** — When the same factor stops working (MCE-aligned) | Hard | HMM, GMM, change-point + classifier; optional market-wide foreign / breadth |
| 12 | **Prediksi multi-fitur dengan walk-forward** — Honest evaluation (+ **calibrate ai-saham scores**) | Hard | LightGBM / XGBoost + walk-forward; leakage examples; label corpus |
| 13 | **Membangun portofolio kecil** — Constraints, turnover, sector caps (+ risk funnel) | Hard | ML scores + mean-variance / constrained optimization |
| 14 | **Peristiwa korporasi massal** — Rights, buybacks, index events | Hard | GBDT event models; intro causal forest |
| 15 | **Earnings surprise** — Consensus miss/beat → short-horizon return | Hard | Linear / GBDT on surprise; PIT earnings dates |
| 16 | **IEV & pre-open** — Opening-session movers and candidate ranking (**generic open-rank first**) | Hard | Rank/classify pre-open features; IEV/screen deep-dive optional |
| 17 | **Pipeline riset ujung-ke-ujung** — Ingest → feature → model → backtest → report → **ai-saham artifact** | Complex | Stacking / ensemble + experiment tracking |
| 18 | **Sandbox keputusan berurutan** — Toy allocation under costs | Complex | **Optional / appendix** — bandits → toy RL (PPO / DQN); not on the core path |

### Appendix (not a numbered course chapter)

- **Kamus bertahap** — terms unlocked only after the chapter that needs them  
  (e.g. overfit after Ch.3, factor / rank IC after Ch.4, foreign flow after Ch.6, insider after Ch.7, regime after Ch.11, leakage after Ch.12, earnings after Ch.15, IEV/pre-open after Ch.16).

### Bridge to `ai-saham` (deep-dive only — not chapter titles)

`ai-saham` production engines are mostly **rules + classical stats** (YAML weights/thresholds). In each related chapter, teach the **generic problem first**; the mapping below is only for the optional deep-dive + artifact pack.

| Generic problem (chapter headline) | Ch. | Deep-dive: `ai-saham` hook | Artifact aim (optional) |
|---|---|---|---|
| Rank names from broker / foreign flow | **6** | Foreign-flow / accum score, BCI, bandar lab | Reweight components vs `ScoreForeignFlow` |
| Sparse insider event signals | **7** | Insider enrichment / company-quality flags | Feature defs for context panels |
| Peers / sector grouping | **5** | Sector-context diagnostics | Peer panels |
| When edges die by market state | **11** | MarketContextEngine / regime | Offline MCE factor blend notes |
| Honest multi-feature eval | **12** | `candidate_observations` + `signal_forward_labels`; SignalEngine weights | Calibration lab vs rule composite; DecisionPolicy stratified checks |
| Screen rules & soft risk filters | **2**, **13** | RiskEngine gates / risk funnel | Gate-feature checklist; not a black-box RiskEngine |
| Opening-session mover ranking | **16** | IEV + `screen pre-open` | Rank/filter vs rule screen; session caveats |
| Factor / ownership ranks | **4** | Fundamentals / shareholding caches | Sleeve definitions reusable in screens |
| Headline tone (when data exists) | **9** | Sentiment analyze path | Label/eval habits |
| Earnings surprise | **15** | `earnings_cache` | Event windows / PIT notes |
| End-to-end research loop | **17** | Same culture as `research/scripts/factor_card_*` | Report + suggested YAML diffs (human-applied) |

Chapter titles and CLI `explore` names stay **generic** (e.g. `broker-flow`, `walk-forward`, `pre-open-rank`) — not `signal-engine` or `mce`.

### Data note (`ai-saham` ingest)

`ml-saham` uses **real** provider data (personal self-teaching; own Stockbit account). **Ingest authority stays in `ai-saham`** (`saham fetch market`, enrichment, `saham fetch iev`, etc.). Learning may:

- read `ai-saham` SQLite directly when the shape is enough, **or**
- **materialize an `ml-saham` learning DB** (panel / time-series / feature tables) when `ai-saham` storage is awkward for lessons —

then export **artifacts** (feature defs, trained baselines, eval reports, suggested YAML weight diffs) intended to inform tuning of `ai-saham`.

### Open decisions (do not freeze yet)

| Topic | Status |
|---|---|
| `roadmap.md` | Ready to write — after your review of this incorporation |

### Settled — datasets (personal learning, real data)

| Decision | Choice |
|---|---|
| Audience / license posture | **Personal self-teaching only**; user's own Stockbit account; **no redistribution product** |
| Data authenticity | **Real provider data** (not synthetic-first) |
| Ingest authority | **`ai-saham`** (`fetch market`, enrichment, **`fetch iev`**, …) |
| `ml-saham` storage | **OK to own a learning DB** when ai-saham schema is a poor fit |
| Bridge back to ai-saham | Artifacts to tune engines — not a second scraper |
| MVP data | candles (+ IHSG), fundamentals, sector meta, broker summaries, foreign flow, optional broker_daily_flow, shareholding |
| v1.1 data | + insider, fuller sector panel (Ch.5/7/8) |
| Phase-2 data | + earnings, corp actions, headlines if any, **IEV / pre-open sidecars**, observation/label tables for Ch.12 |
| Default universe | Liquid subset (LQ45-like ∩ cached); scoreboard **IHSG** (Ch.16 uses session/open scoreboard separately) |
| PIT honesty | Teach `fetched_date` / as-of / session-clock caveats in Ch.0 and Ch.16 |
| Out for now | Public dataset shipping; full tick tape (optional Ch.16 extension only) |

### Settled — problem map + ai-saham engines

| Decision | Choice |
|---|---|
| No vague backlog dump | Map or cut |
| Fold / labs | shareholding → Ch.4; bandar/BCI/accum components → Ch.6; risk precursors → Ch.2; risk funnel → Ch.13; signal calibration → Ch.12; MCE → Ch.11 |
| Scheduled | Ch.7 insider; Ch.15 earnings; **Ch.16 IEV & pre-open** |
| Phase-2 candidate list | **Cleared** (microstructure folded as optional Ch.16 extension) |

### Settled — evaluation spine & MVP

| Decision | Choice |
|---|---|
| Evaluation spine | **Light early** in Ch.0 + Ch.3; **full walk-forward** in Ch.12 |
| MVP (v1) | **Ch.0, 1, 2, 3, 4, 6** |
| Soon after (v1.1) | Ch.5, 7, 8 |
| Phase 2 | Ch.9–17; Ch.18 optional RL appendix |

### Settled — learner, order, scoreboard, costs, RL

| Decision | Choice |
|---|---|
| Learner arc | Retail-curious → aspiring quant habits |
| Ch.4 / Ch.5 order | **Skor faktor before clustering** (swapped) |
| Scoreboard | **Long-only vs IHSG** default; long/short optional as “cara riset membaca faktor” |
| Costs in demos | **A default** (gross vs IHSG + banner *belum termasuk biaya*); optional `--with-costs` haircut (B); fuller costs in Ch.13 (C) |
| Ch.18 RL | **Optional appendix / phase 2** — not on the core MVP path |

**RL = Reinforcement Learning** (pembelajaran dengan umpan balik berulang).

Unlike Ch.4 (rank stocks from features → score), an RL setup looks more like a **game loop**:

```text
state (portfolio, prices, cash, …)
  → agent chooses an action (buy / sell / hold / rebalance)
  → market moves
  → agent gets a reward (e.g. return minus costs)
  → repeat many times; policy is updated to seek higher reward
```

In our outline, “Sandbox keputusan berurutan” means a **toy** allocator that learns a sequence of decisions under costs — using ideas like:

| Family | Plain idea | Names you may see |
|---|---|---|
| **Bandits** | Try options, learn which “arm” pays better (simpler than full RL) | contextual bandits |
| **Full RL** | Learn a policy over many states/actions | DQN, PPO |

That is **not** the same as “train LightGBM on factor scores.” It is sequential decision-making — closer to a simulated trader than to a ranking model.

### Why RL stays optional / phase 2 (not core path)

1. **Wrong lesson order** — retail → aspiring quant needs ranking, leakage, costs banners, walk-forward first. RL jumps to “AI that acts” before “AI that scores honestly.”
2. **Easy to misread** — demos look like a profitable bot; they usually overfit the simulator and ignore IDX liquidity/reality.
3. **Heavy for a mini CLI** — env design, reward shaping, unstable training; poor ROI vs Ch.4/6/12/13 for learning fundamentals.
4. **Bandits alone** (simpler) could be a tiny aside later; full PPO/DQN sandbox is spectacle unless the core path is already solid.

**Locked:** keep Ch.18 as **optional appendix / phase 2 unlock**, not MVP. Full PPO/DQN sandbox stays out of the core path; a tiny bandits aside is optional later if useful.

---

## Chapter 3 note — failure lab + correct framing

Ch.3 does **both**:

1. **Run the naive track** — next-day direction / simple pattern labels with k-NN, tree, small forest; compare to coin-flip and a dumb baseline.
2. **Show why it fails for learning “edge”** — tiny predictability, overfit, wrong question (one ticker’s tomorrow vs who wins in the cross-section), leakage temptations, ignoring costs.
3. **Point to the better framing (later chapters)** — e.g. cross-sectional rank (Ch.4, Ch.6), honest walk-forward (Ch.12), risk/sizing (Ch.10), portfolio constraints (Ch.13). Ch.3 should end with an explicit “lanjut di …” map, not a claim that next-day accuracy is the goal.

---

## Chapter 4 deep dive — Skor faktor: value, momentum, quality

Learners stop looking at one ticker in isolation and start **ranking the IDX cross-section** with a few economic “stories,” then ask: *can ML combine those stories better than a hand-weighted score?*

This is not a claim of live trading edge. Success = understanding the pipeline and the ways a pretty backtest lies.

### Problem (plain language)

Every month a quant faces hundreds of IDX names. Spreadsheet rules (“PE < 15 and ROE > 10”) are slow, opinionated, and hard to combine fairly. A **factor score** turns a few measurable traits into a ranking: prefer names that look cheap, recently strong, and fundamentally healthier — then test whether that ranking related to later returns.

### What “faktor” means here

A **factor** is a measurable trait that, by theory or history, relates to return — not a candlestick pattern and not a news headline.

| Factor | Plain idea | Example features (IDX-friendly) |
|---|---|---|
| **Value** | Cheap vs expensive | E/P, B/P, EV/EBITDA (where available), dividend yield |
| **Momentum** | Recent winners vs losers | 3 / 6 / 12-month return; often skip the last month (less short-term noise); relative strength vs IHSG |
| **Quality** | Healthier businesses | ROE, debt/equity, earnings stability, simplified accruals |
| **Ownership** (optional sleeve) | Who holds the float | Institution vs individual %, top-holder concentration — from `shareholding_composition`-style fields |

Each stock gets a **score per factor**, then a **combined score** used to rank. Default demo: hold the **top bucket long-only vs IHSG**. Optional aside: long/short spread as “cara riset membaca faktor.”

Ownership is a **sleeve inside Ch.4**, not its own chapter. Teach it after value/momentum/quality so learners see “another economic story,” not a new product feature.

### Why this chapter is Medium

- Still explainable in spreadsheet terms (“cheap + rising + solid”).
- Dataset is larger (many tickers × months), so manual ranking gets painful and biased.
- First real taste of **cross-sectional** ML: predict relative winners, not “will BBCA go up tomorrow.”
- Natural place to introduce: z-scoring, sector-neutralizing, fundamental look-ahead, liquidity filters.

### Data flow

```text
IDX universe (e.g. LQ45 or “liquid enough”)
    → pull prices + fundamentals (point-in-time if possible)
    → compute raw factor metrics
    → winsorize / z-score within sector (or whole market)
    → combine → rank → toy long/short or long-only backtest
    → compare: equal-weight factors vs learned weights (ML)
```

### Teaching arc (three approaches, same problem)

1. **Hand score (no ML)**  
   `combined = 0.4*value_z + 0.4*momentum_z + 0.2*quality_z`  
   Establish the economic idea before any model.

2. **Linear / elastic net**  
   Predict next-month (or next ~21 trading day) cross-sectional return from factor z-scores.  
   Learned weights replace gut 0.4 / 0.4 / 0.2 — still interpretable coefficients.

3. **LightGBM (or similar GBDT)**  
   Same inputs, optional interactions (e.g. value × low-volatility).  
   Show non-linear blends and feature importance — then stress: importance ≠ causality, and importance flips by regime (tease Ch.11).

Do **not** put deep nets in this chapter; they hide the factor intuition at the wrong difficulty.

### Algorithm options (reasons & caveats)

| Approach | Why use it | Caveats / considerations |
|---|---|---|
| Equal-weight / hand weights | Baseline: “do we need ML at all?” | Arbitrary weights; easy to overfit by hand-tuning after seeing results |
| Ridge / elastic net | Learned linear blend; coefficients tell a story | Assumes roughly linear effects; collinear factors (value vs quality) need regularization |
| LightGBM / XGBoost | Non-linear combos + interactions on laptop-friendly tabular data | Easy to overfit small IDX universes; feature importance misleads; needs walk-forward discipline |
| Simple ranker (optional aside) | Preview Ch.12: optimize ranking, not MSE on returns | Extra terminology; keep as “coming later” unless learner is ready |

### Implementation sketch

| Piece | Suggestion |
|---|---|
| Features | pandas for factor construction; winsorize at e.g. 1% / 99%; z-score cross-sectionally (optionally within sector) |
| Linear ML | `sklearn.linear_model.ElasticNet` / `Ridge` |
| Tree ML | LightGBM regressor or sklearn `HistGradientBoostingRegressor` |
| Evaluation | Rank IC (correlation of score vs forward return); quintile spreads; naive cumulative curve of top quintile vs IHSG |
| Hardware | Daily/monthly cross-section on LQ45 or similar: fine on a laptop |

High-level diagram:

```text
[prices]──┐
           ├→ [factor metrics] → [clean/z-score] → [hand | elastic net | LightGBM]
[fundies]──┘                         │
                                     ↓
                              [rank / quintiles]
                                     ↓
                         [IC + toy PnL vs IHSG]
```

### CLI demo shape

```text
ml-saham explore factor-score
ml-saham demo factor-score --universe LQ45 --horizon 21d --model equal-weight
ml-saham demo factor-score --universe LQ45 --horizon 21d --model elastic-net
ml-saham demo factor-score --universe LQ45 --horizon 21d --model lightgbm
ml-saham compare factor-score --baseline equal-weight --against lightgbm
```

Terminal outputs worth showing:

- Top / bottom 10 names by score on a chosen date
- Rank IC of score vs forward return
- Naive cumulative PnL of top quintile vs IHSG (banner: **costs not included**)
- Side-by-side: equal-weight vs elastic net vs LightGBM

### IDX-specific caveat checklist

Teach these in-chapter (not as fine print):

- [ ] **Liquidity** — thin names can look “cheap” or “high momentum” off one print; universe filter often matters more than model choice
- [ ] **Point-in-time fundamentals** — using “today’s” filing for a 2019 backtest is classic leakage; delay report dates even in a toy dataset
- [ ] **Sector bias** — banks vs commodity names dominate crude value screens; sector z-score is a first fix
- [ ] **Corporate actions / reporting quirks** — rights issues, restatements, missing fields; factor data quality beats a fancier booster
- [ ] **Crowding / regime** — momentum (and other factors) often work until they don’t; factors are not forever → Ch.11
- [ ] **Costs & turnover** — top-decile rebalancing can erase paper alpha under IDX-like cost assumptions (default scoreboard is gross vs IHSG + banner; optional haircut)
- [ ] **Flow is a separate story** — broker / foreign net can be a fourth sleeve later → Ch.6; keep Ch.4 focused on value / momentum / quality (+ optional ownership)
- [ ] **Ownership data staleness** — shareholding snapshots are sparse; don’t pretend daily rebalance on stale holder %

### Glossary unlocks (introduce only when used)

| Term | When |
|---|---|
| Cross-section | First ranking of many tickers on one date |
| Z-score / winsorize | When comparing PE of BBCA vs a small cap fairly |
| Rank IC | When evaluating whether the score ordered future returns |
| Look-ahead / point-in-time | When building fundamental factors |
| Quintile spread | When showing top vs bottom basket (optional riset aside; default remains long-only vs IHSG) |
| Ownership / shareholding | When adding the optional fourth sleeve |

### Learning outcomes

After Ch.4, a learner should be able to:

1. Explain value, momentum, and quality in one sentence each (and ownership if the sleeve is unlocked).
2. Describe how raw metrics become z-scores and a combined skor / ranking.
3. Say when a hand-weighted score is enough vs when linear ML / LightGBM might help.
4. Point out how leakage, liquidity, and sector bias fake a beautiful backtest.
5. Read the default scoreboard (long-only top bucket vs IHSG) without treating it as live advice.

### Bridges to other chapters

| From Ch.4 | Toward |
|---|---|
| Hand rules vs learned rank | Ch.2 (saring saham) as the simpler cousin |
| Peer groups / sector neutralize | Ch.5 (clustering) as optional peer definition |
| Fourth sleeve: broker / foreign flow | Ch.6 (aliran broker & asing) |
| Sparse event signals (insider) | Ch.7 (aktivitas insider) |
| “Factors die in risk-off” | Ch.11 (rezim IHSG) |
| Honest multi-feature prediction | Ch.12 (walk-forward) |
| From scores to holdings | Ch.13 (portofolio kecil) |
| Earnings as event-return link | Ch.15 (earnings surprise) |

---

## Chapter 6 deep dive — Aliran broker & asing

IDX participants watch broker boards and “asing masuk/keluar” constantly. This chapter turns **broker net buy/sell summaries** and **foreign vs local flow** (from broker identity) into **rank signals** — *who* was active — and teaches how easy it is to misread them.

**Split vs Ch.8:** Ch.6 owns *who* (broker / foreign–local → cross-sectional rank). Ch.8 owns *how much* (volume–price magnitude → anomaly vs own history). Identity-based ranking stays here.

**Bandar / accumulation advanced lab (not a separate chapter):** provider fields like `bandar_detector` / broker-distribution concentration may appear as an **optional lab** at the end of Ch.6 — framed as “concentration metrics with heavy myth risk,” never as smart-money detection.

Not surveillance. Not “smart money identified.” Success = treating flow as a **noisy, delayed feature** with IDX-specific failure modes.

### Problem (plain language)

Price and volume alone do not show *who* was active. Broker summaries show which broker codes accumulated or distributed a name; rolling those codes up by foreign vs local identity gives a foreign-flow story. Doing this by eye across many tickers is slow and opinionated. Can we build a **ranking score** without fooling ourselves?

### What data we mean

| Signal | Plain idea | Typical grain |
|---|---|---|
| **Broker net** | Buy − sell (value or shares) per broker code per ticker per day/window | Broker × ticker × day |
| **Foreign vs local flow** | Same nets aggregated by broker identity (foreign desk vs local) | Side × ticker × day |
| **Derived scores** | N-day foreign net, local net, broker concentration (e.g. top broker share of volume), persistence (days of consecutive foreign net buy) | Ticker × day |

### Why this chapter is Medium (stretches into Hard later)

- Same cross-sectional ranking skills as Ch.4, but a **different data source** and different mistakes.
- Still laptop-friendly at daily broker-summary grain.
- Becomes Hard when fused into walk-forward multi-feature models (Ch.12) or market-wide regime features (Ch.11).
- Near-real-time broker tape would be Complex — out of scope unless streaming ingest exists.

### Where else flow appears (reuse, don’t duplicate)

| Chapter | Role of broker / foreign flow |
|---|---|
| Ch.2 Saring saham | Optional rule filter: N-day foreign net |
| Ch.4 Skor faktor | Optional fourth sleeve only *after* Ch.6 concepts |
| Ch.5 Clustering | Optional peer groups when interpreting flow concentration by theme |
| Ch.7 Insider | Different *who* — disclosed insider filings, not broker boards |
| Ch.8 Volume & lonjakan | Separate chapter: magnitude anomalies from price/volume — not broker identity |
| Ch.11 Rezim IHSG | Market-wide foreign net / breadth of foreign buying as regime features |
| Ch.12 Walk-forward | Do flow features survive honest validation? |
| Ch.13 Portofolio | Teaching overlay only: prefer supportive flow |
| Ch.17 Pipeline | Another ingest source in the end-to-end diagram |

### Data flow

```text
broker summary (net buy/sell by broker code)
    → map broker code → foreign / local (identity table)
    → aggregate per ticker: foreign_net, local_net, broker_concentration, …
    → choose window (1d / 5d / 20d)
    → winsorize / z-score cross-sectionally (liquid universe)
    → rank score → IC / quintiles vs forward return
    → optional: blend with momentum (and later value/quality) via elastic net / LightGBM
```

### Teaching arc

1. **Hand rule** — e.g. 5d or 20d foreign net > 0; rank LQ45; compare to “do nothing.”
2. **Cross-sectional z-score of flow** — reuse Ch.4 pattern so flow feels like a factor sleeve, not magic.
3. **ML blend** — elastic net or LightGBM: momentum + foreign flow (+ local flow); coefficients / importance with heavy caveats.
4. **Caveats as first-class content** — mislabeling, facilitation, timing, thin names, crowding.
5. **Pointer** — “lonjakan volume/harga tanpa identitas broker” → Ch.8; insider filings → Ch.7.
6. **Optional lab** — bandar/accumulation concentration metrics with explicit anti-mythology framing.

### Algorithm options (reasons & caveats)

| Approach | Why use it | Caveats / considerations |
|---|---|---|
| N-day foreign/local net rules | Matches how retail/quants already talk; strong baseline | Easy superstition; sensitive to window; ignores magnitude vs liquidity |
| Cross-sectional z-score + equal weight | Same language as Ch.4 faktor skor | Still arbitrary; foreign net ≠ informed flow |
| Logistic / elastic net on flow features | Learned weights on foreign_net, local_net, concentration, persistence | Collinearity (foreign net ≈ price momentum in some regimes); label noise |
| LightGBM with price + flow | Shows when flow adds (or doesn’t) beyond momentum | Overfit on small universes; needs walk-forward (Ch.12); importance ≠ causality |

Isolation Forest / LOF for bursts are **out of Ch.6 ownership** — teach under Ch.8 (volume–price anomaly).

### Implementation sketch

| Piece | Suggestion |
|---|---|
| Identity map | Static or versioned table: broker_code → {foreign, local, unknown} |
| Features | pandas aggregation; 1d/5d/20d nets; concentration (HHI or top-1 share); persistence counts |
| Ranking ML | `ElasticNet` / `LogisticRegression`; LightGBM optional |
| Evaluation | Rank IC vs forward return; quintile spreads; always compare incremental value vs momentum-only |
| Hardware | Daily summaries for LQ45-sized universes: laptop-OK |

High-level diagram:

```text
[broker nets] → [broker→foreign/local map] → [ticker flow features]
                                                    │
                         ┌──────────────────────────┴──────────────────────────┐
                         ↓                                                     ↓
                  [hand / z-score rank]                             [elastic net / LGBM
                         ↓                                            + momentum]
                  [IC / quintiles]                                  [blend comparison]
```

### CLI demo shape

```text
ml-saham explore broker-flow
ml-saham demo broker-flow --universe LQ45 --window 5d --model foreign-net-rule
ml-saham demo broker-flow --universe LQ45 --window 20d --model elastic-net
ml-saham compare broker-flow --baseline momentum --against momentum+foreign
```

Terminal outputs worth showing:

- Top / bottom names by foreign-net z-score on a date
- Broker concentration for a single ticker (who dominated the net)
- Rank IC: foreign-flow score vs forward return (and vs momentum-only)
- Banner: **foreign label is approximate; not “smart money”**

### IDX-specific caveat checklist

- [ ] **Identity is approximate** — omnibus / nominee brokers mistag foreign vs local
- [ ] **Net buy ≠ informed** — index rebalance, facilitation, client flow, noise
- [ ] **Timing / session** — which board snapshot vs which return window (easy look-ahead)
- [ ] **Liquidity** — one foreign print can dominate thin names
- [ ] **Crowding** — retail chasing broker boards can invert a paper edge
- [ ] **Collinearity with momentum** — always compare flow **incremental** to price momentum
- [ ] **No surveillance claim** — educational ranking only; magnitude bursts → Ch.8; bandar lab ≠ smart money

### Glossary unlocks (introduce only when used)

| Term | When |
|---|---|
| Broker net | First time showing buy − sell by broker code |
| Foreign flow / local flow | When aggregating by broker identity |
| Broker concentration | When one broker dominates the net |
| Persistence | When counting consecutive net-buy days |
| Omnibus / nominee (plain words first) | When explaining why foreign labels are noisy |
| Bandar / accumulation (lab only) | Optional end-of-chapter lab — myth warnings first |

### Learning outcomes

After Ch.6, a learner should be able to:

1. Explain broker net and foreign vs local flow in plain language.
2. Build a simple N-day foreign-net rank and evaluate it like a factor (IC / quintiles).
3. Keep *who* (this chapter) separate from *how much* volume–price spikes (Ch.8) and from insider filings (Ch.7).
4. List IDX-specific ways flow signals lie (mislabel, facilitation, liquidity, crowding).
5. Test whether flow adds anything beyond momentum before trusting a blend.
6. (Lab) Treat bandar/accumulation metrics as noisy concentration features, not prophecy.

### Bridges to other chapters

| From Ch.6 | Toward |
|---|---|
| Cross-section z-score / IC habit | Ch.4 (skor faktor) as the template just learned |
| Disclosed insider *who* | Ch.7 (aktivitas insider) |
| Volume–price magnitude anomalies | Ch.8 (volume & lonjakan) — different question |
| Market-wide foreign breadth | Ch.11 (rezim IHSG) |
| Does flow survive honest validation? | Ch.12 (walk-forward) |
| Overlay on holdings | Ch.13 (portofolio kecil) |
| Ingest path for broker files | Ch.17 (pipeline) |

---

## Chapter 2 note — Saring saham (+ deep-dive risk gates)

**Generic problem:** Hand screens are slow and opinionated; can a simple model learn a ranking from labels better than fixed rules?

**Approaches:** explicit rules → decision tree / logistic → always compare to the hand rule.

**Deep-dive (`ai-saham`):** same screen features often appear in RiskEngine-style gates — optional mapping to `risk_engine.yaml`; do **not** title this chapter “RiskEngine.”

---

## Chapter 7 note — Aktivitas insider

**Problem:** Reported insider buy/sell is a sparse *who* signal different from broker boards — delayed, tiny samples, easy folklore.

**Approaches:** hand rules (net insider buy over N days) → logistic / GBDT on simple event features → always compare to a no-insider baseline.

**Caveats (first-class):** reporting lag, role quality (director vs employee), illiquid names, look-ahead on `transaction_date` vs `fetched_date`.

**Scoreboard:** long-only names with recent constructive insider activity vs IHSG (gross + biaya banner); not a claim of illegal-info edge.

**Data shape (from `fetch market` enrichment):** role, action_type, shares, price, ownership before/after, transaction_date.

---

## Chapter 15 note — Earnings surprise

**Problem:** After earnings, markets reprice — can surprise vs consensus help rank short-horizon returns without leaking filing dates?

**Approaches:** rules on `eps_surprise_pct` → linear / GBDT → event study windows; walk-forward discipline from Ch.12 required.

**Caveats:** point-in-time consensus, announcement vs available-in-database time, thin coverage outside liquid names, costs around gaps.

**Scoreboard:** long-only surprise bucket vs IHSG after event; optional riset long/short aside.

**Data shape:** `eps_actual`, `eps_estimate`, `eps_surprise_pct`, YoY fields from earnings cache.

---

## Chapter 12 note — Walk-forward (+ deep-dive calibrate scores)

**Generic problem:** Multi-feature predictions look great until you respect time — how do we evaluate honestly (walk-forward, leakage, costs banner)?

**Approaches:** LightGBM / XGBoost with walk-forward; leak demos; long-only vs IHSG scoreboard.

**Deep-dive (`ai-saham`):** optional calibration lab — use flow/signal *components* and `signal_forward_labels` (e.g. `SWING_10D`) to compare ML blends vs today’s rule composite; emit suggested weight notes for humans (no auto-promote).

---

## Chapter 13 note — Portofolio (+ deep-dive risk funnel)

**Generic problem:** Scores ≠ holdings. How do we build a small portfolio under sector, turnover, and liquidity constraints?

**Approaches:** ML scores + constrained optimization; costs banner / optional haircut.

**Deep-dive (`ai-saham`):** optional RiskEngine-style OPEN/BLOCKED funnel as filters before sizing — still a portfolio lesson first.

---

## Chapter 16 note — Opening-session ranking (+ deep-dive IEV / pre-open)

**Generic problem:** Before the open, which names deserve attention — and how do we rank them without leaking session timing?

**Approaches:** simple ranker baseline → logistic / GBDT on pre-open features (gap, ATR/RSI, broker tags if any) → opening-horizon scoreboard (not default IHSG long-only).

**Deep-dive (`ai-saham`):** map to **IEV movers** + `screen pre-open` rule stack; compare ML rank vs IEV/rule screen; session-clock caveats first-class.

**Optional extension:** fuller order-book / tick tape if available — still under this chapter.

---

## Chapter 17 note — Pipeline (+ deep-dive ai-saham artifacts)

**Generic problem:** How do we run an end-to-end research loop (ingest → features → model → backtest → report) without fooling ourselves?

**Deep-dive:** export an artifact pack in the same spirit as `ai-saham` `research/scripts/factor_card_*` (human-applied YAML/config notes).

---

## Per-chapter teaching template (CLI)

For every chapter / problem, the terminal flow should cover:

1. **Describe the generic IDX problem** (short story + real data slice).
2. **List approach options** (rules → classical ML → heavier models when justified).
3. **Compare caveats** (data quality, bias, hardware, how people misread metrics).
4. **Run a tiny demo** (train / evaluate / ASCII chart or saved plot).
5. **Show implementation sketch** (library choices, text data-flow diagram).
6. **Optional deep-dive** — `ml-saham deepdive <topic>` (or section flag) linking to `ai-saham` engines/artifacts — skippable without breaking the lesson.

Example vibe:

```text
ml-saham --db … explore broker-flow
ml-saham --db … demo broker-flow --universe LQ45
ml-saham --db … deepdive broker-flow   # optional: kaitkan ke accum/flow score
```

---

## Suggested library map (implementation hints)

| Area | Prefer first | Optional later |
|---|---|---|
| Tabular ML | scikit-learn | — |
| Gradient boosting | LightGBM | XGBoost, CatBoost |
| Time series stats | statsmodels (GARCH, etc.) | — |
| Optimization | cvxpy / scipy | — |
| NLP (Bahasa) | scikit-learn TF-IDF | IndoBERT / transformers |
| Deep learning demos | PyTorch (small) | — |
| Online / streaming concepts | river | — |
| Experiment tracking | plain JSON / CSV logs | MLflow (complex chapters) |

---

## Out of scope (remind learners)

- Live trading advice or “guaranteed edge”.
- Claiming surveillance / market-manipulation detection as production-ready.
- Algorithm-centric textbook chapter order (SVM week, then neural nets week, …).

---

## Decisions log (from review)

| # | Decision |
|---|---|
| 1 | `roadmap.md` after review of ai-saham engine incorporation |
| 2 | Datasets — **real** personal data; ingest in ai-saham; ml-saham may **own learning DB** if schema unfit; artifacts feed back to tune ai-saham |
| 3 | Ch.3 = failure lab **and** pointer to correct framing in later chapters |
| 4 | Scoreboard: **default long-only vs IHSG**; optional long/short as “cara riset membaca faktor” (Ch.16 uses open-session scoreboard) |
| 5 | Interaction ID-first; code + core finance/ML terms EN |
| 6 | Ch.6 = who / flow rank; Ch.8 = how much / volume–price anomaly |
| 7 | Learner: retail-curious → aspiring quant habits |
| 8 | Chapter order: **faktor (Ch.4) before clustering (Ch.5)** |
| 9 | Ch.18 RL — **optional appendix / phase 2** (not core MVP) |
| 10 | Costs in demos — **A default** (gross + banner); optional B haircut; C in Ch.13 |
| 11 | Evaluation spine — light in Ch.0 + Ch.3; full walk-forward in Ch.12 |
| 12 | MVP = Ch.0, 1, 2, 3, 4, 6; v1.1 = Ch.5, 7, 8; phase 2 = Ch.9–17 |
| 13 | Problem map: fold overlaps; drop support/break + speculative fluff |
| 14 | ai-saham bridge: flow/Signal/Risk/MCE/DecisionPolicy/labels/factor-cards mapped; **Ch.12 calibration lab**; risk → Ch.2+Ch.13 |
| 15 | Product goals: (1) step-by-step ML learning (2) artifacts to tune ai-saham (3) own learning DB OK when schema incompatible |
| 16 | **Ch.16** opening-session ranking scheduled; IEV/pre-open = deep-dive; microstructure = optional extension |
| 17 | **Generic problem first; ai-saham = optional deep-dive** — chapters must stand alone without ai-saham branding |
