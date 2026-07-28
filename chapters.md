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
6. Default scoreboard: **long-only vs IHSG** (gross + *belum termasuk biaya* banner). Optional long/short = “cara riset membaca faktor.” Ch.16 uses an **opening-session** scoreboard instead.
7. Ch.6 = *who* (broker / foreign flow rank); Ch.8 = *how much* (volume–price anomaly). No shared ownership of “burst” stories.
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
| **Phase 3 (Advanced)** | 21–36 |

**Evaluation spine:** light honesty in Ch.0 + Ch.3 (train/test, no future peek, coin-flip, biaya banner); full walk-forward in Ch.12.

**Costs:** default gross + banner; optional simple haircut flag; fuller costs in Ch.13.

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

| # | Title (generic problem) | Tier | Implemented Algorithms & Quant Suite | Optional deep-dive → `ai-saham` |
|---|---|---|---|---|
| 0 | **Orientasi** — how we judge “good” without fooling ourselves | — | Baselines (buy & hold, rules), PIT/`fetched_date` checks | Data paths, PIT/`fetched_date` honesty |
| 1 | **Membersihkan harga saham** — missing bars, splits, spikes | Simple | LOF & MAD (default) vs Isolation Forest (compare) | Corp-action break hygiene in caches |
| 2 | **Saring saham dengan aturan** — rules vs learned rank | Simple | LightGBM (default) vs DecisionTree (compare) | Risk-gate *precursors* (fund/liquidity features) |
| 3 | **Mengenali pola harga sederhana** — next-day / pattern **failure lab** | Simple | LightGBM (default) vs 50% coin-flip baseline (compare) | — |
| 4 | **Skor faktor** — value, momentum, quality (+ ownership sleeve) | Medium | LightGBM + SHAP (default) vs ElasticNet/Ridge (compare) | Fundamentals / shareholding caches |
| 5 | **Mengelompokkan saham yang bergerak mirip** — peers / clusters | Medium | HDBSCAN + UMAP (default) vs k-means (compare) | Sector-context diagnostics |
| 6 | **Aliran broker & asing** — *who* ranks from flow | Medium | LightGBM + SHAP (default) vs Logistic/Ridge (compare) | Accum / foreign-flow score components, BCI |
| 7 | **Aktivitas insider** — sparse disclosed insider events | Medium | Logistic Regression (default) vs Insider net shares rule (compare) | Insider enrichment flags |
| 8 | **Memprediksi waktu reaksi harga (Survival Analysis)** — time-to-event | Hard | XGBoost Survival Embeddings (default) vs Kaplan-Meier (compare) | `insider_cache` (waktu hingga profit) |
| 9 | **Volume & lonjakan tidak biasa** — *how much* anomalies | Medium | Autoencoders (default) vs Multivariate IsolationForest (compare) | — |
| 10 | **Membaca berita singkat** — headline tone | Medium | TF-IDF + MultinomialNB vs LogisticRegression + top sentiment vocabulary log-ratios | Sentiment path (when headlines exist) |
| 11 | **Volatilitas & ukuran posisi** — forecast risk for sizing | Medium | GARCH(1,1) Volatility Forecasting (default) vs EWMA (compare) | — |
| 12 | **Rezim pasar** — when the same edge stops working | Hard | Hidden Markov Models (default) vs Gaussian Mixture Model (compare) | Market context / regime engine |
| 13 | **Prediksi multi-fitur + walk-forward** — honest evaluation | Hard | LightGBM (default) vs ElasticNet (compare) + Purged Time-Series Split | Calibrate rule score weights vs forward labels |
| 14 | **Membangun portofolio kecil** — constraints & holdings | Hard | Equal-weight vs Capped-weight vs Hierarchical Risk Parity (HRP) inverse-variance | Risk funnel as filters before sizing |
| 15 | **Peristiwa korporasi massal** — rights, buybacks, index events | Hard | Event study Cumulative Abnormal Return (CAR) vs IHSG market benchmark | Corp-action calendars / events |
| 16 | **Earnings surprise** — miss/beat → short-horizon return | Hard | EPS surprise rank + Ridge Post-Earnings Announcement Drift (PEAD) slope ($\beta_1$) | Earnings cache |
| 17 | **Nowcasting fundamental (Mixed-Frequency)** — fundamental lag | Hard | MIDAS (Mixed-Data Sampling) Regression pada data harian & kuartalan | `company_fundamentals` As-Of Join |
| 18 | **Peringkat menjelang pembukaan** — opening-session ranking | Hard | Pre-open IEV/IEP price imbalance ratio & open-session scoreboard | IEV movers + pre-open screen |
| 19 | **Pipeline riset ujung-ke-ujung** — ingest → model → report | Complex | Feature engineering (Polars) → stacked metrics + Combinatorial Purged CV | Artifact pack (factor-card style) |
| 20 | **Sandbox keputusan berurutan** — sequential allocation under costs | Complex | Multi-armed bandit epsilon-greedy vs random + Policy Shannon Entropy ($H(\pi)$) | — |
| 21 | **Efek musiman & anomali kalender** — seasonality drift | Hard | Kruskal-Wallis ANOVA H-test ($p$-value) + Ridge Calendar Regression | `seasonality_cache` |
| 22 | **Konsensus analis & revisi target harga** — analyst consensus | Hard | Quantile Regression (Q25/Q50/Q75) + Consensus Buy Ratio & Target Upside % | `analyst_cache` |
| 23 | **Akumulasi broker top-N & konsentrasi kepemilikan** — broker accumulation | Hard | Ownership Gini Concentration Index + Top-3 Broker Accumulation Ratio | `broker_distribution_cache` |
| 24 | **Deteksi sindikasi broker (Graph ML)** — coordinated rings | Complex | Node2Vec & Centrality Algorithms pada jaringan transaksi antar broker | `broker_daily_flow` Network |
| 25 | **Partisipasi pasar & rotasi sektor** — sector breadth | Hard | PCA Primary Sector Breadth Factor & Sector Market Participation (> SMA-20) | `factor_card_sector_breadth.py` |
| 26 | **Kompresi volatilitas & klasifikasi breakout** — volatility squeeze | Hard | LSTM / GRU Sequence Modeling (default) vs RandomForest (compare) | `strategies/bb-squeeze` |
| 27 | **Relative strength Mansfield vs IHSG** — relative strength | Hard | Regresi ElasticNet Relative Strength Mansfield vs IHSG Benchmark | `strategies/rs-momentum` |
| 28 | **Skor kualitas akuntansi Piotroski F-Score** — financial quality | Hard | Matriks 9 Sinyal Akuntansi Piotroski F-Score & Regresi Logistik | `company_financials` |
| 29 | **Model kebangkrutan Altman Z-Score** — financial distress | Hard | Emerging Market Altman Z'-Score Model & Isolation Forest Anomaly Filter | `company_financials` |
| 30 | **Klasifikasi breakout awan Kumo Ichimoku** — ichimoku cloud | Hard | RandomForest Kumo Cloud Breakout Classifier pada Tenkan/Kijun/Span A/B | `plugins/indicators/ichimoku.py` |
| 31 | **Klasifikasi sinyal akumulasi broker bandar** — bandar detector | Hard | RandomForest Multi-Window Bandar Accumulation/Distribution Classifier | `bandar_detector` |
| 32 | **Valuasi konsensus Forward P/E & rasio PEG** — forward valuation | Hard | Regresi Ridge Konsensus Forward P/E & Model Rasio PEG Growth | `forward_estimates_cache` |
| 33 | **Notasi khusus bursa, UMA & risiko likuiditas** — special monitoring | Hard | DecisionTree Exchange Notations, UMA Warning & Haircut Tail-Risk Classifier | `ticker_notation_cache` |
| 34 | **Anomali akrual Sloan & kualitas laba** — earnings quality | Hard | Regresi Huber Robust Anomali Akrual Sloan & Kualitas Arus Kas | `company_financials` |
| 35 | **Ilikuiditas & dampak harga mikrostruk** — microstructure impact | Hard | Order Flow Imbalance ML / Hawkes Process (SOTA) vs Bid-Ask Spread (Baseline) | `candles` |
| 36 | **Super learner ensemble multi-faktor terstack** — meta ensemble | Complex | TabNet / Optuna Blended Level-1 Meta-Learner | Multi-factor stacked pipelines |

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
