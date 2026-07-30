# ml-saham

**Challenge lab** for the personal IDX quant stack (`ai-saham`), with a curriculum attached.

| Priority | Job |
|----------|-----|
| **1. Challenge** | Stress-test **policies, factors, and screener scenarios** on real market data (read-only SQLite) |
| **2. Learning** | Problem-centric ML chapters so those audits are understandable |

**Product map (start here):** [docs/challenge_product.md](./docs/challenge_product.md)  
**ADRs:** [ADR-001 challenge-first](./docs/adr/ADR-001-challenge-first-product-axis.md) · [ADR-002 challenge system](./docs/adr/ADR-002-ideal-challenge-system.md)

| Challenge purpose | Question | Status |
|-------------------|----------|--------|
| **Tune** | Factor worth it? Weights/combo OK? | **Shipped** |
| **Champion** | Better score rule than production (internals optional)? | **Shipped** (`challenge champion`) |

Not investment advice. **Never auto-promotes** configs into `ai-saham`.

### Sibling boundary (`ai-saham`)

| Job | Where |
|-----|--------|
| Fetch, live screen/plan, **corpus** obs + path labels | **`ai-saham`** — `saham research accum capture\|labels\|status` |
| Policy tournament, rank IC, factor KEEP·DEMOTE | **this repo** — `challenge run` / `challenge factor` |
| ai-saham `research accum evaluate` | **Not required** — dropped product; see [BOUNDARY.md](./BOUNDARY.md) |

`ml-saham` is **read-only** on ai-saham SQLite; no Python imports across repos; no scrapers.  
Full ownership matrix and vocabulary: **[BOUNDARY.md](./BOUNDARY.md)** (mirror: `ai-saham/BOUNDARY.md`).

---

## Language

| Axis | Surfaces | Learner-facing language |
|------|----------|-------------------------|
| **Challenge** (primary) | `challenge …`, `vet`, audit exports | **English** |
| **Learning** (secondary) | `explore`, curriculum narrative | **Indonesian** |

Commands, flags, slugs, and code stay English on both axes.

---

## Setup

```bash
cd ~/dev/ml-saham
python3.11 -m venv .venv   # or 3.12
source .venv/bin/activate
pip install -e ".[ml]"     # challenge path (recommended)
```

### Database

Default: `~/dev/ai-saham/data/db/data.db`  
Ingest stays in `ai-saham`. `ml-saham` does not scrape providers or import ai-saham Python packages.

```bash
export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db
ml-saham doctor --deep
ml-saham vet
```

---

## Challenge product (main path)

### Vocabulary (ai-saham-aligned)

| Term | Meaning | Example |
|------|---------|---------|
| **Engine** | Stack audit group | `screener` |
| **Scenario** | Screen path | `accum`, `pre-open` |
| **Policy** | One PolicySpec tournament | `screener.accum.score_weights` |

### Shipped catalog

| Scenario | Policy | Protocol (primary) | Note |
|----------|--------|--------------------|------|
| `accum` | `screener.accum.score_weights` | `accum_path_v1` (**H=10**) | [docs](./docs/challenge_accum_score_weights.md) |
| `pre-open` | `screener.pre_open.iev_rank` | `pre_open_session_v1` (open→close) | [docs](./docs/challenge_pre_open_iev_rank.md) |
| `pre-open` | `screener.pre_open.directional_score` | `pre_open_session_v1` | [docs](./docs/challenge_pre_open_directional_score.md) |

**Engine rollup:** [docs/challenge_engine_screener.md](./docs/challenge_engine_screener.md)  
**Champion:** [docs/challenge_champion.md](./docs/challenge_champion.md)  
**Factor keep/demote (accum):** [docs/challenge_factor_validity.md](./docs/challenge_factor_validity.md)  
**Full product doc:** [docs/challenge_product.md](./docs/challenge_product.md)

### Commands

```bash
ml-saham challenge list
ml-saham challenge engine list

# One policy (prefer equal_sleeves for stable digs)
ml-saham challenge run screener.accum.score_weights --against equal_sleeves
ml-saham challenge run screener.pre_open.iev_rank --against equal_sleeves
ml-saham challenge run screener.pre_open.directional_score --against equal_sleeves

# Screener portfolio (all scenarios, or one)
ml-saham challenge engine screener
ml-saham challenge engine screener --scenario accum
ml-saham challenge engine screener --scenario pre-open

# Champion (learned score rule vs production)
ml-saham challenge champion screener.accum.score_weights --model lgbm_reweight

# Control tower
ml-saham challenge health --with-champion --with-factors
# ml-saham challenge promote-packet --from-json /tmp/export.json

# Factor validity (accum sleeves)
ml-saham challenge factor screener.accum.score_weights --all
ml-saham challenge factor screener.accum.score_weights --factor consistency
```

| Command | Job |
|---------|-----|
| `challenge list` | Policy ids + protocols |
| `challenge run <policy>` | Production vs challenger (tune) |
| `challenge champion` | Learned score rule vs production |
| `challenge health` | Control tower pack (engine ± champion ± factors) |
| `challenge promote-packet` | Human promote/reject checklist from export |
| `challenge engine screener` | PolicySpec portfolio (`--scenario` optional) |
| `challenge factor …` | KEEP / DEMOTE / DROP_CANDIDATE (accum) |
| `vet` / `doctor --deep` | Data-plane gate |
| `challenge legacy …` | Old chapter-loop batch — **not** promotion authority |
| `compare <slug>` | Curriculum lab — **not** ADR-002 authority |

Statuses: `WIN` · `LOSE` · `INCONCLUSIVE` · `BLOCKED_DATA` · `BLOCKED_POLICY` (first-class; thin data is honest, not a broken install).

Map: [docs/engine_factor_map.md](./docs/engine_factor_map.md) · Decision example: [docs/decisions/](./docs/decisions/).

---

## Learning second (onboarding)

```bash
ml-saham chapters
ml-saham explore broker-flow --no-pager
ml-saham demo clean-prices
```

Curriculum list: [chapters.md](./chapters.md). Registry SSOT: `src/ml_saham/chapters/registry.py`.

---

## Ops

| Item | Location |
|------|----------|
| Progress (curriculum) | `~/.ml-saham/progress.json` |
| Artifacts | `./artifacts` or `ML_SAHAM_ARTIFACTS` |
| Challenge acceptance (historical fixture suite) | [challenge_acceptance.md](./challenge_acceptance.md) |

Hard rules: **no** ai-saham Python imports · **no** scrapers · **no** auto-promote.  
Sibling contract: **[BOUNDARY.md](./BOUNDARY.md)**.

```text
ai-saham  →  fetch/enrich → SQLite → corpus obs + path labels (no accum evaluate product)
ml-saham  →  read-only DB
              ├─ challenge run / engine / factor   →  ADR-002 scoring authority
              ├─ challenge legacy                  →  chapter-loop (legacy)
              └─ explore / demo                    →  curriculum
```

ADRs: [docs/adr/](./docs/adr/) · Architecture: [architecture.md](./architecture.md) · Boundary: [BOUNDARY.md](./BOUNDARY.md)  
SOTA vocabulary (not literature frontier): [docs/sota_vocabulary_and_literature.md](./docs/sota_vocabulary_and_literature.md)
