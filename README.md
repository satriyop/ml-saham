# ml-saham

**Challenge lab** for personal IDX quant stack (`ai-saham`) — with a curriculum attached.

Primary job: stress-test **factors, weights, and engine policies** on real market data (read-only SQLite from `ai-saham`).  
Secondary job: problem-centric ML chapters so those audits are understandable.

Product axis (locked): **[ADR-001 — Challenge-first](./docs/adr/ADR-001-challenge-first-product-axis.md)**  
Challenge system (target): **[ADR-002 — Ideal Challenge System](./docs/adr/ADR-002-ideal-challenge-system.md)**  
Design: [architecture.md](./architecture.md) · [engine_factor_map.md](./docs/engine_factor_map.md) · [chapters.md](./chapters.md) · [ux.md](./ux.md)

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

**Design:** [ADR-002](./docs/adr/ADR-002-ideal-challenge-system.md).  
**Shipped policy challenges:**  
- Accum: [docs/challenge_accum_score_weights.md](./docs/challenge_accum_score_weights.md)  
- Pre-open IEV rank: [docs/challenge_pre_open_iev_rank.md](./docs/challenge_pre_open_iev_rank.md)  
- Pre-open observation / raw_score: [docs/challenge_pre_open_directional_score.md](./docs/challenge_pre_open_directional_score.md)

| Command | Job |
|---------|-----|
| `challenge list` | List ADR-002 policy ids |
| `challenge run <policy>` | Production policy vs challenger (fixed protocol) |
| `challenge factor … --factor X` / `--all` | Keep/demote/drop one factor, or batch table for all enabled sleeves |
| `challenge legacy …` | Old chapter-loop batch (do not use for promotion) |
| `vet` / `doctor --deep` | Data-plane gate |
| `compare <slug>` | Curriculum / single-topic lab (not ADR-002 authority) |

**Accum horizons:** report **3 / 10 / 20** sessions; **primary = 10**. Never auto-promotes configs.

```bash
ml-saham doctor --deep
ml-saham vet
ml-saham challenge list
ml-saham challenge run screener.accum.score_weights --against equal_sleeves
ml-saham challenge run screener.accum.score_weights --against ridge_reweight
ml-saham challenge run screener.pre_open.iev_rank --against equal_sleeves
ml-saham challenge run screener.pre_open.directional_score --against equal_sleeves
ml-saham challenge factor screener.accum.score_weights --list-factors
ml-saham challenge factor screener.accum.score_weights --factor consistency
ml-saham challenge factor screener.accum.score_weights --all

# Legacy batch only
ml-saham challenge legacy all
```

Engine map: [docs/engine_factor_map.md](./docs/engine_factor_map.md) · Factor validity: [docs/challenge_factor_validity.md](./docs/challenge_factor_validity.md).

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
              ├─ challenge run <policy>  →  ADR-002 policy tournament (primary)
              ├─ challenge legacy …      →  old chapter-loop batch
              └─ explore / demo          →  curriculum onboarding
```

Hard rules: no `ai-saham` Python imports · no scrapers · no auto-promote of configs.

ADRs: [docs/adr/](./docs/adr/)
