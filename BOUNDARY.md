# Boundary — `ml-saham` ↔ `ai-saham`

Sibling contract so the two repos do **not** re-own each other’s jobs.

| Repo | Role |
|------|------|
| **`ai-saham`** | Production engine + market ingest + **corpus authority** (observations + path labels) |
| **`ml-saham` (this repo)** | Offline **challenge lab** + curriculum — **owns accum scoring / policy evaluation** |

Sibling path (maintainer default): `~/dev/ai-saham`  
Full mirror of this contract: [`ai-saham/BOUNDARY.md`](../ai-saham/BOUNDARY.md) (if checked out next to this tree).

---

## One-liners

| Ask | Answer in |
|-----|-----------|
| Capture decisions + path labels (3d/10d/20d)? | **`ai-saham`** — `research accum capture|backfill|labels|status` |
| Score the accum book / stress policies / factors? | **this repo** — `challenge run` / `challenge factor` / engine |
| Fetch / screen / plan / apply YAML | **`ai-saham` only** |

---

## Decision: drop ai-saham accum cohort evaluate

**Status:** Accepted (product) — 2026-07-29  
**Mirror:** `ai-saham/BOUNDARY.md` (same decision).

### Why

| Fact | Implication |
|------|-------------|
| This repo builds panels + metrics from `learning_observations` + `candles` | **Does not read** `learning_evaluations` for challenge scoring |
| ai-saham `research accum evaluate` was a single global rollup of path labels | Not time-bounded; not an input to ADR-002 |
| Duplicating “evaluation” in both repos confuses agents | One scoring authority for accum: **ml-saham challenge** |

### What ml-saham must not depend on

| Item | Rule |
|------|------|
| `saham research accum evaluate` | **Do not require** in doctor, challenge gates, docs, or acceptance |
| ACCUM rows in `learning_evaluations` | **Optional / historical only** — soft doctor presence is fine; never treat as WIN/LOSE or IC source |
| ai-saham multi-horizon evaluate automation | **Not a sibling dependency** |

### What ml-saham still needs from ai-saham (accum)

| Item | Use |
|------|-----|
| `learning_observations` | Features / score components |
| `candles` (+ IHSG) | Protocol labels (excess @ H=3/10/20) |
| `learning_outcome_labels` | Optional join only (future explicit protocol) — **not** default y |
| Capture + labels cron in ai-saham | Keep corpus fresh |

### Pre-open

Unchanged: pre-open challenge protocols use IEV / pre-open observations + session excess.  
ai-saham `research pre-open evaluate` is **not** required for ml-saham challenge either (same pattern: optional soft presence).

---

## Ownership matrix

| Concern | ai-saham | ml-saham |
|---------|:--------:|:--------:|
| Market / broker / IEV fetch & cache | **write** | read |
| Live screen / signal / risk / plan / TUI | **owns** | — |
| `learning_observations` capture / backfill | **write** | **read** (features) |
| `learning_outcome_labels` (`price_path.accum_*`, …) | **SSOT write** | optional join; not default challenge y |
| Accum **cohort evaluate** / ACCUM `learning_evaluations` | **dropped (legacy)** | **do not depend on** |
| Policy tournament WIN / LOSE / rank IC / folds (**tune**) | — | **owns** |
| Factor KEEP / DEMOTE / DROP_CANDIDATE (**tune**) | — | **owns** |
| Champion / beat-production scorer hunt | — | **owns** (planned track; no auto-promote) |
| Curriculum explore / demo | light / optional | **primary onboarding** |
| Decision memos for tuning | may link | **`docs/decisions/`** |
| Auto-promote config into production | human policy path only | **never** |
| Import the other repo’s Python packages | **no** | **no** |
| Scrapers / Stockbit auth | **owns** | **forbidden** |

Hard rules (unchanged): **no** ai-saham Python imports · **no** scrapers · **no** auto-promote · **read-only** on ai-saham SQLite unless materializing a **ml-saham-owned** learning store.

---

## Shared SQLite

- Default DB: `~/dev/ai-saham/data/db/data.db` (`ML_SAHAM_DB` / `--db`).
- This repo opens it **read-only** for challenge/curriculum.
- **Only ai-saham migrates and writes** `learning_*` and market tables.
- This repo writes **artifacts** under `./artifacts` (or `ML_SAHAM_ARTIFACTS`) and optional `~/.ml-saham/` — **not** into ai-saham learning tables.

### How challenge uses the corpus today

| Input | Source | Role |
|-------|--------|------|
| Features / score components | `learning_observations` | Extract production-like sleeves |
| Protocol labels (default) | `candles` + IHSG | **Rebuild** excess return at H=3/10/20 (`accum_path_v1`) |
| Corpus path labels | `learning_outcome_labels` | Not default challenge SSOT |
| Book evaluate rows | `learning_evaluations` | **Ignore for product authority** (legacy / soft doctor only) |

Horizons **3 / 10 / 20** (primary **10**) align with ai-saham ADR-056 **by number**.  
Challenge excess and corpus SUCCESS/FAILURE labels remain **different products** unless a protocol explicitly says otherwise.

---

## Vocabulary (do not conflate)

| Term | Means in **ai-saham** | Means in **ml-saham** |
|------|----------------------|----------------------|
| **label** | `learning_outcome_labels` row | Protocol panel target (often continuous excess) |
| **evaluate (accum)** | **Dropped product** | Prefer **`challenge run`** |
| **WIN / LOSE** | N/A for research accum | Challenge verdict only |
| **primary 10d / H=10** | `price_path.accum_10d.v1` path label | Protocol primary horizon for IC |

Curriculum `compare` / `challenge legacy` are **not** promotion authority (ADR-001 / ADR-002).

---

## What this repo must **not** grow into

- No market **ingest** or provider scrapers  
- No **writes** to ai-saham `learning_*` or production YAML  
- No claim that challenge excess IC **is** the corpus path-label grade  
- No **requiring** `saham research accum evaluate` as a pipeline step  
- No import of `ai-saham` packages “for convenience”

Optional later: a challenge protocol with `label_source=corpus` that **joins** `learning_outcome_labels` — must be **explicit** in the protocol id, never silent.

---

## Operator flows

```text
# Produce corpus (sibling) — required
cd ~/dev/ai-saham
saham research accum labels --all-label-contracts
saham research accum status
# Do NOT require: saham research accum evaluate

# Stress-test policy (this repo) — scoring authority
export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db
ml-saham doctor --deep
ml-saham vet
ml-saham challenge run screener.accum.score_weights --against equal_sleeves
ml-saham challenge factor screener.accum.score_weights --all
# Decision memo under docs/decisions/ — human may edit ai-saham config later
```

---

## Doc pointers

| Need | Where |
|------|--------|
| This boundary (ml-saham) | [BOUNDARY.md](./BOUNDARY.md) |
| Sibling boundary | `ai-saham/BOUNDARY.md` |
| Challenge product | [docs/challenge_product.md](./docs/challenge_product.md) |
| Challenge system | [docs/adr/ADR-002-ideal-challenge-system.md](./docs/adr/ADR-002-ideal-challenge-system.md) |
| Product axis | [docs/adr/ADR-001-challenge-first-product-axis.md](./docs/adr/ADR-001-challenge-first-product-axis.md) |
| Data plane | [data_contract.md](./data_contract.md) |
| Architecture | [architecture.md](./architecture.md) |

When this file and informal chat disagree, **this file + ADRs win**.
