# Chapters — ML Learning CLI (IDX)

Final curriculum for `ml-saham`: problem-centric, IDX-only, personal self-teaching with **real** market data.

Frozen design docs (this set). Early drafts live locally under `archive/` (gitignored).  
Ideas not scheduled: [problem_backlog.md](./problem_backlog.md)  
CLI UX: [ux.md](./ux.md)  
Architecture: [architecture.md](./architecture.md) · Data: [data_contract.md](./data_contract.md) · Artifacts: [artifacts.md](./artifacts.md) · MVP: [mvp_acceptance.md](./mvp_acceptance.md)  
Roadmap: [roadmap.md](./roadmap.md)

---

## Product goals

1. Learn ML **step by step** on IDX problems (not an algorithm textbook).
2. Optionally produce **artifacts** that help tune `ai-saham` (features, eval habits, weight notes).
3. Prefer data from `ai-saham` ingest; **`ml-saham` may own a learning DB** when a panel / time-series / feature-store shape is needed.

---

## Design rules

1. **Problem first, algorithm second.**
2. Per problem always cover: approach options → caveats → implementation sketch (libs, data flow).
3. **ID-first** learner copy; code and core finance/ML terms stay **EN**.
4. Glossary unlocks gradually with chapter difficulty.
5. **Generic problem first**; any `ai-saham` engine/YAML/table link is an **optional deep-dive after** the core lesson. Removing the deep-dive must leave a complete ML chapter.
6. Default scoreboard: **long-only vs IHSG** (gross + *belum termasuk biaya* banner). Optional long/short = “cara riset membaca faktor.” Ch.18 (`pre-open-rank`) uses an **opening-session** scoreboard instead.
7. Ch.6 = *who* (broker / foreign flow rank); Ch.9 = *how much* (volume–price anomaly). No shared ownership of “burst” stories.
8. Bandar / accum-style concentration = **lab inside Ch.6**, not a “smart money” chapter.

### Teaching shape

```text
1) Masalah umum (IDX)          ← chapter title
2) Opsi algoritma + caveat
3) Demo pada data real
4) [Opsional] Deep-dive: kaitkan ke ai-saham + artifact
```

---

## Ship phases

| Phase | Chapters |
|---|---|
| **MVP (v1)** | 0, 1, 2, 3, 4, 6 |
| **v1.1** | 5, 7, 9 |
| **Phase 2** | 8, 10–20 |
| **Phase 3 (Advanced)** | 21–44 |

**Evaluation spine:** light honesty in Ch.0 + Ch.3 (train/test, no future peek, coin-flip, biaya banner); full walk-forward in Ch.13.

**Costs:** default gross + banner; optional simple haircut flag; fuller costs in Ch.14.

---

## Data

| Topic | Choice |
|---|---|
| Authenticity | Real provider data (personal Stockbit / `ai-saham` fetch) |
| Ingest | Stays in `ai-saham` (`fetch market`, enrichment, `fetch iev`, …) |
| Learning store | Read `ai-saham` DB and/or materialize `ml-saham` learning tables |
| MVP data | candles (+ IHSG), fundamentals, sector meta, broker summaries, foreign flow, optional broker_daily_flow, shareholding |
| v1.1 data | + insider, fuller sector panel |
| Phase-2 data | + earnings, corp actions, headlines if any, IEV/pre-open sidecars, observation/label tables |
| Universe default | Liquid subset (LQ45-like ∩ cached) |

---

## Chapter list

