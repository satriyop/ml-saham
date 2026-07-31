# Challenge product (ml-saham)

English overview of the **shipped** ADR-002 challenge lab.  
Design intent: [ADR-001](./adr/ADR-001-challenge-first-product-axis.md) · [ADR-002](./adr/ADR-002-ideal-challenge-system.md).  
Sibling ownership vs ai-saham: **[BOUNDARY.md](../BOUNDARY.md)** (ingest/corpus labels vs challenge protocol labels).

**Not investment advice. Never auto-promotes into `ai-saham`.**

---

## Operator ritual (SSOT)

Recommended maintainer path — same Typer verbs; no TUI.

| Step | When | Command | Purpose |
|------|------|---------|---------|
| **1. Catalog** | Always start here | `ml-saham challenge list` | **One entry point** for all production PolicySpecs + dig hints (screener / signal / gate / factor / diagnostic) |
| **2. Weekly tower** | Weekly (or after big capture refresh) | `ml-saham challenge health --with-diagnostics` | Screener tune rollup + **display bags** (not Action). Optional: `--with-factors` / `--with-champion` |
| **3. Deep dig** | Only when retuning that knob | `challenge engine signal --scenario accum` · `challenge engine risk --scenario accum` · `challenge run …` | Signal / risk / single-policy tournaments — **not** the weekly default |
| **4. Diagnostics → production?** | After `PROMOTE_CANDIDATE` | Design a **new PolicySpec** → `challenge run` / `factor` (tune) → human memo | **Never** treat diagnostic verdicts as TradeSetup Action |
| **5. Action ENTER (P4)** | Only when ready | Deferred | Needs dense Action + labels and a real ENTER H0 — **not** more rank IC |

```bash
# 1 — catalog
ml-saham challenge list

# 2 — weekly ritual
ml-saham challenge health --with-diagnostics
# optional deeper weekly: --with-factors --with-champion
# install cron: ./scripts/install_challenge_health_cron.sh

# 3 — on-demand digs (when retuning)
ml-saham challenge engine signal --scenario accum
ml-saham challenge engine risk --scenario accum --against gate_off
ml-saham challenge run screener.accum.score_weights --against equal_sleeves

# 4 — diagnostic promote ladder (never Action)
ml-saham challenge diagnostic run mce.screen_display --all
# PROMOTE_CANDIDATE ⇒ write PolicySpec design ⇒ challenge run/factor ⇒ human ai-saham change
```

Hard rules:

- **`challenge list`** is the catalog; do not invent a parallel inventory of policies.  
- **Signal/risk engines** are dig surfaces after list — not the weekly default.  
- **`PROMOTE_CANDIDATE` / KEEP_DISPLAY never set ENTER/Action** (ADR-057).  
- **P4 Action desk** stays deferred until data + H0 exist ([challenge_product_roadmap.md](./challenge_product_roadmap.md)).

Related: [challenge_health.md](./challenge_health.md) · [challenge_diagnostic_validity.md](./challenge_diagnostic_validity.md)

---

## What it is

`ml-saham` **challenge** stress-tests **frozen production-like policies** (PolicySpecs) from the personal IDX stack against clean challengers, on **read-only** `ai-saham` SQLite.

| In scope | Out of scope |
|----------|----------------|
| Policy tournaments (WIN / LOSE / INCONCLUSIVE / BLOCKED_*) | Auto-writing ai-saham YAML/code |
| Factor keep/demote (accum sleeves) | Replacing `ai-saham` ingest/engines |
| Engine portfolio rollups | Curriculum demos as promotion authority |
| English audit reports + artifacts | Live trading / paper broker |
| **Champion track** — beat production with a learned score rule | Treating curriculum “Default” models as production authority |
| **Health / promote-packet** — control tower packs | Auto-writing ai-saham YAML |

Learning (`ml-saham learn …`) is **secondary** and mostly Indonesian for pedagogy.

---

## Two purposes under Challenge (tune vs champion)

Still **one axis** (Challenge), two **purposes / tracks**. Not a third top-level axis like Learning.

| Track | Purpose | You care about ai-saham factors / weights / formula? | Question |
|-------|---------|------------------------------------------------------|----------|
| **Challenge (tune)** — **shipped** | Help humans **tune** production policy | **Yes** | (1) Is this **factor** worth it? (2) Are **weights & combination** sensible? |
| **Challenge champion** — **shipped** (accum) | Find a **better scoring rule** that beats production | **No** (internals optional / black-box OK) | (3) Is there a contender that **replaces** production score under the same protocol? |

```text
ml-saham
├── Learning              teach methods (Default vs Baseline demos)
└── Challenge             English audit lab (production baseline, no auto-promote)
      ├── tune            factor worth? · weights/combo OK?     ← shipped
      │     policy tournament · factor validity · engine rollup
      ├── champion        better score rule than production?  ← shipped
      └── diagnostic      explain-only bags: keep/hide display · promote-candidate  ← shipped v1
```

