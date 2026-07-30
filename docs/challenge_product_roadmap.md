# Challenge product roadmap

**Status:** Living plan (not a ship gate)  
**Date:** 2026-07-30  
**Audience:** maintainer + agents expanding ADR-002 PolicySpecs

Shipped catalog: [challenge_product.md](./challenge_product.md)  
Engine gaps: [engine_factor_map.md](./engine_factor_map.md)  
Live enter-stack inventory (ai-saham): `docs/evidence_diagnostic_factor_accum.md`  
Curriculum build order: [roadmap.md](../roadmap.md) (orthogonal — learning chapters)

**Never auto-promote into ai-saham.** Challenge output = human decision support only ([BOUNDARY.md](../BOUNDARY.md)).

---

## North star

Ship **versioned PolicySpec tournaments** for production decisions you actually retune — not a mirror of every YAML knob, and not a clone of the accum enter inventory.

```text
ai-saham live judgment map  →  evidence_diagnostic_factor_accum.md
ml-saham product challenge  →  PolicySpec + protocol + English artifact
curriculum                  →  explore / demo / compare (never promotion authority)
```

| Question | Product answer today |
|----------|----------------------|
| Whole evidence + diagnostic inventory under challenge? | **No** |
| What is product-challenged on the **accum** journey? | **AccumScore sleeves only** (7 enabled after P0; BB off) |
| Can challenge tune “should we ENTER this ticker?” | **No** — only sleeve / score rules vs protocol labels |
| Pre-open? | Separate lane (2 policies already shipped) |

---

## Coverage snapshot (accum enter stack)

Legend: **Product** = ADR-002 `challenge run` / `factor` / `engine` / `champion` / `health` · **Curriculum** = learn labs only · **None** = no dedicated product or lab for that role.

| Inventory area (ai-saham) | Status | Notes |
|---------------------------|--------|--------|
| Hard filters (§3) | **None** product | Window multi-payload pick only; no filter tournament |
| Accum sleeves cons/streak/vwap/rsi/flow (§4) | **Product** | `screener.accum.score_weights` + factor + champion |
| BB / BCI (§4) | In PolicySpec, **not** enabled | BB `enabled: false`; BCI weight 0 + excluded note |
| Sector breadth bonus (§4) | **None** product | Curriculum `sector-breadth` only; not even a PolicySpec stub |
| Signal groups / flags / DecisionPolicy (§5) | **None** product | Curriculum partial; engine map: “no PolicySpec yet” |
| Named setups / phase / readiness (§6–7) | **None** product | Parked in [problem_backlog.md](../problem_backlog.md) |
| Risk gates (§8) | **None** product | Curriculum risk-ish labs only |
| Diagnostic bags / MCE (§9) | **None** product (by design on desk) | Do not promote diagnostics to Action authority |
| TradeSetup Action composition (§10-ish) | **None** | Different product from sleeve IC |

Pre-open (not this inventory): `screener.pre_open.iev_rank`, `screener.pre_open.directional_score` — keep on a **separate lane**.

---

## Principles (how we expand)

1. **One PolicySpec = one falsifiable H0** under a fixed protocol (ADR-002).  
2. Prefer **ablations, reweights, gate off, threshold shifts** over new curriculum chapters.  
3. **Decision type matches the production knob** (`score` / `rank` / `gate` / later `action`) — do not force rank IC onto gates.  
4. **Data readiness gate:** observation (or cache) fields must already be capturable; else `BLOCKED_DATA` is honest, not a ship failure of the *idea*.  
5. Curriculum (`accum-macro`, `accum-deep`, …) may **demo** full-stack ideas; it never defines the challenge catalog.  
6. Diagnostics (ADR-057) stay **explain-only** unless production wires them into score/Action.

---

## Phases

### P0 — Close the AccumScore lab

**Goal:** PolicySpec mirrors production Accum book more honestly; docs stop over-claiming.

