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
| `learning_policy_snapshots` v1-v3 history / v4 active set | **SSOT write** | **read + independently verify** |
| `learning_diagnostic_producer_snapshots` + schema-14 bindings | **SSOT write** | **read + independently verify** |
| `learning_outcome_labels` (`price_path.accum_*`, …) | **SSOT write** | optional join; not default challenge y |
| Accum **cohort evaluate** / ACCUM `learning_evaluations` | **dropped (legacy)** | **do not depend on** |
| Policy tournament WIN / LOSE / rank IC / folds (**tune**) | — | **owns** |
| Factor KEEP / DEMOTE / DROP_CANDIDATE (**tune**) | — | **owns** |
| Champion / beat-production scorer hunt | — | **owns** (`challenge champion`; no auto-promote) |
| Health report / promote packet packs | — | **owns** (artifacts only; never write ai-saham) |
| Curriculum `learn explore` / `learn demo` | light / optional | **primary onboarding** |
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

### Compatibility cohort discipline

- ai-saham stamps `learning_observations.compatibility_id` from **ADR-068
  behavioural cohort identity** for ACCUM: digest of (behavioural probe
  outputs, ADR-059 snapshot payload digest, observation payload schema
  version). Config comments and renames no longer fork; threshold/scoring
  changes do. Pre-open keeps its own mechanism.
- ai-saham records `producer_source_revision` on observations as provenance
  beside identity. Multi-build rows under one `compatibility_id` are valid;
  do not treat build diversity as corruption.
- Probe coverage on the ai-saham side is a **measured floor**, not a proof of
  behavioural equivalence — ml-saham must still treat each `compatibility_id`
  as an opaque hard boundary.
- **ml-saham never mixes** multiple `compatibility_id` values in one panel or curriculum load.
- Shared helper: `src/ml_saham/data/observation_cohort.py` (challenge + curriculum must use it; no ad-hoc `SELECT … FROM learning_observations` in chapters/challenge).
- **Production-facing challenge** (`challenge run|factor|engine|health|champion` and
  promote reopen): bind an **explicit** purpose-family cohort — ACCUM policies
  require a real ACCUM `compatibility_id` (+ verified snapshots); PRE_OPEN
  observation policies require a real PRE_OPEN cohort; IEV rank binds iev
  snapshot batch identity (observation cohort ids are not a population filter).
  Largest/single-cohort auto-select is **not** allowed for production verdicts.
- **Exploratory / curriculum** loaders may still auto-select largest `n` (ties →
  newest `max(captured_at)`) and must record selected/excluded cohorts in notes.
- Doctor soft-flags multi-cohort presence; retired tables `candidate_observations` / `signal_forward_labels` are never hard SSOT.

### Verified production-policy snapshots

- Active accumulation comparisons require exactly nine
  `production_policy_snapshot.v4` rows for the selected compatibility cohort,
  including the unevaluable-gate and resolved signal decision policies.
- ml-saham recomputes canonical payload digests and snapshot IDs and validates
  all cohort/contract/semantic bindings. It never imports ai-saham Python,
  writes/repairs the table, infers missing rows, or falls back to packaged
  policy mirrors.
- `VerifiedProductionPolicySnapshot`, ML-owned `ChallengePolicyAdapter`, and
  `Protocol` are separate contracts. Production material cannot come from the
  adapter.
- Historical `production_policy_snapshot.v1`/v2/v3 cohorts are audit history,
  not eligible for current `baseline=production`.
- Snapshot or adapter integrity failures are `BLOCKED_POLICY`; valid policy
  with insufficient rows/folds is `BLOCKED_DATA`.
- Operators must pass `--compatibility-id` for every production-facing ACCUM or
  PRE_OPEN observation challenge (not only thin/new rulebooks). Omitting it
  fails closed with `BLOCKED_POLICY`. A mixed engine reuses one flag only as a
  pass-through; each policy still validates its own purpose family.
- **`baseline=production`** is allowed only with a verified production-policy
  snapshot and supported challenge adapter. Static pre-open / IEV fixtures have
  no such identity today: requesting `production` is **`BLOCKED_POLICY`** (no
  silent remap). Reference digs require an explicit
  `--baseline static_reference` and are not promote-eligible.

### Purpose-specific diagnostic identity (ADR-069)

- Diagnostic challenge authority is two-dimensional: one explicit ACCUM Action
  `compatibility_id` plus one explicit purpose-specific
  `diagnostic_compatibility_id`. Diagnostic health accepts a repeatable exact
  diagnostic-ID mapping; a missing mapping blocks only that bag.
- ai-saham owns six immutable `diagnostic_producer_snapshot.v1` producers and
  four closed bindings in observation schema 14. ml-saham recomputes canonical
  payload digests, snapshot IDs, producer sets, and composite IDs through its
  read-only connection; it never synthesizes or repairs them.
- Current product extraction uses only `features_by_window.7`, exact named
  Alpha/Trigger contributions, canonical `sc_sector_breadth`, and frozen
  `shared.market_context`. Root aliases, first-present windows, current MCE
  table joins, and packaged production-policy fallbacks are historical only.
- Diagnostic artifact schema 4 is sealed, explicitly non-promotable, and binds
  both identities, producer snapshots/digests/source revisions, current spec
  and extractor content, population, session/cutoff ranges, and sample unit.
  Current display/reopen re-resolves upstream authority. Schema 3 remains
  historical display-only.
- **Population identity** is typed and purpose-specific: `accum_compat` /
  `pre_open_compat` (observation cohort id) or `iev_batch` (selection contract
  + stable hash of selected IEV row material: capture time, NCP lock, rank,
  IEV, IEP — not mere ticker/date membership). Carried on results/artifacts as
  `population_identity_*` (challenge artifact schema **v3**). Promote reopen of
  production ACCUM packets **requires** these fields and enforces
  `kind=accum_compat` with `id == observation_compatibility_id`.

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

Curriculum `learn compare` is **not** promotion authority (ADR-001 / ADR-002). Chapter-loop challenge batch is retired.

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
ml-saham challenge run screener.accum.score_weights \
  --compatibility-id <ACCUM_COHORT_ID> --against equal_sleeves
ml-saham challenge factor screener.accum.score_weights --all \
  --compatibility-id <ACCUM_COHORT_ID>
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
