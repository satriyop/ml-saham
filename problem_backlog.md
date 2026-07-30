# Problem backlog — not yet in chapters

Ideas that are **not** scheduled in [chapters.md](./chapters.md).  
Keep this list small. Promote only with a generic IDX problem statement (then curriculum `explore` / product `challenge` as needed).

Discussion context: early drafts in local `archive/` (gitignored).

---

## Explicitly deferred / out (do not schedule without revisiting)

| Idea | Why parked |
|---|---|
| Support / break probability as a main chapter | Fights Ch.3 “wrong question”; OK only as anti-pattern inside Ch.3 |
| Seasonality as a main ML chapter | Calendar superstition risk; Ch.3 anti-pattern at most |
| Analyst consensus as its own chapter | Herding misuse; optional aside inside Ch.4 / Ch.10 only |
| Alt-data fusion | Needs a real alt-data commitment first |
| Market-wide stress / scenario generators | Niche vs learner arc; maybe after Ch.11 someday |
| Near-real-time streaming feature store | Systems problem beyond session open-ranking (Ch.18) |
| Uneven-liquidity multi-task / transfer learning | Too niche for this learner arc |
| Public dataset shipping | Personal-learning product; not a redistribution goal |

---

## Optional extensions (attached to an existing chapter — not new chapters yet)

| Idea | Park under | Notes |
|---|---|---|
| Full tick / order-book microstructure | **Ch.18** | Only if richer tape exists; opening-session ranking stays the headline |
| Setup-gate / phase-detector threshold sweeps | **Ch.12** compare / notes | Research-card style; not a TA chapter |
| Tracked “smart/noise” broker list quality | **Ch.6** lab | List hygiene + caveats; not smart-money mythology |

---

## Candidate problems (from ai-saham factor inventory)

See also: [docs/engine_factor_map.md](./docs/engine_factor_map.md).

| Idea | Tier | Why | Data | Slot |
|---|---|---|---|---|
| **Sector macro context** (routed macros per sector group; ADR-053) | Hard | Distinct from peer breadth; may become score input later | macro series + sector group map; fingerprints `smc_*` | New challenge slug `sector-macro` under `market_context` when ready |
| Insider as **policy / gate** input | Medium | Already a curriculum chapter; SignalEngine penalties | `insider_cache` | Add PolicySpec or gate track if scoring uses insider heavily |
| Setup phase / readiness | Hard | Swing lens / phase gates | observation labels | Deepdive / later slug — not scheduled |
| Source-field / reconciliation DQ | Medium | Trust of caches | DQ tables / contracts | Prefer `data-integrity` + doctor (shipped Ch.45) |

When promoting a candidate, write:

1. **Generic problem** (one sentence, IDX).  
2. **Tier** (Simple / Medium / Hard / Complex).  
3. **Why ML helps.**  
4. **Data needed** (and whether `ai-saham` already has it).  
5. **Suggested chapter slot** or “new chapter.”  
6. **Optional `ai-saham` surface note** (engine/table) — never the title.