| # | Work | Exit when |
|---|------|-----------|
| P0.1 | **BCI (`bci` / `inst`) as enabled sleeve** | **Done** — enabled weight 8.3; factor list + extract via `inst` |
| P0.2 | **Sector breadth bonus** as first-class component | **Done** — `sector_breadth` weight 10.0; fingerprint/candidate extract |
| P0.3 | **Coverage note in product docs** | **Done** — this file + product/engine map |
| P0.4 | Optional: **BB sleeve** enable only if production re-enables BB | Still off (matches production) |

**Protocol:** keep `accum_path_v1` (excess vs IHSG, primary H=10).  
**Surfaces:** existing `challenge run` / `factor` / `champion` / `engine screener --scenario accum`.  
**Non-goal:** Action ENTER accuracy.

Suggested policy evolution:

- Prefer **extend** `screener.accum.score_weights` v1 → v2 (same `policy_id`, version/hash bump) when still “weighted sleeves.”  
- Split a new policy only if decision type changes (e.g. pure gate).

---

### P1 — Screen knobs that veto candidates *(when you retune them)*

**Goal:** Challenge eligibility / board filters as **gates**, not sleeve IC.

| Candidate policy_id | Decision type | Question |
|---------------------|---------------|----------|
| `screener.accum.hard_filters` (name TBD) | `gate` | Does raising/lowering `min_net_buy_days`, mcap/Piotroski floors, `min_accum_score` change path quality under protocol? |

| # | Work | Exit when |
|---|------|-----------|
| P1.1 | Define gate protocol (universe in/out + forward excess or path-label join) | Spec + min-N / BLOCKED_DATA rules written |
| P1.2 | Challengers: `threshold_shift`, `gate_off:<name>` | Tournament runs on maintainer DB or honest thin-data |
| P1.3 | Register under engine `screener` / scenario `accum` when stable | `challenge engine list` shows it |

**Skip P1** if production keeps floors at 0 / off and you never move them.

---

### P2 — Signal score path *(score that moves Action)*

**Goal:** PolicySpecs for production signal evidence — still not full TradeSetup.

| Candidate policy_id | Focus |
|---------------------|--------|
| `signal.accum.flow_setup_weights` (TBD) | Flow group weight / cap, setup quality weight when attached |
| `signal.accum.flags` (TBD) | VALUATION / ANALYST / INSIDER penalties |
| `signal.accum.classification` (TBD) | 70 / 45 cutoffs → preliminary ENTER/WATCH/AVOID **as score bands**, not Action desk |

| # | Work | Exit when |
|---|------|-----------|
| P2.0 | **Data contract:** confirm observation payloads embed group scores / flags / raw signal | Extractors green or documented gaps |
| P2.1 | First Signal PolicySpec + protocol (reuse excess@H or add path-label protocol later) | `challenge list` includes signal policy |
| P2.2 | Engine portfolio: new engine_id `signal` **or** scenario under screener — pick one and document | `challenge engine list` truthful |
| P2.3 | Factor track only where multi-sleeve weights exist | KEEP/DEMOTE meaningful |

**Curriculum stays secondary:** insider / forward-valuation / analyst-consensus chapters do not replace P2.

Pre-open `directional_score` already challenges `signal.raw_score` on the **pre-open** path — do not conflate with accum Action.

---

### P3 — Risk gates *(hard Action override)*

**Goal:** `gate` policies for RiskEngine hard blocks.

| Candidate | Challengers | Label idea |
|-----------|-------------|------------|
| Fundamental / liquidity / free float / bandar | `gate_off`, threshold ± | Forward bad path, or “blocked would have avoided large loss” honesty metrics |
| Technical (opt-in re-judge) | same | Only if production uses it |

| # | Work | Exit when |
|---|------|-----------|
| P3.1 | Protocol for gate FP/FN vs forward outcomes (not rank IC alone) | Written + min-N |
| P3.2 | First risk PolicySpec registered | Engine map updates Signal/Risk rows |
| P3.3 | Health recipe can include risk row | Optional control-tower extension |

