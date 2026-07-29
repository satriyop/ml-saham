# Challenge product (ml-saham)

English overview of the **shipped** ADR-002 challenge lab.  
Design intent: [ADR-001](./adr/ADR-001-challenge-first-product-axis.md) · [ADR-002](./adr/ADR-002-ideal-challenge-system.md).

**Not investment advice. Never auto-promotes into `ai-saham`.**

---

## What it is

`ml-saham` **challenge** stress-tests **frozen production-like policies** (PolicySpecs) from the personal IDX stack against clean challengers, on **read-only** `ai-saham` SQLite.

| In scope | Out of scope |
|----------|----------------|
| Policy tournaments (WIN / LOSE / INCONCLUSIVE / BLOCKED_*) | Auto-writing ai-saham YAML/code |
| Factor keep/demote (accum sleeves) | Replacing `ai-saham` ingest/engines |
| Engine portfolio rollups | Curriculum demos as promotion authority |
| English audit reports + artifacts | Live trading / paper broker |

Learning (`explore` / chapters) is **secondary** and mostly Indonesian for pedagogy.

---

## Vocabulary (aligned with ai-saham)

| Term | Meaning | Examples |
|------|---------|----------|
| **Engine** | Product stack audit group | `screener` |
| **Scenario** | Screen path inside an engine (ADR-047 / research CLI) | `accum`, `pre-open` |
| **Policy** | One frozen PolicySpec + protocol tournament | `screener.accum.score_weights` |
| **Protocol** | Evaluation law (labels, horizons, folds) | `accum_path_v1`, `pre_open_session_v1` |
| **Challenger** | Named alternative under the same decision type | `equal_sleeves`, `ridge_reweight` |

Prefer **`--scenario`**, not “track.”

---

## Catalog (shipped)

### Engine: `screener`

| Scenario | Policy id | Protocol | Operator note |
|----------|-----------|----------|---------------|
| `accum` | `screener.accum.score_weights` | `accum_path_v1` (primary **H=10**, report 3/10/20) | [challenge_accum_score_weights.md](./challenge_accum_score_weights.md) |
| `pre-open` | `screener.pre_open.iev_rank` | `pre_open_session_v1` (same-session open→close, H=0) | [challenge_pre_open_iev_rank.md](./challenge_pre_open_iev_rank.md) |
| `pre-open` | `screener.pre_open.directional_score` | `pre_open_session_v1` | [challenge_pre_open_directional_score.md](./challenge_pre_open_directional_score.md) |

**Engine portfolio:** [challenge_engine_screener.md](./challenge_engine_screener.md)  
**Factor validity (accum):** [challenge_factor_validity.md](./challenge_factor_validity.md)  
**Engine → data map:** [engine_factor_map.md](./engine_factor_map.md)

### Outcomes

| Status / verdict | Meaning |
|------------------|---------|
| `WIN` / `LOSE` / `INCONCLUSIVE` | Challenger vs production under protocol rules |
| `BLOCKED_DATA` | Insufficient / unextractable panel (honest; product may still be complete) |
| `BLOCKED_POLICY` | Unknown policy, wrong track, or unsupported combination |
| Factor `KEEP` / `DEMOTE` / `DROP_CANDIDATE` / `INCONCLUSIVE` | Sleeve validity (accum factor track only today) |

---

## Commands (primary path)

```bash
export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db

ml-saham doctor --deep
ml-saham vet

# Catalog
ml-saham challenge list
ml-saham challenge engine list

# One policy
ml-saham challenge run screener.accum.score_weights --against equal_sleeves
ml-saham challenge run screener.pre_open.iev_rank --against equal_sleeves
ml-saham challenge run screener.pre_open.directional_score --against equal_sleeves

# Engine rollup (all scenarios, or one)
ml-saham challenge engine screener
ml-saham challenge engine screener --scenario accum
ml-saham challenge engine screener --scenario pre-open

# Factor validity (accum only)
ml-saham challenge factor screener.accum.score_weights --list-factors
ml-saham challenge factor screener.accum.score_weights --factor consistency
ml-saham challenge factor screener.accum.score_weights --all
```

Defaults worth knowing:

| Surface | Default challenger |
|---------|-------------------|
| `challenge run` | `ridge_reweight` (CLI default; prefer `equal_sleeves` for stable digs) |
| `challenge engine` | **`equal_sleeves`** |

Exports: `--export-json` / `--export-md`. Artifacts: `./artifacts/challenge/…` (gitignored).

---

## How to use results

1. **`challenge engine screener`** — “How is the screener stack?”  
2. **`challenge run <policy>`** — dig one policy / challenger.  
3. **`challenge factor …`** — sleeve keep/demote on accum weights.  
4. Write a **human decision memo** if needed (example: [decisions/accum_score_weights_2026-07-29.md](./decisions/accum_score_weights_2026-07-29.md)).  
5. **Do not** promote into ai-saham from a single thin window or BLOCKED run.

### Data-tolerant policies

Some products are **complete** even when the maintainer DB is thin:

| Policy | Thin-data behavior |
|--------|---------------------|
| `directional_score` | `BLOCKED_DATA` until denser `PRE_OPEN_AUCTION_DIRECTION` captures |
| Engine rollup | Lists BLOCKED rows; exit 0 if engine/scenario resolve OK |

That is intentional, not a failed install.

---

## What is *not* the product authority

| Surface | Role |
|---------|------|
| `challenge legacy …` | Pre-ADR-002 chapter-loop batch |
| `compare <slug>` / `demo` | Curriculum / lab |
| `explore` | Indonesian problem framing |

---

## Doc index

| Doc | Role |
|-----|------|
| This file | Product map + commands |
| [challenge_engine_screener.md](./challenge_engine_screener.md) | Engine portfolio operator note |
| [challenge_accum_score_weights.md](./challenge_accum_score_weights.md) | Accum policy |
| [challenge_pre_open_iev_rank.md](./challenge_pre_open_iev_rank.md) | Pre-open IEV rank |
| [challenge_pre_open_directional_score.md](./challenge_pre_open_directional_score.md) | Pre-open observation / raw_score |
| [challenge_factor_validity.md](./challenge_factor_validity.md) | Factor track |
| [engine_factor_map.md](./engine_factor_map.md) | Engines ↔ tables ↔ policies |
| [adr/](./adr/) | Locked product decisions |

---

## One-line summary

> **Challenge = versioned PolicySpec tournaments (+ factor / engine rollups) under fixed protocols, English artifacts, no auto-promotion — learning stays optional.**
