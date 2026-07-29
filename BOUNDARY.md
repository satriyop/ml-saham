# Boundary — `ml-saham` ↔ `ai-saham`

Sibling contract so the two repos do **not** re-own each other’s jobs.

| Repo | Role |
|------|------|
| **`ai-saham`** | Production engine + market ingest + **corpus authority** |
| **`ml-saham` (this repo)** | Offline **challenge lab** + curriculum (read-only consumer) |

Sibling path (maintainer default): `~/dev/ai-saham`  
Full mirror of this contract: [`ai-saham/BOUNDARY.md`](../ai-saham/BOUNDARY.md) (if checked out next to this tree).

---

## One-liners

| Ask | Answer in |
|-----|-----------|
| What did the **production book** do on path labels? | **`ai-saham`** — `research accum labels` / `evaluate` / `status` |
| Should we **change** a production policy / factor weight? | **`ml-saham` (this repo)** — `challenge run` / `challenge factor` |
| Fetch / screen / plan / apply YAML | **`ai-saham` only** |

---

## Ownership matrix

| Concern | ai-saham | ml-saham |
|---------|:--------:|:--------:|
| Market / broker / IEV fetch & cache | **write** | read |
| Live screen / signal / risk / plan / TUI | **owns** | — |
| `learning_observations` capture / backfill | **write** | **read** (features) |
| `learning_outcome_labels` (`price_path.accum_*`, …) | **SSOT write** | do not redefine as SSOT |
| `learning_evaluations` (cohort report card) | **SSOT write** | do not replace |
| Policy tournament WIN / LOSE / rank IC / folds | — | **owns** |
| Factor KEEP / DEMOTE / DROP_CANDIDATE | — | **owns** |
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
- This repo writes **artifacts** under `./artifacts` (or `ML_SAHAM_ARTIFACTS`) and optional `~/.ml-saham/` progress / learning store — **not** into ai-saham learning tables.

### How challenge uses the corpus today

| Input | Source | Role |
|-------|--------|------|
| Features / score components | `learning_observations` (e.g. ACCUMULATION_DISCOVERY) | Extract production-like sleeves |
| Protocol labels (default) | `candles` + IHSG | **Rebuild** excess return at H=3/10/20 (`accum_path_v1`) |
| Corpus path labels | `learning_outcome_labels` | **Not** the default challenge SSOT (optional future protocol only) |
| Book evaluate rows | `learning_evaluations` | **Do not** treat as challenge WIN/LOSE |

Horizons **3 / 10 / 20** (primary **10**) align with ai-saham ADR-056 **by number**.  
Challenge excess labels and corpus SUCCESS/FAILURE labels are **different products** unless a protocol explicitly says otherwise.

---

## Vocabulary (do not conflate)

| Term | Means in **ai-saham** | Means in **ml-saham** |
|------|----------------------|----------------------|
| **label** | `learning_outcome_labels` row | Protocol panel target (often continuous excess) |
| **evaluate** | `research … evaluate` book report | Prefer **`challenge run`** — not a synonym |
| **readiness** / `OOS_DIAGNOSTIC_*` | Learning evaluation ceiling | N/A — use WIN / LOSE / INCONCLUSIVE / BLOCKED_* |
| **WIN / LOSE** | N/A | Challenge verdict only |
| **primary 10d / H=10** | `price_path.accum_10d.v1` | Protocol primary horizon for IC |

Curriculum `compare` / `challenge legacy` are **not** promotion authority (ADR-001 / ADR-002).

---

## What this repo must **not** grow into

- No market **ingest** or provider scrapers  
- No **writes** to ai-saham `learning_*` or production YAML  
- No claim that challenge excess IC **is** the corpus book grade  
- No replacing `saham research accum evaluate` with `challenge run` in docs or agents  
- No import of `ai-saham` packages “for convenience”

Optional later: a challenge protocol with `label_source=corpus` that **joins** `learning_outcome_labels` — must be **explicit** in the protocol id, never silent.

---

## Operator flows

```text
# Produce corpus (sibling)
cd ~/dev/ai-saham
saham research accum labels --all-label-contracts
saham research accum evaluate

# Stress-test policy (this repo)
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
| Data plane | [data_contract.md](./data_contract.md) (keep table names in sync with live ai-saham schema) |
| Architecture | [architecture.md](./architecture.md) |

When this file and informal chat disagree, **this file + ADRs win**.
