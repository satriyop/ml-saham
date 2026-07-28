# ml-saham

CLI kursus **machine learning problem-centric** untuk pasar saham Indonesia (IDX).  
Personal learning — data real dari SQLite `ai-saham` milikmu.

Desain: [chapters.md](./chapters.md) · [ux.md](./ux.md) · [roadmap.md](./roadmap.md)

## Setup

```bash
cd ~/dev/ml-saham
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Database

Default: `~/dev/ai-saham/data/db/data.db`

```bash
export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db
# atau
ml-saham --db ~/dev/ai-saham/data/db/data.db doctor
```

Isi data lewat `ai-saham` (`saham fetch market`, dll). `ml-saham` tidak scrape provider.

## Perintah utama

```bash
ml-saham chapters          # jalur MVP + progress
ml-saham chapters --all
ml-saham status
ml-saham doctor
ml-saham explore orientasi --no-pager
ml-saham demo orientasi
ml-saham demo clean-prices
ml-saham demo screen-rules
ml-saham compare screen-rules --baseline hand --against tree
ml-saham demo pattern-fail
ml-saham demo factor-score
ml-saham compare factor-score --baseline equal-weight --against elastic-net
ml-saham demo broker-flow
ml-saham demo cluster-peers
ml-saham demo insider
ml-saham demo volume-anomaly
ml-saham deepdive broker-flow
```

Acceptance: [mvp_acceptance.md](./mvp_acceptance.md) · [v1_1_acceptance.md](./v1_1_acceptance.md)

Butuh: `pip install -e .` (pandas + scikit-learn). LightGBM opsional: `pip install -e ".[ml]"`.

Progress: `~/.ml-saham/progress.json` (override `ML_SAHAM_HOME`).  
Artifact root: `./artifacts` atau `ML_SAHAM_ARTIFACTS` / `--artifacts-dir`.

## Status implementasi

| Phase | Isi | Status |
|---|---|---|
| 0 | Scaffold CLI + registry + DB resolve | **done** |
| 1 | Doctor tabel MVP + loaders + universe | **done** |
| 2 | Metrics + artifacts + explore pager | **done** |
| 3 | Chapter 0, 1, 2, 3, 4, 6 | **done** |
| 4 | MVP harden / sign-off | **done** |
| 5 | v1.1 chapters 5, 7, 8 | **done** |
| 6 | Phase-2 curriculum 9–17 (+18) | **done** |
| 7 | Fitur Algoritma & Performa Suite ML | **done** |

## Algoritma ML & Performa Dataplane

- **Dataplane Bebas N+1 Query & Aman SQL**: Resolusi universe menggunakan `GROUP BY` batch query 1x ke SQLite. Semua pengaksesan nama tabel/kolom dinamis divalidasi regex `[a-zA-Z0-9_]+` terhadap injeksi SQL.
- **Vektor & In-Memory Efficiency**: Pengolahan z-score dan filtering rentang tanggal (`end=as_of`) dioptimalkan dengan NumPy & query tanggal langsung di SQLite.
- **Quant ML Suite per Chapter**:
  - **Ch.1 clean-prices**: IQR + Isolation Forest + CUSUM Change-Point Detection.
  - **Ch.2 screen-rules**: DecisionTree feature importances & rules threshold.
  - **Ch.3 pattern-fail**: Uji signifikansi statistik Binomial Z-test ($p$-value) vs coin-flip baseline.
  - **Ch.4 factor-score**: Bobot koefisien fitur (`ElasticNet.coef_` & `Ridge`).
  - **Ch.5 cluster-peers**: Silhouette Score & Davies-Bouldin Index untuk evaluasi kluster.
  - **Ch.6 broker-flow**: Model regresi inkremental net flow asing vs price momentum.
  - **Ch.7 insider**: Koefisien Logistic Regression pada tipe transaksi insider (BUY/SELL).
  - **Ch.8 volume-anomaly**: IsolationForest vs One-Class SVM anomaly overlap.
  - **Ch.9 headline-tone**: Ekstraksi token TF-IDF & log-ratio MultinomialNB.
  - **Ch.10 volatility-sizing**: EWMA ($\lambda=0.94$) volatility forecasting & risk-targeted position sizing.
  - **Ch.11 market-regime**: State GMM terurut (Bearish, Neutral, Bullish) + probabilitas posterior.
  - **Ch.12 walk-forward**: Purged Time-Series Split ($H=5$ days gap) pencegah target leakage.
  - **Ch.13 portfolio-small**: Hierarchical Risk Parity (HRP) / inverse-variance asset allocation.
  - **Ch.14 corp-events**: Event study Cumulative Abnormal Return (CAR) vs IHSG.
  - **Ch.15 earnings-surprise**: Estimasi slope drift PEAD ($\beta_1$) & $R^2$.
  - **Ch.16 pre-open-rank**: Prediksi ketidakseimbangan order book pre-open (IEV vs IEP).
  - **Ch.17 research-pipeline**: Combinatorial Purged CV & Probability of Overfitting ($P_{\text{CSCV}}$).
  - **Ch.18 rl-sandbox**: Policy Shannon Entropy ($H(\pi)$) & tracking distribusi aksi bandit.
  - **Ch.19 seasonality-drift**: Uji ANOVA Kruskal-Wallis (p-value) & Regresi Ridge Anomali Musiman Kalender.
  - **Ch.20 analyst-consensus**: Regresi Kuantil Target Upside Analis & Consensus Buy Ratio.
  - **Ch.21 broker-accumulation**: Indeks Gini Konsentrasi Kepemilikan & Top-3 Broker Accumulation Ratio.
  - **Ch.22 sector-breadth**: PCA Primary Sector Breadth Factor & Partisipasi Sektor (> SMA-20).
  - **Ch.23 volatility-squeeze**: RandomForest Breakout Classifier pada Bollinger Bandwidth Squeeze & Surge Volume Ratio.
  - **Ch.24 relative-strength**: Regresi ElasticNet Relative Strength Mansfield vs IHSG Benchmark.
  - **Ch.25 financial-quality**: Matriks 9 Sinyal Akuntansi Piotroski F-Score & Regresi Logistik Kualitas Laporan Keuangan.
  - **Ch.26 financial-distress**: Emerging Market Altman Z'-Score Bankruptcy Model & Isolation Forest Anomaly Filter.
  - **Ch.27 ichimoku-cloud**: RandomForest Kumo Cloud Breakout Classifier pada Tenkan/Kijun/Span A/B.
  - **Ch.28 bandar-detector**: RandomForest Multi-Window Bandar Accumulation/Distribution Classifier.
  - **Ch.29 forward-valuation**: Regresi Ridge Konsensus Forward P/E & Model Rasio PEG Growth.
  - **Ch.30 special-monitoring**: DecisionTree Exchange Notations, UMA Warning & Haircut Tail-Risk Classifier.
  - **Ch.31 earnings-quality**: Regresi Huber Robust Anomali Akrual Sloan & Kualitas Arus Kas.
  - **Ch.32 microstructure-impact**: Model SVR Dampak Harga & Rasio Ilikuiditas Amihud.
  - **Ch.33 meta-ensemble**: Stacked Super Learner Multi-Faktor (Level-1 Ridge Ensemble).

## Catatan

Bukan saran trading/investasi. Skorboard demo default long-only vs IHSG (gross + banner biaya) — lihat desain di repo.