Diagnostic validity: [challenge_diagnostic_validity.md](./challenge_diagnostic_validity.md) — **not** Action authority; `PROMOTE_CANDIDATE` only opens a tune PolicySpec design.

```bash
ml-saham challenge diagnostic list
ml-saham challenge diagnostic run mce.screen_display --all
ml-saham challenge diagnostic health --scenario accum
```

| | **Tune** | **Champion** |
|--|----------|--------------|
| Baseline | Always **`production`** | Always **`production`** |
| Typical against | `equal_sleeves`, `ridge_reweight`, drop-factor | `lgbm_reweight`, `elastic_net_reweight` |
| If WIN | Maybe retune weights / demote factor | Maybe **adopt a new scorer** (bigger human change) |
| Protocol / folds / labels | Required | Required (same honesty; train-only fit) |
| Auto-promote to ai-saham | **Never** | **Never** |
| CLI | `challenge run` / `factor` / `engine` | **`challenge champion`** |

**Champion is not Learning.** Curriculum LightGBM demos stay non-authority.  
**Champion is not “SOTA.”** It is “beats production under protocol → human promote review.”  
Operator: [challenge_champion.md](./challenge_champion.md).

### Control tower (shipped)

| Command | Purpose |
|---------|---------|
| **`challenge health --with-diagnostics`** | **Weekly ritual:** screener tune + display bags (see Operator ritual) |
| **`challenge health --with-factors` / `--with-champion`** | Optional deeper weekly pack |
| **`challenge promote-packet`** | Human checklist from export JSON / artifact (never applies) |

Operator: [challenge_health.md](./challenge_health.md).

---

## Vocabulary (aligned with ai-saham)

| Term | Meaning | Examples |
|------|---------|----------|
| **Engine** | Product stack audit group | `screener` |
| **Scenario** | Screen path inside an engine (ADR-047 / research CLI) | `accum`, `pre-open` |
| **Policy** | One frozen PolicySpec + protocol tournament | `screener.accum.score_weights` |
| **Protocol** | Evaluation law (labels, horizons, folds) | `accum_path_v1`, `pre_open_session_v1` |
| **Challenger** | Named alternative under the same decision type | `equal_sleeves`, `ridge_reweight` |
| **Tune** | Challenge purpose: factor + weight/combo audit | `challenge factor`, `run --against equal_sleeves` |
| **Champion** | Challenge purpose: beat production with a better score rule | `challenge champion`, `lgbm_reweight` |

Prefer **`--scenario`**, not “track,” for accum vs pre-open.  
Prefer **tune vs champion** for purpose (not a third product axis).

---

## Coverage (honest)

**Accum enter stack (honest):**

| Layer | Product surface |
|-------|-----------------|
| Accum sleeves (7; BB off) | `screener.accum.score_weights` |
| Signal | `raw_score` · `flags` · `classification` · **`evidence_group_weights`** |
| Risk hard gates | `risk.accum.hard_gates` (+ `gate_off:<gate>`; mean excess open) |
| Weekly cron | `scripts/install_challenge_health_cron.sh` → `health --with-diagnostics` |
| Diagnostics | `challenge diagnostic` (display/promote-candidate only) |
| Screen hard filters (P1) | **Skipped** (unused knobs) |
| Action ENTER desk (P4) | **Deferred** |

Expansion plan: **[challenge_product_roadmap.md](./challenge_product_roadmap.md)**.  
Live judgment inventory (ai-saham): `docs/evidence_diagnostic_factor_accum.md`.

---

## Catalog (shipped)

### Engine: `screener`

| Scenario | Policy id | Protocol | Operator note |
|----------|-----------|----------|---------------|
| `accum` | `screener.accum.score_weights` | `accum_path_v1` (primary **H=10**, report 3/10/20) | [challenge_accum_score_weights.md](./challenge_accum_score_weights.md) |
| `pre-open` | `screener.pre_open.iev_rank` | `pre_open_session_v1` (same-session open→close, H=0) | [challenge_pre_open_iev_rank.md](./challenge_pre_open_iev_rank.md) |
| `pre-open` | `screener.pre_open.directional_score` | `pre_open_session_v1` | [challenge_pre_open_directional_score.md](./challenge_pre_open_directional_score.md) |

### Engine: `signal`

| Scenario | Policy id | Protocol | Operator note |
|----------|-----------|----------|---------------|
| `accum` | `signal.accum.raw_score` | `accum_path_v1` | [challenge_signal_raw_score.md](./challenge_signal_raw_score.md) |
| `accum` | `signal.accum.flags` | `accum_path_v1` | vs `flags_off` (penalties 10/8/12) |
| `accum` | `signal.accum.classification` | `accum_path_v1` | vs `threshold_shift` (70/45 bands) |
| `accum` | `signal.accum.evidence_group_weights` | `accum_path_v1` | setup 0.60 / flow 0.40; [note](./challenge_signal_evidence_group_weights.md) |

### Engine: `risk`

