# Roadmap — `ml-saham`

Build order and status for the personal IDX **challenge lab** (`ai-saham` sibling).

| Priority | Axis | Job |
|----------|------|-----|
| **1** | **Challenge** | Stress-test frozen production-like policies on read-only SQLite — **tune** + **champion** |
| **2** | **Learning** | Curriculum onboarding so audits are interpretable — **not** promotion authority |

**Product map:** [docs/challenge_product.md](./docs/challenge_product.md)  
**Policy expansion plan:** [docs/challenge_product_roadmap.md](./docs/challenge_product_roadmap.md)  
**ADRs:** [ADR-001 challenge-first](./docs/adr/ADR-001-challenge-first-product-axis.md) · [ADR-002 ideal challenge system](./docs/adr/ADR-002-ideal-challenge-system.md)  
**Boundary:** [BOUNDARY.md](./BOUNDARY.md) · **Acceptance:** [challenge_acceptance.md](./challenge_acceptance.md)

Curriculum design (secondary): [chapters.md](./chapters.md) · [ux.md](./ux.md) · historical MVP checklists below.

Early drafts (local only): `archive/` (gitignored).

---

## North star

Ship a Typer CLI whose **primary path** is:

```text
doctor / vet
  → challenge run | factor | engine | champion | health | promote-packet
  → English artifacts + human decision memos
  → never auto-promote into ai-saham
```

Learning (`learn list|explore|demo|compare`) stays installed and useful, but **loses priority conflicts** to challenge work (ADR-001).

| Challenge purpose | Question | Status |
|-------------------|----------|--------|
| **Tune** | Is this **factor** worth it? Are **weights / combination** sensible? | **Shipped** |
| **Champion** | Is there a **better scoring rule** than production under the same protocol? | **Shipped** (accum default) |

Not investment advice. Artifacts never write ai-saham YAML/code.

---

## Product model (current)

```text
ml-saham
├── Challenge (primary)          English audit lab
│     ├── tune                   factor worth + weights/combo
│     │     run · factor · engine rollup
│     ├── champion               learned score rule vs production
│     ├── diagnostic             explain-only bags (shipped v1)
│     │     KEEP_DISPLAY · DEMOTE_DISPLAY · PROMOTE_CANDIDATE
│     └── control tower          health · promote-packet
└── Learning (secondary)         Indonesian pedagogy
      learn list · explore · demo · compare
```

Diagnostic track: [docs/challenge_diagnostic_validity.md](./docs/challenge_diagnostic_validity.md) · `challenge diagnostic list|run|health`.

| Term | Meaning | Example |
|------|---------|---------|
| **Engine** | Stack audit group | `screener` |
| **Scenario** | Screen path | `accum`, `pre-open` |
| **Policy** | Frozen PolicySpec tournament | `screener.accum.score_weights` |
| **Protocol** | Evaluation law (labels, horizons, folds) | `accum_path_v1` (primary H=10) |
| **Tune** | Production baseline vs clean challengers / factor KEEP·DEMOTE | `equal_sleeves`, drop-factor |
| **Champion** | Production baseline vs learned scorer | `lgbm_reweight` |

SSOT: `src/ml_saham/challenge/` · curriculum registry: `src/ml_saham/chapters/registry.py`.

---

## Shipped (challenge baseline)

### Catalog

| Scenario | Policy | Protocol (primary) | Tracks |
|----------|--------|--------------------|--------|
| `accum` | `screener.accum.score_weights` | `accum_path_v1` (**H=10** excess vs IHSG) | tune · factor · champion · health |
| `pre-open` | `screener.pre_open.iev_rank` | `pre_open_session_v1` (open→close) | tune · engine |
| `pre-open` | `screener.pre_open.directional_score` | `pre_open_session_v1` | tune · engine |

**Engine portfolio:** `screener` only (`challenge engine list`).  
Signal / Risk / MCE: **no PolicySpec portfolio yet** — see expansion plan.

### Surfaces

| Command | Job |
|---------|-----|
| `challenge list` | Policy ids + protocols |
| `challenge run <policy>` | Production vs challenger (**tune**) |
| `challenge factor …` | KEEP / DEMOTE / DROP_CANDIDATE (accum sleeves) |
| `challenge champion` | Learned score rule vs production |
| `challenge engine screener` | PolicySpec portfolio rollup (`--scenario` optional) |
| `challenge health` | Control tower pack (engine ± champion ± factors) |
| `challenge promote-packet` | Human promote/reject checklist (never applies) |
| `vet` / `doctor --deep` | Data-plane gate before audits |

Operator notes: [docs/challenge_*.md](./docs/) · map: [docs/engine_factor_map.md](./docs/engine_factor_map.md).

### Honest coverage (accum enter stack)

Product challenge for the **accumulation journey** is **not** the full ai-saham enter desk. Today it is **AccumScore weighted sleeves** (seven enabled factors after P0 BCI + sector_breadth; BB off) under rank IC vs excess return — not Action ENTER accuracy.

Live inventory (ai-saham): `docs/evidence_diagnostic_factor_accum.md`.  
Gap plan: [docs/challenge_product_roadmap.md](./docs/challenge_product_roadmap.md).

---

## Forward plan (challenge product)

Ordered expansion of **PolicySpecs** — not new curriculum chapters. Full detail and exit criteria: **[docs/challenge_product_roadmap.md](./docs/challenge_product_roadmap.md)**.

