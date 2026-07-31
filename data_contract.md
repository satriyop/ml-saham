# Data contract — `ml-saham`

What data demos expect, how `doctor` validates it, and minimum PIT honesty.  
Architecture: [architecture.md](./architecture.md) · Chapters: [chapters.md](./chapters.md)

Source of ingest: personal **`ai-saham`** DB (real provider data).  
`ml-saham` is read-only on that DB unless materializing a **learning store**.

Default path assumption: `~/dev/ai-saham/data/db/data.db` (override with `--db` / `ML_SAHAM_DB`).

---

## Data tiers (by ship phase)

| Tier | Ship phase | Purpose |
|---|---|---|
| **MVP data** | MVP (Ch.0,1,2,3,4,6) | Prices, fundamentals, broker/foreign flow, sector, IHSG |
| **v1.1 data** | v1.1 (Ch.5,7,9) | + insider, fuller sector usage |
| **Phase-2 data** | Phase 2 | + earnings, corp actions, IEV/pre-open, labels/observations, headlines if any |

`doctor` reports each tier as: **ok** / **partial** / **missing** with table-level detail.

---

## MVP data — required for first demos

Logical requirements (map to `ai-saham` table names below). Counts are guidance, not hard CI gates.

### Tables & columns

| Logical need | `ai-saham` table | Required columns (min) | Notes |
|---|---|---|---|
| OHLCV | `candles` | `ticker`, `date`, `open`, `high`, `low`, `close`, `volume` | Prefer `source` aware; adjustment policy if present |
| Benchmark | `candles` where `ticker='IHSG'` | same | Scoreboard; session calendar proxy |
| Fundamentals | `company_fundamentals` | `ticker`, `fetched_date`, `pe_ratio_ttm`, `roe_ttm`, `pbv`, `dividend_yield`, `market_cap_idr` | Snapshot semantics |
| Sector meta | `stock_meta` and/or `ticker_notation_cache` | `ticker`, sector-like field | Use best available |
| Broker day summary | `broker_summaries` | `ticker`, `date`, `foreign_buy_value`, `foreign_sell_value`, `foreign_buy_lot`, `foreign_sell_lot`, `total_value` | Foreign nets |
| Top brokers (optional enrich) | `broker_summaries.top_buyers_json` / `top_sellers_json` | JSON with `broker_code`, `broker_type` | foreign/local when present |
| Foreign flow series | `foreign_flow_points` | `ticker`, `date`, `net_val`, `net_lot`, `source` | Ch.6 |
| Shareholding | `shareholding_composition` | `ticker`, `fetched_date`, `institution_pct`, `individual_pct` | Ch.4 ownership sleeve |
| Broker-by-broker (optional Ch.6 depth) | `broker_daily_flow` | `ticker`, `date`, `broker_code`, `net_value` or nets | Soft requirement for MVP |

### Universe

- Default demo universe: intersection of configured LQ45-like list ∩ tickers present in `candles` with enough history.  
- `doctor` should print: ticker count, date min/max for candles & broker_summaries, whether IHSG exists.

### Soft vs hard failures

| Missing | Demo behavior |
|---|---|
| `candles` or IHSG | **Hard fail** → point to `saham fetch market` |
| `broker_summaries` / `foreign_flow_points` | **Hard fail** for `broker-flow`; others may run |
| `company_fundamentals` | **Hard fail** for `factor-score`; Ch.1–3 may run |
| `shareholding_composition` | Soft: skip ownership sleeve with warning |
| `broker_daily_flow` | Soft: skip concentration lab |

---

## v1.1 data

| Need | Table | Min columns |
|---|---|---|
| Insider | `insider_cache` | `ticker`, `transaction_date`, `action_type`, `shares`, `role`, `fetched_date` |
| Sector panel | `stock_meta` / notation | enough distinct sectors for clustering |

Scrub absurd dates (e.g. year 1970) in chapter adapters; warn in `doctor`.

---

## Phase-2 data (summary)

