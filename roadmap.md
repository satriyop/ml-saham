# Roadmap — `ml-saham`

Build order for the personal IDX ML learning CLI.  
Locked design: [chapters.md](./chapters.md) · [ux.md](./ux.md) · [architecture.md](./architecture.md) · [data_contract.md](./data_contract.md) · [artifacts.md](./artifacts.md) · [mvp_acceptance.md](./mvp_acceptance.md)

Early drafts (local only): `archive/` (gitignored).

---

## North star

Ship a Typer CLI that teaches problem-centric ML on **real** personal market data (via `ai-saham` SQLite), with optional deep-dives/artifacts for tuning `ai-saham` — starting with MVP chapters **0, 1, 2, 3, 4, 6**.

---

## Phase 0 — Scaffold (week 1)

**Goal:** empty app that installs, resolves DB, and fails honestly.

| # | Milestone | Done when |
|---|---|---|
| 0.1 | Python package | `pyproject.toml`, `src/ml_saham/`, console script `ml-saham` |
| 0.2 | Typer app shell | `ml-saham --help` lists `chapters`, `explore`, `demo`, `compare`, `deepdive`, `glossary`, `doctor` (stubs OK) |
| 0.3 | DB resolution | `--db` / `ML_SAHAM_DB` / default `~/dev/ai-saham/data/db/data.db` |
| 0.4 | Chapter registry | Topic slugs from [ux.md](./ux.md) registered; MVP marked |
| 0.5 | Progress stub | `~/.ml-saham/progress.json` create/read |
| 0.6 | README | How to install, point `--db`, run `doctor` |

**Exit:** `pip install -e .` && `ml-saham chapters` prints MVP list.

---

## Phase 1 — Data plane + doctor (week 1–2)

**Goal:** MVP-table visibility before any ML demo.

| # | Milestone | Done when |
|---|---|---|
| 1.1 | Read-only SQLite access | Helpers that load MVP tables listed in [data_contract.md](./data_contract.md) (`candles`, fundamentals, broker/foreign flow, …) |
| 1.2 | `doctor` for MVP data | Table-level ok/partial/missing + date ranges + IHSG + remediation text |
| 1.3 | Universe helper | LQ45-like ∩ cached tickers; printable count |
| 1.4 | Fixture SQLite (tiny) | Unit tests for doctor without needing full personal DB |
| 1.5 | Scoreboard + banners | Shared renderer: long-only vs IHSG stub + biaya + bukan-saran |

**Exit:** `ml-saham doctor` green on maintainer DB; non-zero exit when MVP hard-deps missing.

---

## Phase 2 — Shared eval + artifacts (week 2)

**Goal:** every later demo can emit the same honesty/artifact frame.

| # | Milestone | Done when |
|---|---|---|
| 2.1 | Metrics | Rank IC, simple bucket/top-quantile return helper |
| 2.2 | Costs flag | `--with-costs` optional haircut; default gross + banner |
| 2.3 | Artifact writer | `manifest.json` + `summary.md` + `metrics.json` per [artifacts.md](./artifacts.md) |
| 2.4 | CLI wiring | `demo`/`compare` write artifacts unless `--no-artifact` |
| 2.5 | Explore pager | Paged `explore` output; `--no-pager`; `--verbose` |

**Exit:** a throwaway stub chapter can `demo` → artifact folder with valid manifest.

---

## Phase 3 — MVP chapters (week 2–5)

Implement in order (dependencies + pedagogy). Each chapter: `explore` + `demo` (+ `compare` where noted) meeting [mvp_acceptance.md](./mvp_acceptance.md). Deepdive may be stub.

| Order | Topic | Chapter | Focus tickets |
|---|---|---|---|
| 3.1 | `orientasi` | 0 | Goals, PIT story, doctor/status demo |
| 3.2 | `clean-prices` | 1 | z-score/IQR ± Isolation Forest flags on real candles |
| 3.3 | `screen-rules` | 2 | Hand screen vs tree/logistic; `compare` |
| 3.4 | `pattern-fail` | 3 | Failure lab vs coin-flip; pointers onward |
| 3.5 | `factor-score` | 4 | value/momentum/quality; hand vs elastic-net/LightGBM; IC / vs IHSG; `compare` |
| 3.6 | `broker-flow` | 6 | Foreign-net rank; IC / vs IHSG; vs momentum note; doctor hard-deps |

**Parallelizable after 3.1:** clean-prices ∥ screen-rules; factor-score after fundamentals reader solid; broker-flow after broker readers solid.

