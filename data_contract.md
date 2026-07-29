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

| Need | Tables (ai-saham) |
|---|---|
| Earnings | `earnings_cache` |
| Corp actions | `corp_action_cache` / `corporate_action_events` (+ dates) |
| IEV / pre-open | `iev_snapshots` (+ sidecars if used by demos) |
| Honest labels | `candidate_observations`, `signal_forward_labels` |
| Headlines | only if a real source exists |

Detail column lists when those chapters are implemented; phase-2 data need not block the MVP roadmap.

---

## PIT / as-of honesty (minimum)

Even with real caches, teach:

1. **`fetched_date` ≠ economic date** for fundamentals / shareholding / analyst-like snapshots.  
2. Demos must print `as_of` (run date or user flag) and, where used, the snapshot date of fundamentals.  
3. Ch.0 explains look-ahead with a tiny concrete example (e.g. using “today’s” PE on a past week).  
4. Broker/flow joins to returns must use **known** session dates only (no future bars).  
5. Ch.18 `pre-open-rank` (later): session clock vs availability — separate from IHSG long-only scoreboard.

Learning-store materialization (later) should add explicit `as_of_date` / `available_at` columns when panels are built — not required to start Direct-mode MVP.

---

## Learning store (when Direct mode is awkward)

Optional SQLite owned by `ml-saham`, e.g. `data/learning.db` or `~/.ml-saham/learning.db`.

Suggested early panels (implement when needed):

| Table | Grain | Role |
|---|---|---|
| `bar` | ticker × date | Cleaned OHLCV + IHSG aligned calendar |
| `cross_section` | ticker × as_of | Factor / flow features for one date |
| `feature_asof` | ticker × as_of × feature | Long features if wide panels hurt |

Population: ETL command e.g. `ml-saham data build-panel --from-db <ai-saham>` (phase when Direct mode is insufficient).

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
