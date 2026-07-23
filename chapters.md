# Chapters — ML Learning CLI (IDX)

Final curriculum for `ml-saham`: problem-centric, IDX-only, personal self-teaching with **real** market data.

Related discussion log (keep until frozen): [chapter_proposal.md](./chapter_proposal.md)  
Original intent: [specs.md](./specs.md)  
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
| **v1.1** | 5, 7, 8 |
| **Phase 2** | 9–17 |
| **Optional appendix** | 18 (RL) |

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

| # | Title (generic problem) | Tier | Algorithms (intro) | Optional deep-dive → `ai-saham` |
|---|---|---|---|---|
| 0 | **Orientasi** — how we judge “good” without fooling ourselves | — | Baselines (buy & hold, rules) | Data paths, PIT/`fetched_date` honesty |
| 1 | **Membersihkan harga saham** — missing bars, splits, spikes | Simple | z-score / IQR → Isolation Forest, LOF; change-point | Corp-action break hygiene in caches |
| 2 | **Saring saham dengan aturan** — rules vs learned rank | Simple | Rules → decision tree, logistic | Risk-gate *precursors* (fund/liquidity features) |
| 3 | **Mengenali pola harga sederhana** — next-day / pattern **failure lab** | Simple | k-NN, tree, forest vs coin-flip; pointer to better framing | — |
| 4 | **Skor faktor** — value, momentum, quality (+ ownership sleeve) | Medium | Hand weights → elastic net → LightGBM | Fundamentals / shareholding caches |
| 5 | **Mengelompokkan saham yang bergerak mirip** — peers / clusters | Medium | k-means, hierarchical clustering, PCA | Sector-context diagnostics |
| 6 | **Aliran broker & asing** — *who* ranks from flow | Medium | Flow rules → elastic net / logistic → LightGBM + momentum; bandar lab | Accum / foreign-flow score components, BCI |
| 7 | **Aktivitas insider** — sparse disclosed insider events | Medium | Rules → logistic / GBDT | Insider enrichment flags |
| 8 | **Volume & lonjakan tidak biasa** — *how much* anomalies | Medium | Isolation Forest, One-Class SVM (price/volume only) | — |
| 9 | **Membaca berita singkat** — headline tone | Medium | TF-IDF + naive Bayes / logistic → small IndoBERT | Sentiment path (when headlines exist) |
| 10 | **Volatilitas & ukuran posisi** — forecast risk for sizing | Medium | GARCH vs GBDT / RF; liquidity/spread inputs | — |
| 11 | **Rezim pasar** — when the same edge stops working | Hard | HMM, GMM, change-point + classifier; breadth / foreign / macro-style features | Market context / regime engine |
| 12 | **Prediksi multi-fitur + walk-forward** — honest evaluation | Hard | LightGBM / XGBoost; leakage demos; label corpus | Calibrate rule score weights vs forward labels; regime-stratified checks |
| 13 | **Membangun portofolio kecil** — constraints & holdings | Hard | Scores + constrained optimization | Risk funnel as filters before sizing |
| 14 | **Peristiwa korporasi massal** — rights, buybacks, index events | Hard | GBDT event models; intro causal forest | Corp-action calendars / events |
| 15 | **Earnings surprise** — miss/beat → short-horizon return | Hard | Linear / GBDT; PIT dates | Earnings cache |
| 16 | **Peringkat menjelang pembukaan** — opening-session ranking | Hard | Rank/classify pre-open features; session scoreboard | IEV movers + pre-open screen |
| 17 | **Pipeline riset ujung-ke-ujung** — ingest → model → report | Complex | Stacking / ensemble + experiment tracking | Artifact pack (factor-card style; human-applied) |
| 18 | **Sandbox keputusan berurutan** — sequential allocation under costs | Complex | **Optional appendix:** bandits → toy RL (PPO / DQN) | — |

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
| Tabular ML | scikit-learn | — |
| Gradient boosting | LightGBM | XGBoost, CatBoost |
| Time series stats | statsmodels | — |
| Optimization | cvxpy / scipy | — |
| NLP | TF-IDF (sklearn) | IndoBERT / transformers |
| Deep learning demos | PyTorch (small) | — |
| Online concepts | river | — |
| Tracking | JSON/CSV logs | MLflow (late chapters) |

---

## Out of scope (product)

- Live trading advice or guaranteed edge.  
- Surveillance / manipulation-detection claims.  
- Algorithm-centric textbook chapter order.  
- Auto-promoting model weights into `ai-saham` (artifacts are human-applied).