| Need | Where it lives | Tables / outputs |
|---|---|---|
| Earnings | **ai-saham** ingest | `earnings_cache` |
| Corp actions | **ai-saham** ingest | `corp_action_cache` / `corporate_action_events` |
| IEV / pre-open ranks | **ai-saham** ingest | `iev_snapshots`, prefer `iev_snapshot_history` |
| Decisions / captures | **ai-saham** corpus | **`learning_observations`** |
| Corpus outcome labels | **ai-saham** corpus | **`learning_outcome_labels`** |
| Cohort evaluations | **ai-saham** research loop | **`learning_evaluations`** (optional for ml-saham demos) |
| Headlines | **ai-saham** if a real source exists | (table name varies) |
| Challenge evaluation labels | **Protocol-owned in ml-saham** (not written back to ai-saham) | Built from `candles` and/or **joined** corpus labels → panel in-memory / artifacts / optional learning store |

Detail: [§ Label ownership](#label-ownership-ingest-vs-challenge) · [§ Learning corpus](#learning-corpus-ai-saham-live).  
Phase-2 soft tables need not block MVP demos; **challenge** needs observations + candles (see [docs/challenge_product.md](./docs/challenge_product.md)).

### Retired / do not reintroduce

These names appear in older notes or fixtures only. **Live ai-saham does not use them as the observation/label plane.** Do not teach agents to require them for challenge or new features:

| Dead / legacy name | Replaced by (ai-saham corpus) |
|---|---|
| `candidate_observations` | `learning_observations` (`decision_payload_json`, `purpose`, …) |
| `signal_forward_labels` | `learning_outcome_labels` (ai-saham research/label contracts) |

Do **not** treat “honest labels for challenge” as a reason to recreate those dead tables inside ml-saham. Challenge labels are protocol-owned (next section).

Curriculum labs soft-read **`learning_outcome_labels`** (canonical). A soft fallback to retired `signal_forward_labels` exists only if the corpus table is empty (old fixtures).

---

## Label ownership (ingest vs challenge)

Two different “label” ideas — **do not merge ownership**.

| Kind | Owner | Stored where | Written by |
|---|---|---|---|
| **Ingest / corpus labels** | **ai-saham** | Always ai-saham SQLite: `learning_outcome_labels` (+ related research tables) | ai-saham `research <scenario> labels` / evaluate pipeline |
| **Challenge evaluation labels** | **ml-saham Protocol** | **Not** written into ai-saham. Exist as panel fields in-memory during `challenge run` / `engine`; may be summarized in **artifacts** (`./artifacts/…`) or an **optional ml-saham learning store** | ml-saham challenge only |

### Ingest / corpus labels (ai-saham only)

- Path contracts such as `price_path.open_30m.v1`, `price_path.accum_10d.v1` live in **`learning_outcome_labels`**.  
- Observations they attach to live in **`learning_observations`**.  
- ml-saham is **read-only** on this plane.  
- Never invent parallel `candidate_observations` / `signal_forward_labels` tables in ml-saham “for honesty.”

### Challenge evaluation labels (protocol-owned)

ADR-002 panels need a **y** for rank IC under a fixed protocol. That **y** is built at challenge time:

| Protocol family | How evaluation labels are built (read-only inputs) | Primary store of the result |
|---|---|---|
| `accum_path_v1` | Excess close→close vs IHSG from **`candles`** @ H=3/10/20 (primary **10**) | Challenge panel / artifact metrics — **not** ai-saham tables |
| `pre_open_session_v1` | Same-session open→close excess vs IHSG from **`candles`**, and/or **join** `learning_outcome_labels` when available | Same |

Rules:

1. Challenge **reads** ai-saham corpus labels when useful (join on `observation_id`); it does **not** upsert them.  
2. Challenge **computes** protocol returns from **`candles`** when that is the protocol contract (especially accum multi-horizon).  
3. Challenge **writes** only to ml-saham surfaces: terminal report, `--export-json` / `--export-md`, `artifacts/challenge/…`, and later optional `data/learning.db` / `~/.ml-saham/learning.db` materializations.  
4. **No auto-promote** of weights/labels into ai-saham configs or corpus tables.

```text
ai-saham                          ml-saham challenge
────────                          ──────────────────
learning_observations  ──read──►  features / scores
learning_outcome_labels ─read──►  optional y (join)
candles (+ IHSG)         ─read──►  protocol y (excess / open-close)
                                  │
                                  └── write → artifacts / exports
                                              (optional learning store)
                                  never write → ai-saham SQLite
```

---

## Learning corpus (ai-saham live)

**ai-saham-owned** store for research captures and corpus outcomes. Challenge **reads** these; it does not own them.

### `learning_observations`

| Column (min) | Role |
|---|---|
| `purpose` | e.g. `ACCUMULATION_DISCOVERY`, `PRE_OPEN_AUCTION_DIRECTION` |
| `captured_at` | Capture time (ordering / dedupe) |
| `decision_payload_json` | Full decision JSON (components, scores, ticker, dates) |
| `observation_id` | Identity for join to corpus outcomes (when column present) |
| `compatibility_id` | Semantic cohort / rulebook stamp (ai-saham material-config hash) |

**Read by challenge for features / scores:**

| Purpose | Policy / surface |
|---|---|
| `ACCUMULATION_DISCOVERY` (and ACCUM*) | `screener.accum.score_weights` |
| `PRE_OPEN_AUCTION_DIRECTION` | `screener.pre_open.directional_score` |

**Single-cohort discipline (all readers):** when `compatibility_id` is present, **challenge panels, curriculum chapters, and doctor notes** load or report **exactly one** cohort per purpose family — never pool mixed rulebooks. Implementation: `ml_saham.data.observation_cohort` (`fetch_accum_observation_raw`, `fetch_pre_open_observation_raw`, `curriculum_payload_rows`). Default: largest `n` (ties → newest `max(captured_at)`). Explicit override via `preferred_compatibility_id` / panel `compatibility_id=`. Notes always record the selected id and excluded cohort sizes. Fixtures without the column keep the legacy unfiltered path. MVP fixture ships two ACCUM cohorts so CI proves non-mixing.

### `learning_outcome_labels` (corpus labels)

| Column (min) | Role |
|---|---|
| `observation_id` | Join key → observation |
| `contract_id` | e.g. `price_path.open_30m.v1`, `price_path.accum_10d.v1` |
| `outcome` / `availability` | SUCCESS/FAILURE/… + AVAILABLE |
| `metrics_json` | Path metrics (e.g. open_to_close_return_pct) |
| `labeled_at` | Label time |

Owned by **ai-saham** ingest/research. Challenge may **join** for protocol **y** (e.g. pre-open directional); accum ADR-002 primarily uses **`candles`** excess for evaluation labels (protocol-owned computation).

### `learning_evaluations`

Historical / optional rows from ai-saham `research <scenario> evaluate`.

**Accum product decision (2026-07-29):** ai-saham **dropped** accum cohort evaluate as a required pipeline step. Challenge **must not** depend on ACCUM `learning_evaluations`. Doctor may report table presence only (soft). See [BOUNDARY.md](./BOUNDARY.md).

Pre-open may still write evaluations in ai-saham; still not an input to ADR-002 panels unless a protocol explicitly says so.

### Related caches (inputs, not label stores)

| Table | Role |
|---|---|
| `candles` (+ IHSG) | Raw prices for **protocol-owned** challenge evaluation labels |
| `iev_snapshots` / `iev_snapshot_history` | Pre-open IEV rank **features** (not learning_observations) |

---

## PIT / as-of honesty (minimum)

Even with real caches, teach:

1. **`fetched_date` ≠ economic date** for fundamentals / shareholding / analyst-like snapshots.  
2. Demos must print `as_of` (run date or user flag) and, where used, the snapshot date of fundamentals.  
3. Ch.0 explains look-ahead with a tiny concrete example (e.g. using “today’s” PE on a past week).  
4. Broker/flow joins to returns must use **known** session dates only (no future bars).  
5. Pre-open: IEV / observation timestamps are pre-open; labels use **that session’s** open→close (or outcome contract) — separate from multi-day H=10 close excess.  
6. Observation `captured_at` / payload `snapshot_date` / `session_date` must not be confused with label availability (`learning_outcome_labels.labeled_at`).

### Product challenge extract contracts (regression-tested)

Guarded by golden fixtures in `tests/fixtures/golden/` + `tests/test_challenge_payload_contracts.py` (not fixture-only schemas).

| Panel | Score / feature path | Label / capture invariant | Units |
|-------|----------------------|---------------------------|--------|
| Accum sleeves | `features_by_window.<w>.candidate.accum_score_breakdown` | H=3/10/20 excess vs IHSG (same horizons) | sleeve points |
| Signal | `features_by_window.<w>.signal` → `raw_exact_score` / `assessment.score` (top-level `signal.raw_score` = legacy only) | same H=10 path as accum | score 0–100-ish |
| Risk hard gates | `features_by_window.<w>.trade_setup.blocking_gates` / `action` (top-level `trade_setup` = legacy only) | same H=10 excess; metric = mean excess among allowed | gate fire 0/1 |
| Pre-open directional | observation features | Prefer open→09:30 stock (**gross**); else open→close − IHSG open→close. **Never** open→09:30 − full-day IHSG | `*_return_pct` = **percent points** (always ÷100) |
| IEV rank | official rank; challengers `log_iev`, `iev`, `iep` — **not** `iev/iep` | Prefer `is_ncp_locked` / clock **[08:45, 09:00)** over largest post-open batch | IEV=volume, IEP=price |
| Verdict | — | **WIN needs ≥2 valid OOS folds**; single-fold edge = provisional `INCONCLUSIVE` | — |

Learning-store materialization (later) should add explicit `as_of_date` / `available_at` columns when panels are built — not required to start Direct-mode MVP.

---

## Learning store (when Direct mode is awkward)

Optional SQLite **owned by `ml-saham`**, e.g. `data/learning.db` or `~/.ml-saham/learning.db`.

This is a place for **materialized challenge/curriculum panels** (including protocol evaluation labels and features), **not** a second copy of ai-saham’s corpus. It must not replace `learning_observations` / `learning_outcome_labels` as the system of record for decisions/outcomes.

Suggested early panels (implement when needed):

| Table | Grain | Role |
|---|---|---|
| `bar` | ticker × date | Cleaned OHLCV + IHSG aligned calendar |
| `cross_section` | ticker × as_of | Factor / flow features for one date |
| `feature_asof` | ticker × as_of × feature | Long features if wide panels hurt |

Population: ETL command e.g. `ml-saham data build-panel --from-db <ai-saham>` (phase when Direct mode is insufficient). Write path: **ml-saham only**.

---

## Challenge product data plane (short)

| Read from ai-saham | Write from ml-saham challenge |
|---|---|
| `learning_observations`, `learning_outcome_labels` (optional join), `candles`, `iev_*`, … | Artifacts, exports, optional learning store |
| Never required: `candidate_observations`, `signal_forward_labels` | Never write challenge **y** or policy verdicts into ai-saham |

See [docs/challenge_product.md](./docs/challenge_product.md).

---

## `doctor` output contract

```text
DB: /path/to/data.db
MVP data: ok|partial|missing
  candles          ok  tickers=N  range=YYYY-MM-DD..YYYY-MM-DD
  IHSG             ok|missing
  fundamentals     …
  broker_summaries …
  foreign_flow     …
  shareholding     …
v1.1 data: …
Phase-2 data: …
Universe default: … (N tickers)
Remediation: …
```

Exit code non-zero if the **active command’s required data tier** is not satisfiable.

---

## Non-goals

- Guaranteeing multi-year history (current ~1y personal DB is enough for learning)  
- Rebuilding Stockbit auth inside `ml-saham`  
- Shipping redistributable market dumps