| # | Title (generic problem) | Tier | Shipped algorithms (code SSOT) | Optional deep-dive → `ai-saham` |
|---|---|---|---|---|
| 0 | **Orientasi** — how we judge “good” without fooling ourselves | — | Baselines (buy & hold, rules), PIT/`fetched_date` checks | Data paths, PIT/`fetched_date` honesty |
| 1 | **Membersihkan harga saham** — missing bars, splits, spikes | Simple | LOF & MAD (default) vs Isolation Forest (compare) | Corp-action break hygiene in caches |
| 2 | **Saring saham dengan aturan** — rules vs learned rank | Simple | LightGBM (default) vs DecisionTree (compare) | Risk-gate *precursors* (fund/liquidity features) |
| 3 | **Mengenali pola harga sederhana** — next-day / pattern **failure lab** | Simple | LightGBM/DecisionTree vs 50% coin-flip; binomial Z-test | — |
| 4 | **Skor faktor** — value, momentum, quality (+ ownership sleeve) | Medium | LightGBM (default) vs ElasticNet/Ridge (compare) | Fundamentals / shareholding caches |
| 5 | **Mengelompokkan saham yang bergerak mirip** — peers / clusters | Medium | k-means (core deps); HDBSCAN + UMAP when `umap-learn` installed | Sector-context diagnostics |
| 6 | **Aliran broker & asing** — *who* ranks from flow | Medium | Ridge foreign-net flow vs momentum baseline | Accum / foreign-flow score components, BCI |
| 7 | **Aktivitas insider** — sparse disclosed insider events | Medium | Logistic Regression (default) vs insider net-shares rule (compare) | Insider enrichment flags |
| 8 | **Memprediksi waktu reaksi harga (Survival Analysis)** — time-to-event | Hard | Time-to-event scores (XGBoost-style / Ridge) vs Kaplan–Meier | `insider_cache` (waktu hingga profit) |
| 9 | **Volume & lonjakan tidak biasa** — *how much* anomalies | Medium | MLP reconstruction autoencoder (default) vs IsolationForest (compare) | — |
| 10 | **Membaca berita singkat** — headline tone | Medium | TF-IDF + LogisticRegression (default) vs MultinomialNB (compare); synthetic corpus OK | Sentiment path (when headlines exist) |
| 11 | **Volatilitas & ukuran posisi** — forecast risk for sizing | Medium | Ridge dynamic sizing vs static risk baseline | — |
| 12 | **Rezim pasar** — when the same edge stops working | Hard | RandomForest regime classifier | Market context / regime engine |
| 13 | **Prediksi multi-fitur + walk-forward** — honest evaluation | Hard | LightGBM (default) vs ElasticNet + purged time-series split | Calibrate rule score weights vs forward labels |
| 14 | **Membangun portofolio kecil** — constraints & holdings | Hard | Equal-weight vs capped-weight vs Hierarchical Risk Parity (HRP) | Risk funnel as filters before sizing |
| 15 | **Peristiwa korporasi massal** — rights, buybacks, index events | Hard | Event-study CAR vs IHSG; RandomForest residual compare | Corp-action calendars / events |
| 16 | **Earnings surprise** — miss/beat → short-horizon return | Hard | LightGBM PEAD-style forward return scores | Earnings cache |
| 17 | **Nowcasting fundamental (Mixed-Frequency)** — fundamental lag | Hard | Mixed-frequency panel; MLP vs OLS-style baseline | `company_fundamentals` as-of join |
| 18 | **Peringkat menjelang pembukaan** — opening-session ranking | Hard | IEV/IEP imbalance ranking + open-session scoreboard | IEV movers + pre-open screen |
| 19 | **Pipeline riset ujung-ke-ujung** — ingest → model → report | Complex | Feature panel + combinatorial purged-CV style metrics | Artifact pack (factor-card style) |
| 20 | **Sandbox keputusan berurutan** — sequential allocation under costs | Complex | Multi-armed bandit epsilon-greedy vs random; policy entropy | — |
| 21 | **Efek musiman & anomali kalender** — seasonality drift | Hard | Kruskal–Wallis calendar test + ridge-style seasonality | `seasonality_cache` |
| 22 | **Konsensus analis & revisi target harga** — analyst consensus | Hard | Target upside % + consensus buy-ratio features | `analyst_cache` |
| 23 | **Akumulasi broker top-N & konsentrasi kepemilikan** — broker accumulation | Hard | Ownership Gini + top-N accumulation; LightGBM classify | `broker_distribution_cache` |
| 24 | **Deteksi sindikasi broker (Graph ML)** — coordinated rings | Complex | networkx centrality / PageRank on broker flow graph | `broker_daily_flow` network |
| 25 | **Partisipasi pasar & rotasi sektor** — sector breadth | Hard | Sector participation / breadth index (PCA-style) | `factor_card_sector_breadth.py` |
| 26 | **Kompresi volatilitas & klasifikasi breakout** — volatility squeeze | Hard | BB/KC squeeze features + LightGBM breakout classifier | `strategies/bb-squeeze` |
| 27 | **Relative strength Mansfield vs IHSG** — relative strength | Hard | Mansfield RS vs IHSG; MLP / ElasticNet-style scores | `strategies/rs-momentum` |
| 28 | **Skor kualitas akuntansi Piotroski F-Score** — financial quality | Hard | Piotroski 9-signal matrix + LightGBM quality classifier | `company_financials` |
| 29 | **Model kebangkrutan Altman Z-Score** — financial distress | Hard | Emerging-market Altman Z' + anomaly filter | `company_financials` |
| 30 | **Klasifikasi breakout awan Kumo Ichimoku** — ichimoku cloud | Hard | Tenkan/Kijun/Span features; ML vs classic crossover | `plugins/indicators/ichimoku.py` |
| 31 | **Klasifikasi sinyal akumulasi broker bandar** — bandar detector | Hard | Multi-window accum features + Isolation Forest | `bandar_detector` |
| 32 | **Valuasi konsensus Forward P/E & rasio PEG** — forward valuation | Hard | Forward P/E & PEG features + RandomForest | `forward_estimates_cache` |
| 33 | **Notasi khusus bursa, UMA & risiko likuiditas** — special monitoring | Hard | Notation / UMA / haircut risk gating classifiers | `ticker_notation_cache` |
| 34 | **Anomali akrual Sloan & kualitas laba** — earnings quality | Hard | Sloan accrual quality + LightGBM | `company_financials` |
| 35 | **Ilikuiditas & dampak harga mikrostruk** — microstructure impact | Hard | Amihud-style illiquidity / impact features + RandomForest | `candles` |
| 36 | **Super learner ensemble multi-faktor terstack** — meta ensemble | Complex | Level-1 Ridge reweight of multi-factor scores | Multi-factor stacked pipelines |
| 37 | **Menantang pembobotan statis AccumScorePolicy** — accum policy | Hard | LightGBM/Ridge on accum components vs manual equal weights | `score_accum_use_case` |
| 38 | **Menantang aturan batas (capping) dan Raw Score Pre-Open** — pre-open heuristic | Hard | Learned classifier on raw IEP/pressure vs manual heuristic tree | `pre_open_directional_baseline` |
| 39 | **Menantang penggabungan makro: Signal × Market × Risk** — accum macro | Hard | Ridge macro-ensemble vs static product of sleeves | Accum macro glue |
| 40 | **Deep fingerprint mining** — high-dim accum features | Hard | LightGBM/XGBoost-style on large feature fingerprint | Accum feature store |
| 41 | **Pre-open modul arah (direction)** | Hard | Direction audit module vs baseline rules | Pre-open direction path |
| 42 | **Pre-open modul partisipasi (spoofing-ish)** | Hard | Participation / spoofing-risk audit features | Pre-open participation path |
| 43 | **Pre-open modul auction quality** | Hard | Auction quality audit features | Pre-open auction path |
| 44 | **Pre-open modul keseluruhan (full)** | Hard | Full pre-open feature audit | Full pre-open screen |

