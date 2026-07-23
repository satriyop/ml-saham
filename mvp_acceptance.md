# MVP acceptance — v1

Definition of **done** for the first ship of `ml-saham`.  
Chapters: [chapters.md](./chapters.md) · UX: [ux.md](./ux.md) · Data: [data_contract.md](./data_contract.md) · Arch: [architecture.md](./architecture.md)

**MVP chapters:** 0, 1, 2, 3, 4, 6  
**Out of MVP:** deepdive quality polish, v1.1/phase-2 data tiers, TUI, notebooks, learning-store ETL (unless forced by Ch.4/6 pain).

**Sign-off (Phase 4):** 2026-07-23 — fixture suite green; maintainer DB smoke (`~/dev/ai-saham/data/db/data.db`) for doctor + MVP demos.

---

## Global (all MVP chapters)

- [x] Installable CLI: `ml-saham --help`  
- [x] `--db` / `ML_SAHAM_DB` resolution works  
- [x] `ml-saham doctor` reports MVP data coverage with remediation text  
- [x] `ml-saham chapters` lists MVP path and topic slugs  
- [x] ID-first teaching copy; EN flags/slugs  
- [x] Every `demo` scoreboard shows **biaya banner** + **bukan saran trading/investasi**  
- [x] Default scoreboard long-only vs IHSG where applicable (not Ch.3 toy accuracy-only)  
- [x] `demo` writes artifact pack (manifest + summary + metrics) unless `--no-artifact`  
- [x] No Python imports from `ai-saham` packages  
- [x] No live provider scraping inside `ml-saham`

---

## Per chapter

### Ch.0 — `orientasi`

- [x] `explore orientasi` explains goals, scoreboard, PIT/`fetched_date` warning with a concrete toy example  
- [x] `demo orientasi` (or doctor+status) shows DB connectivity, IHSG presence, universe size, date ranges  
- [x] Deepdive optional / may be stub

### Ch.1 — `clean-prices`

- [x] `explore` covers missing bars / spikes / adjustment mindset + algorithm options  
- [x] `demo` flags anomalies on a real ticker or universe sample (z-score/IQR and/or Isolation Forest)  
- [x] Output: list or count of flagged dates/tickers; artifact metrics

### Ch.2 — `screen-rules`

- [x] `explore` contrasts hand rules vs learned rank  
- [x] `demo` runs a simple rule screen and a tree/logistic alternative on real fundamentals+prices  
- [x] `compare` shows both side by side (names or hit counts)  
- [x] Deepdive may mention risk-gate precursors (optional stub OK)

### Ch.3 — `pattern-fail`

- [x] `explore` frames next-day/pattern as **failure lab** + pointers to later chapters  
- [x] `demo` trains a small model, compares to coin-flip / dumb baseline  
- [x] Explicit on-screen conclusion: wrong question / easy overfit — not “edge found”  
- [x] Pointers to `factor-score`, `broker-flow`, `walk-forward`

### Ch.4 — `factor-score`

- [x] `explore` defines value / momentum / quality (+ optional ownership)  
- [x] `demo` builds z-scored factors, hand blend and at least one of elastic-net / LightGBM  
- [x] Prints top names + rank IC or bucket vs IHSG (gross + banners)  
- [x] `compare equal-weight vs model` works  
- [x] Ownership sleeve soft-skips if shareholding missing

### Ch.6 — `broker-flow`

- [x] `explore` teaches *who* / foreign vs local flow ranking (generic)  
- [x] `demo` builds N-day foreign-net (or z-score) rank; IC or bucket vs IHSG  
- [x] Incremental check vs momentum mentioned or shown  
- [x] Bandar/concentration lab optional; deepdive stub may reference accum/flow score  
- [x] Hard-fails via doctor if broker/foreign tables missing

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

**Status: MVP accepted (Phase 4).** Next ship track: v1.1 (Ch.5, 7, 8) per [roadmap.md](./roadmap.md).