Engine map today: **RiskEngine — no PolicySpec portfolio yet** — P3 is what flips that.

---

### P4 — Setup readiness & Action *(last; different product)*

Only after P2–P3 have honest data:

| Work | Why last |
|------|----------|
| Named setup match / phase / readiness tournaments | Needs stable family + phase in captures (ADR-058) |
| **Action-level protocol** (ENTER universe vs excess / path labels) | Different H0 from sleeve IC; risk-first composer |
| MCE / diagnostic bags as score authority | Only if production DecisionPolicy wires them |

Parked ideas remain in [problem_backlog.md](../problem_backlog.md) until promoted with a one-sentence H0.

---

## Parallel track: diagnostic validity (shipped v1)

Explain-only bags are **not** P0–P4 PolicySpecs. They use a separate Challenge purpose:

**[challenge_diagnostic_validity.md](./challenge_diagnostic_validity.md)** — `KEEP_DISPLAY` / `DEMOTE_DISPLAY` / `PROMOTE_CANDIDATE` (never Action; promote only by starting a tune PolicySpec).

**Shipped bags:** `mce.screen_display`, `sector.peer_context` · CLI: `challenge diagnostic list|run|health`.

`PROMOTE_CANDIDATE` feeds this roadmap (e.g. sector bag residual strength → P0 breadth sleeve design).

---

## Explicit non-goals

| Non-goal | Why |
|----------|-----|
| Challenge every row of `evidence_diagnostic_factor_accum.md` as production PolicySpec | Inventory is live judgment; production product is falsifiable policies; diagnostics use the diagnostic track instead |
| Auto-promote WIN into ai-saham YAML | BOUNDARY / ADR-002 |
| Treat `learn compare accum-macro` / `accum-deep` as product | Pedagogy only |
| Rank IC as the only metric for gates/Action | Wrong decision type |
| Promote diagnostic panels to Action challenge by default | ADR-057 |
| Merge pre-open and accum into one “ENTER” super-policy | Separate journeys and protocols |

---

## Data readiness checklist (before coding a policy)

Copy into the PR / decision memo:

1. **Engine** that owns the decision (screener / signal / risk / MCE).  
2. **Tables / observation fields** available read-only in SQLite.  
3. **Decision type** (`score` | `rank` | `gate` | `action`).  
4. **Protocol** (horizons, label, folds, min N) — reuse or new versioned id.  
5. **Production baseline** source (PolicySpec JSON mirror / payload-embedded).  
6. **Challengers** (ablation-first).  
7. **Engine portfolio registration** yes/no.  
8. **Curriculum** only if the *problem* is non-obvious (never as promotion path).

---

## Suggested build order (one line)

```text
P0 Accum sleeves honesty (BCI + sector breadth + docs)
  → P1 hard filters (only if knobs move)
  → P2 signal score / flags / cuts
  → P3 risk gates
  → P4 readiness + Action protocol
```

Pre-open lane: maintain / densify data for existing policies; optional feature sleeves on `directional_score` when captures stabilize — **parallel**, not blocking P0–P3.

---

## Related

| Doc | Role |
|-----|------|
| [challenge_product.md](./challenge_product.md) | Shipped commands + catalog |
| [engine_factor_map.md](./engine_factor_map.md) | Engine → policy → curriculum |
| [challenge_accum_score_weights.md](./challenge_accum_score_weights.md) | Current accum policy operator note |
| [challenge_factor_validity.md](./challenge_factor_validity.md) | Factor KEEP/DEMOTE |
| [challenge_champion.md](./challenge_champion.md) | Beat-production scorer track |
| [problem_backlog.md](../problem_backlog.md) | Unscheduled ideas |
| [adr/ADR-002-ideal-challenge-system.md](./adr/ADR-002-ideal-challenge-system.md) | Ideal system |
| [BOUNDARY.md](../BOUNDARY.md) | ml-saham vs ai-saham ownership |