**Appendix (not numbered):** kamus bertahap — unlock terms only when the chapter needs them.

---

## Per-chapter content contract

Every chapter CLI path should support:

1. Explain the **generic** IDX problem.  
2. List ML/rule options with reasons and caveats.  
3. Run a **real-data** demo.  
4. Show a short implementation sketch (libs + data flow).  
5. Optionally: `deepdive` linking to `ai-saham` + exportable artifact.

Example:

```text
ml-saham --db … explore broker-flow
ml-saham --db … demo broker-flow --universe LQ45
ml-saham --db … deepdive broker-flow    # optional
```

---

## Libraries (prefer first)

| Area | Prefer | Optional later |
|---|---|---|
| Tabular ML | scikit-learn, LightGBM | XGBoost, CatBoost |
| DataFrame & Vector | polars (for massive panels) | pandas (fallback) |
| Feature Importance | shap | — |
| Time series stats | statsmodels, arch (GARCH) | hmmlearn (HMM) |
| Optimization | cvxpy / scipy, optuna | — |
| NLP | TF-IDF (sklearn) | IndoBERT / transformers |
| Graph ML | networkx | node2vec, PyTorch Geometric |
| Deep learning demos | PyTorch (small) | TabNet |
| Online concepts | river | — |
| Tracking | JSON/CSV logs | MLflow (late chapters) |

---

## Out of scope (product)

- Live trading advice or guaranteed edge.  
- Surveillance / manipulation-detection claims.  
- Algorithm-centric textbook chapter order.  
- Auto-promoting model weights into `ai-saham` (artifacts are human-applied).