| Scenario | Policy id | Protocol | Operator note |
|----------|-----------|----------|---------------|
| `accum` | `risk.accum.hard_gates` | `accum_path_v1` (metric: mean excess among allowed) | [challenge_risk_hard_gates.md](./challenge_risk_hard_gates.md) |

**Engine portfolio:** `challenge engine list` · [challenge_engine_screener.md](./challenge_engine_screener.md)  
**Factor validity (accum sleeves):** [challenge_factor_validity.md](./challenge_factor_validity.md)  
**Diagnostics:** [challenge_diagnostic_validity.md](./challenge_diagnostic_validity.md)  
**Engine → data map:** [engine_factor_map.md](./engine_factor_map.md)

### Outcomes

| Status / verdict | Meaning |
|------------------|---------|
| `WIN` / `LOSE` / `INCONCLUSIVE` | Challenger vs production under protocol rules. **WIN requires ≥2 valid OOS folds** (+ fold-agree / margin / tail). A single post-embargo fold with an IC edge is **INCONCLUSIVE** (“promising but provisional”), not promotion-ready. |
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
ml-saham challenge run signal.accum.raw_score --against equal_sleeves
ml-saham challenge run risk.accum.hard_gates --against gate_off

# Engine rollup
ml-saham challenge engine list
ml-saham challenge engine screener
ml-saham challenge engine signal --scenario accum
ml-saham challenge engine risk --scenario accum

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

### Tune (shipped)

1. **`challenge engine screener`** — “How is the screener stack?”  
2. **`challenge run <policy>`** — dig weights/combo vs equal or ridge.  
3. **`challenge factor …`** — is this sleeve worth it?  
4. Write a **human decision memo** if needed (example: [decisions/accum_score_weights_2026-07-29.md](./decisions/accum_score_weights_2026-07-29.md)).  
5. **Do not** promote into ai-saham from a single thin window or BLOCKED run.

### Champion (shipped)

```bash
ml-saham challenge champion screener.accum.score_weights --model lgbm_reweight
```

1. Same protocol and production baseline.  
2. Learned scorer fit **only on train folds**.  
3. If **WIN** (and folds/stability OK) → promote-candidate **memo** only — human may redesign ai-saham scoring; ml-saham does not write config.  
4. See [challenge_champion.md](./challenge_champion.md).

### Health + promote (shipped)

```bash
# Weekly default (screener + display diagnostics)
ml-saham challenge health --with-diagnostics

# Deeper optional weekly pack
ml-saham challenge health --with-diagnostics --with-factors --with-champion

ml-saham challenge promote-packet --from-json /tmp/champ.json
```

See [challenge_health.md](./challenge_health.md) · ritual SSOT above.

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
| `learn compare` / `learn demo` | Curriculum / lab (chapter `run_compare` is pedagogy only) |
| `learn explore` | Indonesian problem framing |

Pre-ADR-002 chapter-loop batch (`challenge legacy` / `ENGINE_FACTORS`) is **retired** — not available as a product path.

---

## Doc index

| Doc | Role |
|-----|------|
| This file | Product map + commands |
| [challenge_extract_contract.md](./challenge_extract_contract.md) | **Ship gate:** golden payloads, PR checklist, anti-patterns, CI script |
| [challenge_product_roadmap.md](./challenge_product_roadmap.md) | Planned PolicySpec expansion (P0–P4); not a ship gate |
| [challenge_diagnostic_validity.md](./challenge_diagnostic_validity.md) | Diagnostic track (display keep/hide / promote-candidate) — shipped v1 |
| [challenge_champion.md](./challenge_champion.md) | Champion track (learned vs production) |
| [challenge_health.md](./challenge_health.md) | Health report + promote-packet control tower |
| [challenge_engine_screener.md](./challenge_engine_screener.md) | Engine portfolio operator note |
| [challenge_accum_score_weights.md](./challenge_accum_score_weights.md) | Accum policy |
| [challenge_pre_open_iev_rank.md](./challenge_pre_open_iev_rank.md) | Pre-open IEV rank |
| [challenge_pre_open_directional_score.md](./challenge_pre_open_directional_score.md) | Pre-open observation / raw_score |
| [challenge_factor_validity.md](./challenge_factor_validity.md) | Factor track |
| [engine_factor_map.md](./engine_factor_map.md) | Engines ↔ tables ↔ policies |
| [data_contract.md](../data_contract.md) | Live SQLite tables; **label ownership** (corpus = ai-saham, challenge **y** = protocol / artifacts only) |
| [BOUNDARY.md](../BOUNDARY.md) | Repo split: what ai-saham vs ml-saham owns (mirror next to ai-saham) |
| [sota_vocabulary_and_literature.md](./sota_vocabulary_and_literature.md) | “SOTA” ≠ literature frontier; chapter vs challenge models |
| [adr/](./adr/) | Locked product decisions |

---

## One-line summary

> **Challenge = versioned PolicySpec tournaments (+ factor / engine rollups) under fixed protocols, English artifacts, no auto-promotion — learning stays optional.**
