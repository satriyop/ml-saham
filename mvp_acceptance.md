# MVP acceptance — v1

Definition of **done** for the first ship of `ml-saham`.  
Chapters: [chapters.md](./chapters.md) · UX: [ux.md](./ux.md) · Data: [data_contract.md](./data_contract.md) · Arch: [architecture.md](./architecture.md)

**MVP chapters:** 0, 1, 2, 3, 4, 6  
**Out of MVP:** deepdive quality polish, v1.1/phase-2 data tiers, TUI, notebooks, learning-store ETL (unless forced by Ch.4/6 pain).

---

## Global (all MVP chapters)

- [ ] Installable CLI: `ml-saham --help`  
- [ ] `--db` / `ML_SAHAM_DB` resolution works  
- [ ] `ml-saham doctor` reports MVP data coverage with remediation text  
- [ ] `ml-saham chapters` lists MVP path and topic slugs  
- [ ] ID-first teaching copy; EN flags/slugs  
- [ ] Every `demo` scoreboard shows **biaya banner** + **bukan saran trading/investasi**  
- [ ] Default scoreboard long-only vs IHSG where applicable (not Ch.3 toy accuracy-only)  
- [ ] `demo` writes artifact pack (manifest + summary + metrics) unless `--no-artifact`  
- [ ] No Python imports from `ai-saham` packages  
- [ ] No live provider scraping inside `ml-saham`

---

## Per chapter

### Ch.0 — `orientasi`

- [ ] `explore orientasi` explains goals, scoreboard, PIT/`fetched_date` warning with a concrete toy example  
- [ ] `demo orientasi` (or doctor+status) shows DB connectivity, IHSG presence, universe size, date ranges  
- [ ] Deepdive optional / may be stub

### Ch.1 — `clean-prices`

- [ ] `explore` covers missing bars / spikes / adjustment mindset + algorithm options  
- [ ] `demo` flags anomalies on a real ticker or universe sample (z-score/IQR and/or Isolation Forest)  
- [ ] Output: list or count of flagged dates/tickers; artifact metrics

### Ch.2 — `screen-rules`

- [ ] `explore` contrasts hand rules vs learned rank  
- [ ] `demo` runs a simple rule screen and a tree/logistic alternative on real fundamentals+prices  
- [ ] `compare` shows both side by side (names or hit counts)  
- [ ] Deepdive may mention risk-gate precursors (optional stub OK)

### Ch.3 — `pattern-fail`

- [ ] `explore` frames next-day/pattern as **failure lab** + pointers to later chapters  
- [ ] `demo` trains a small model, compares to coin-flip / dumb baseline  
- [ ] Explicit on-screen conclusion: wrong question / easy overfit — not “edge found”  
- [ ] Pointers to `factor-score`, `broker-flow`, `walk-forward`

### Ch.4 — `factor-score`

- [ ] `explore` defines value / momentum / quality (+ optional ownership)  
- [ ] `demo` builds z-scored factors, hand blend and at least one of elastic-net / LightGBM  
- [ ] Prints top names + rank IC or bucket vs IHSG (gross + banners)  
- [ ] `compare equal-weight vs model` works  
- [ ] Ownership sleeve soft-skips if shareholding missing

### Ch.6 — `broker-flow`

- [ ] `explore` teaches *who* / foreign vs local flow ranking (generic)  
- [ ] `demo` builds N-day foreign-net (or z-score) rank; IC or bucket vs IHSG  
- [ ] Incremental check vs momentum mentioned or shown  
- [ ] Bandar/concentration lab optional; deepdive stub may reference accum/flow score  
- [ ] Hard-fails via doctor if broker/foreign tables missing

---

## Explicitly not required for MVP done

- Polished `deepdive` suggestions.md quality  
- Ch.5/7/8 and later  
- Learning DB materialization CLI  
- `--plot` images  
- Progress file sophistication beyond basic marks  
- Parity with all `ai-saham` engine knobs  

---

## Sign-off

MVP is accepted when all Global checks and all Per-chapter checks above are checked on the maintainer’s real `ai-saham` DB path.