| Phase | Focus | Outcome |
|-------|--------|---------|
| **P0** *(next)* | AccumScore honesty: **BCI + sector breadth** (+ docs coverage) | Sleeves closer to production book; same `accum_path_v1` |
| **P1** | Screen hard filters / thresholds as **gate** policies | Only if production knobs actually move |
| **P2** | **Signal** score / flags / classification PolicySpecs | New decision surface; engine map updates |
| **P3** | **Risk** gate FP/FN policies | Hard Action override audited under gate protocol |
| **P4** | Setup readiness + **Action-level** protocol | Last; different product from sleeve IC |

**Parallel lane:** pre-open — densify data / optional feature sleeves on existing policies; do not block P0–P3.

**Non-goals:** auto-promote; challenge every diagnostic bag; treat `learn compare` as authority; rank-IC-only metrics for gates.

### Suggested immediate work

1. **P0.3 docs** — coverage callouts (partially landed in product docs).  
2. **P0.1–P0.2 code** — enable/extract BCI + sector breadth on accum PolicySpec (v2 or hash bump).  
3. Maintainer ritual: `challenge health --with-champion --with-factors` + decision memo when WIN/LOSE is actionable.  
4. Promote backlog rows only with a one-line H0 + data readiness checklist (see expansion plan).

---

## Learning (secondary)

Curriculum is **onboarding and pedagogy**. Registry lists ~45 topics; explore/demo/compare remain available.

| Track | State | Docs |
|-------|--------|------|
| MVP chapters 0, 1, 2, 3, 4, 6 | **Done** | [mvp_acceptance.md](./mvp_acceptance.md) |
| v1.1 chapters 5, 7, 9 | **Done** | [v1_1_acceptance.md](./v1_1_acceptance.md) |
| Phase-2 curriculum (registry phase-2) | **Done** | [phase2_acceptance.md](./phase2_acceptance.md) |
| New chapters | **Only if** a non-obvious problem needs teaching — prefer PolicySpec first | [problem_backlog.md](./problem_backlog.md) |

Rules:

- `learn compare <slug>` is **not** ADR-002 promotion authority.  
- Flat root `explore` / `demo` / `compare` / `chapters` are **retired** → use `ml-saham learn …`.  
- Pre-ADR-002 chapter-loop challenge batch (`ENGINE_FACTORS` / `challenge legacy`) is **retired**.

Optional UX (low priority, on demand): `demo --plot`, notebook export, TUI browser — do not schedule ahead of challenge P0–P2.

---

## Foundation history (curriculum build — complete)

Historical phase ladder used to stand up the package. **All curriculum phases below are done**; kept for archaeology and acceptance links. New work does **not** continue “Phase 7 as main focus.”

| Phase | Goal | State |
|-------|------|--------|
| 0 | Scaffold package + CLI + registry | **Done** |
| 1 | Read-only data plane + `doctor` | **Done** |
| 2 | Shared metrics + artifacts + explore UX | **Done** |
| 3–4 | MVP chapters + harden | **Done** — [mvp_acceptance.md](./mvp_acceptance.md) |
| 5 | v1.1 chapters | **Done** — [v1_1_acceptance.md](./v1_1_acceptance.md) |
| 6 | Phase-2 curriculum | **Done** — [phase2_acceptance.md](./phase2_acceptance.md) |

MVP dependency graph (historical):

```text
scaffold → doctor + readers → metrics/artifacts
  → orientasi → clean-prices | screen-rules | pattern-fail | factor-score | broker-flow
  → harden → MVP done → v1.1 → phase-2 curriculum done
```

Challenge product then **superseded** chapter-loop audits as the primary ship path (ADR-001 / ADR-002, 2026-07-29).

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Agents re-center on “finish the course” | ADR-001; this roadmap’s priority table; challenge SSOT in `src/ml_saham/challenge/` |
| Confusing curriculum demos with production authority | BOUNDARY + challenge reports always English; no auto-promote |
| Scope creep to full enter-stack | Expansion plan P0–P4; inventory stays in ai-saham doc |
| ai-saham schema drift | [data_contract.md](./data_contract.md); doctor/vet; honest `BLOCKED_DATA` |
| Importing ai-saham Python | Architecture boundary + review |
| Learning-store / ETL too early | Direct SQLite first; materialize only when blocked |
| Champion mistaken for “SOTA literature” | [docs/sota_vocabulary_and_literature.md](./docs/sota_vocabulary_and_literature.md) |

---

## Immediate next actions

1. **Challenge P0** — BCI + sector breadth sleeves (or explicit production-parity decision memo if deferred).  
2. Run **control tower** on maintainer DB when retuning: `challenge health --with-champion --with-factors`.  
3. Expand PolicySpecs only per [docs/challenge_product_roadmap.md](./docs/challenge_product_roadmap.md) + data readiness checklist.  
4. Curriculum: maintenance / bugfix only unless a new **teaching** problem is justified in [problem_backlog.md](./problem_backlog.md).

---

## Status

| Item | State |
|------|--------|
| Product priority | **Challenge-first** (tune + champion) — ADR-001 |
| Challenge catalog (3 policies, screener engine) | **Shipped** — [challenge_acceptance.md](./challenge_acceptance.md) |
| Champion + health + promote-packet | **Shipped** |
| Factor validity (accum sleeves) | **Shipped** |
| Diagnostic validity (display / promote-candidate) | **Shipped v1** (MCE + sector bags) |
| Curriculum MVP → phase-2 | **Done** (secondary) |
| PolicySpec expansion P0–P4 | **Planned** — [docs/challenge_product_roadmap.md](./docs/challenge_product_roadmap.md) |
| Current focus | **P0 AccumScore honesty** + diagnostic bag expansion + maintainer ritual |
| Idle / on-demand only | Phase-7-style UX extras, new chapters without PolicySpec H0 |