**Exit:** all Global + Per-chapter checks in `mvp_acceptance.md` ticked on real DB.

---

## Phase 4 — MVP harden (week 5)

| # | Milestone | Done when |
|---|---|---|
| 4.1 | Smoke tests | explore non-empty; demo smoke with fixture or marked integration |
| 4.2 | Error UX | Missing required tables → doctor pointer, not raw traceback |
| 4.3 | Progress marks | explore/demo update progress; `chapters` shows ticks |
| 4.4 | Deepdive stubs | Each MVP topic has a labeled stub deepdive (even if short) |
| 4.5 | MVP sign-off | Maintainer runs acceptance checklist end-to-end |

**Exit:** MVP declared done.

---

## Phase 5 — v1.1 chapters (after MVP)

**v1.1 data** + chapters **5, 7, 9** (`volume-anomaly` is Ch.9 after survival insert).

| Order | Topic | Chapter | Notes |
|---|---|---|---|
| 5.1 | Doctor for v1.1 data | — | insider + sector coverage |
| 5.2 | `cluster-peers` | 5 | HDBSCAN + UMAP vs k-means |
| 5.3 | `insider` | 7 | sparse events; scrub bad dates |
| 5.4 | `volume-anomaly` | 9 | MLP autoencoder vs Isolation Forest on price-volume only |
| 5.5 | Deepdive pass | 5, 7, 9 | Optional ai-saham links where mapped |

**Exit:** v1.1 acceptance (mirror MVP checklist style — write when starting phase 5).

---

## Phase 6 — Phase-2 curriculum (later)

Chapters **8, 10–19** (+ **20** optional). Registry SSOT. Suggested build clusters:

| Cluster | Chapters | Data / deps |
|---|---|---|
| Survival | 8 | time-to-event / insider horizon |
| Text | 10 | Headline source if/when available; synthetic OK |
| Risk & regime | 11, 12 | vol features; breadth/foreign/macro-style inputs |
| Honesty + calibrate | 13 | learning store if needed; labels/observations for deepdive |
| Portfolio | 14 | constraints + optional risk-funnel deepdive |
| Events | 15, 16 | corp actions, earnings |
| Nowcast | 17 | mixed-frequency fundamentals |
| Open session | 18 | IEV / pre-open sidecars; open-session scoreboard |
| Pipeline | 19 | end-to-end + artifact pack quality |
| Optional | 20 | RL sandbox appendix — lowest priority |

Extended advanced chapters **21–44** (incl. `broker-network` Ch.24) follow the same chapter contract.

Introduce **`ml-saham data build-panel`** (learning store) when Direct mode blocks Ch.13/4/6 quality — not before it hurts.

---

## Phase 7 — Optional UX extras (only if needed)

- `demo --plot`  
- `demo --export-notebook`  
- TUI chapter browser  
- Richer `suggestions.md` / structured suggestion JSON for ai-saham  

Do not start these before Phase 4 exit.

---

## Dependency graph (MVP)

```text
Phase 0 scaffold
    → Phase 1 doctor + readers + scoreboard
        → Phase 2 metrics + artifacts + explore UX
            → Ch.0 orientasi
                → Ch.1 clean-prices
                → Ch.2 screen-rules → compare
                → Ch.3 pattern-fail
                → Ch.4 factor-score → compare
                → Ch.6 broker-flow
            → Phase 4 harden → MVP done
```

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| ai-saham schema drift | data_contract column lists; doctor fails loud |
| Temptation to import ai-saham | architecture boundary + CI grep / review |
| Pretty demos without honesty | scoreboard module mandatory in demo path |
| Scope creep (engines, TUI, RL) | MVP acceptance + backlog docs |
| Learning DB too early | Direct mode first; materialize only when blocked |

---

## Immediate next actions

1. Use the CLI (MVP → v1.1 → phase-2).  
2. Phase 7 UX extras only if needed (`--plot`, notebooks, TUI).

---

## Status

| Item | State |
|---|---|
| Design freeze | **Yes** |
| Phase 0–4 (MVP) | **Done / accepted** |
| Phase 5 v1.1 | **Done** — [v1_1_acceptance.md](./v1_1_acceptance.md) |
| Phase 6 phase-2 curriculum | **Done** — [phase2_acceptance.md](./phase2_acceptance.md) |
| Implementation | idle / Phase 7 on demand |
| Current focus | idle |
