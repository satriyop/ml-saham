# Architecture — `ml-saham`

Implementation shape for the personal IDX **challenge lab** (+ curriculum onboarding).  
**Product axis (locked):** [ADR-001 — Challenge-first](./docs/adr/ADR-001-challenge-first-product-axis.md)  
**Challenge system (design target):** [ADR-002 — Ideal Challenge System](./docs/adr/ADR-002-ideal-challenge-system.md)  
Map: [engine_factor_map.md](./docs/engine_factor_map.md)  
Curriculum: [chapters.md](./chapters.md) · UX: [ux.md](./ux.md) · Data: [data_contract.md](./data_contract.md) · Artifacts: [artifacts.md](./artifacts.md)

---

## Goals that constrain architecture

1. **Challenge first** — policy tournaments + factor keep/drop under fixed protocols (ADR-001, **ADR-002**). Chapter-loop product surface is retired.  
2. **Learning second** — chapter modules teach problems so audits are interpretable (`ml-saham learn explore` / light `learn demo`).  
3. Emit artifacts usable to tune `ai-saham` (**never auto-promote**).  
4. Read real market data from `ai-saham` SQLite **or** a derived learning DB.  
5. **Horizons:** align with ai-saham (accum primary **10** sessions; report **3** and **20** where applicable) — ADR-002 §4.

---

## Hard boundaries

| Rule | Meaning |
|---|---|
| **No import of `ai-saham` Python packages** | `ml-saham` talks to data via SQLite paths / exported files only |
| **Ingest stays in `ai-saham`** | No Stockbit/Yahoo/IDX scrapers inside `ml-saham` |
| **Chapters stay problem-centric** | Topic modules teach generic problems; product authority is ADR-002 challenge, not curriculum glue |
| **Challenge outranks curriculum polish** | When priorities conflict, ship `run_compare` / engine audits before soft demos (ADR-001) |
| **Language by axis** | Challenge UI/reports **English**; learning `learn explore` narrative **Indonesian** (ADR-001 §6). Flags/slugs always EN |
| **CLI is the product** | Typer (or Click) app; no web/TUI in MVP |

---

## Stack (locked for MVP)

| Piece | Choice |
|---|---|
| Language | Python 3.11+ |
| CLI | Typer |
| Data | pandas + SQLAlchemy or stdlib `sqlite3` (prefer thin `sqlite3` + pandas for MVP) |
| ML | scikit-learn; LightGBM where chapters need GBDT |
| Config | env `ML_SAHAM_DB` + `--db`; optional `~/.ml-saham/config.toml` later |
| Packaging | `pyproject.toml` / installable console script `ml-saham` |

Plots optional (`matplotlib` or similar) behind `--plot`; not required to finish a demo.

---

## Repository layout

```text
ml-saham/
├── pyproject.toml
├── README.md
├── chapters.md
├── ux.md
├── data_contract.md
├── artifacts.md
├── mvp_acceptance.md
├── problem_backlog.md
├── roadmap.md
├── archive/                  # local drafts only (gitignored)
├── src/ml_saham/
│   ├── __init__.py
│   ├── cli/
│   │   └── app.py            # Typer root: challenge + learn + doctor/vet
│   ├── data/
│   │   ├── connection.py     # resolve --db / env
│   │   ├── doctor_checks.py  # MVP / v1.1 / phase-2 data presence
│   │   ├── aisaham_read.py   # read-only queries against ai-saham schema
│   │   └── learning_store.py # optional materialize panels into ml-saham DB
│   ├── eval/
│   │   ├── scoreboard.py     # long-only vs IHSG + banners
│   │   ├── metrics.py        # rank IC, etc.
│   │   └── costs.py          # optional haircut
│   ├── artifacts/
│   │   └── writer.py         # schema in artifacts.md
│   ├── progress.py           # ~/.ml-saham/progress.json
│   └── chapters/
│       ├── registry.py       # topic slug → chapter meta
│       ├── _template/        # copy-paste contract
│       ├── orientasi/
│       ├── clean_prices/
│       ├── screen_rules/
│       ├── pattern_fail/
│       ├── factor_score/
│       ├── broker_flow/
│       └── …                 # add with ship phase
└── tests/
    ├── data/
    └── chapters/
```

Each chapter package exposes a small interface (see below) so CLI stays thin.

---

## Chapter module contract

Every chapter under `src/ml_saham/chapters/<slug>/` provides:

| Symbol | Role |
|---|---|
| `META` | id, number, title (ID), tier, phase, topic slug |
| `explore_text()` | markdown/plain for `learn explore` |
| `run_demo(ctx) -> DemoResult` | real-data run via `learn demo` |
| `run_compare(ctx) -> CompareResult` | curriculum lab via `learn compare` (not ADR-002 authority) |
| `required_data` | `"mvp"` / `"v1_1"` / `"phase2"` for `doctor` |

`ctx` carries: db connection, universe, as_of, model flags, output dirs, cost flags.

---

## Runtime flow

```text
CLI
  → resolve db (flag / env / config)
  → registry.get(topic)
  → doctor gate if learn demo/compare (data-tier requirement)
  → chapter.run_* 
  → scoreboard.render (banners)
  → optional artifacts.writer
  → progress.mark
```

---

## Two database modes

| Mode | When | Who writes |
|---|---|---|
| **Direct** | Table shape enough for the lesson | Read-only from `ai-saham` `data.db` |
| **Learning store** | Need panel / as_of / chapter features | `ml-saham` materializes into e.g. `~/.ml-saham/learning.db` or project `data/learning.db` from ai-saham extracts |

MVP chapters (0–4, 6) should work in **Direct** mode where possible; introduce learning-store materialization when cross-section panels get painful (likely Ch.4/6 polish or Ch.13 walk-forward).

---

## Alignment with `ai-saham` (without coupling)

- Same user muscle memory: CLI, `--db`, universe names.  
- Different codebase and dependency graph.  
- Shared understanding of table names via [data_contract.md](./data_contract.md), not shared Python types from `ai-saham`.

---

## Testing strategy (MVP)

| Layer | What |
|---|---|
| Unit | metrics, scoreboard banners, doctor checks on fixture SQLite |
| Chapter smoke | `learn explore` returns non-empty; `learn demo` runs against a **real** local db path in integration job (optional/local marker) |
| No | Live Stockbit calls inside `ml-saham` tests |

---

## Non-goals

- Embedding or vendoring `ai-saham`  
- Background daemons / schedulers  
- Multi-user auth  
- Auto-writing into `ai-saham` YAML
