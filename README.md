# ml-saham

**Challenge lab** for personal IDX quant stack (`ai-saham`) — with a curriculum attached.

Primary job: stress-test **factors, weights, and engine policies** on real market data (read-only SQLite from `ai-saham`).  
Secondary job: problem-centric ML chapters so those audits are understandable.

Product axis (locked): **[ADR-001 — Challenge-first](./docs/adr/ADR-001-challenge-first-product-axis.md)**  
Design: [architecture.md](./architecture.md) · [chapters.md](./chapters.md) · [ux.md](./ux.md)

### Language (by product axis)

| Axis | Surface | Learner-facing language |
|------|---------|-------------------------|
| **Challenge** (primary) | `challenge`, `compare`, engine audit reports/exports | **English** |
| **Learning** (secondary) | `explore`, curriculum narrative, teaching caveats | **Indonesian** |

Commands, flags, topic slugs, and code stay English on both axes. See ADR-001 §6.

Not investment advice. Artifacts never auto-promote into `ai-saham`.

---

## Setup

```bash
cd ~/dev/ml-saham
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[ml]"    # challenge path (recommended)
# pip install -e .        # core only: explore + light demos
```

### Database

Default: `~/dev/ai-saham/data/db/data.db`  
Ingest stays in `ai-saham` (`saham fetch market`, …). `ml-saham` does not scrape providers.

```bash
export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db
ml-saham doctor
```

---

## Challenge first (main path)

Both primary commands are **related to `ai-saham`**, with different scope (ADR-001 §2):

| Command | Product definition | Relation to `ai-saham` |
|---------|-------------------|------------------------|
| **`challenge`** | Multi-factor **engine audit** + rollup export | **For** engines: how is the stack doing? |
| **`compare`** | **One-factor** baseline vs against experiment | **Against** ai-saham-style / static baselines: should we change *this* factor? |

```text
compare   = single-factor lab (challenge an ai-saham-style baseline)
challenge = runs those compares in bulk for an engine / all factors
```

Same data plane as `ai-saham` (read-only SQLite). **Never auto-promotes** configs.

### `challenge` — engine audit

Engine map: `src/ml_saham/eval/challenge.py` (`ENGINE_FACTORS`).

| Target | What it audits |
|--------|----------------|
| `screener` | Pre-open + accumulation factors |
| `engine` | Signal / risk / market-context factors (`--category`, `--type`) |
| `other` | Supporting labs + **`data-integrity`** gate |
| `all` | Full audit |

```bash
ml-saham challenge all
ml-saham challenge all --export-json /tmp/challenge.json --export-md /tmp/challenge.md
ml-saham challenge screener
ml-saham challenge screener --scenario pre-open
ml-saham challenge screener --scenario accum
ml-saham challenge engine --category signal
ml-saham challenge engine --category risk --type sizing
ml-saham challenge engine --category market --type regime
ml-saham challenge other

# Data plane vet (before engine challenge)
ml-saham doctor --deep
ml-saham vet
ml-saham compare data-integrity --baseline coverage --against integrity
```

Engine → tables → slugs: [docs/engine_factor_map.md](./docs/engine_factor_map.md)  
Curriculum gap example: **sector macro context** (ai-saham ADR-053) ≠ `sector-breadth` — candidate `sector-macro` (not shipped yet).

### `compare` — single-factor experiment

Prefer baselines that mean **current static / engine-like policy**; `--against` is the learned alternative. Requires `--baseline` and `--against`.

```bash
ml-saham compare factor-score --baseline equal-weight --against elastic-net
ml-saham compare pattern-fail --baseline coinflip --against lgbm
ml-saham compare broker-network --baseline degree --against pagerank
```

**Quality bar:** engine-map factors must have working **`run_compare`** + honest metrics.  
Prefer install errors for missing ML deps over silent weak models that fake a win.

---

## Learning second (onboarding)

Use when you need the *problem framing* before reading a challenge report.

```bash
ml-saham chapters
ml-saham chapters --all
ml-saham explore broker-flow --no-pager
ml-saham demo clean-prices          # light illustration (not the audit spine)
ml-saham deepdive broker-flow       # optional link notes → ai-saham
```

Chapter numbers: **registry** SSOT (`src/ml_saham/chapters/registry.py`).  
Curriculum list: [chapters.md](./chapters.md).

Some engine chapters intentionally push you to `compare` / `challenge` instead of a soft `demo` — that is by design (ADR-001).

---

## Ops

| Item | Location |
|------|----------|
| Progress (curriculum) | `~/.ml-saham/progress.json` (`ML_SAHAM_HOME`) |
| Artifacts | `./artifacts` or `ML_SAHAM_ARTIFACTS` / `--artifacts-dir` |
| Doctor | `ml-saham doctor` — data tiers before demos/challenges |
| Acceptance (challenge first) | [challenge_acceptance.md](./challenge_acceptance.md) |
| Acceptance (curriculum, historical) | [mvp_acceptance.md](./mvp_acceptance.md) · [v1_1_acceptance.md](./v1_1_acceptance.md) · [phase2_acceptance.md](./phase2_acceptance.md) |

Scoreboard default: long-only vs IHSG (gross + cost banner).  
Ch.18 `pre-open-rank` uses an open-session scoreboard.

---

## Architecture snapshot

```text
ai-saham  →  fetch/enrich → SQLite
ml-saham  →  read-only DB
              ├─ challenge / compare  →  engine factor audit + artifacts  (primary)
              └─ explore / demo       →  curriculum onboarding          (secondary)
```

Hard rules: no `ai-saham` Python imports · no scrapers · no auto-promote of configs.

ADRs: [docs/adr/](./docs/adr/)
