# Challenge product roadmap

**Status:** Living plan (not a ship gate)  
**Date:** 2026-07-30  
**Audience:** maintainer + agents expanding ADR-002 PolicySpecs

Shipped catalog: [challenge_product.md](./challenge_product.md)  
Engine gaps: [engine_factor_map.md](./engine_factor_map.md)  
Live enter-stack inventory (ai-saham): `docs/evidence_diagnostic_factor_accum.md`  
Root pointer: [roadmap.md](../roadmap.md) · Curriculum catalog: [chapters.md](../chapters.md) (orthogonal — learning)

**Never auto-promote into ai-saham.** Challenge output = human decision support only ([BOUNDARY.md](../BOUNDARY.md)).

---

## North star

Ship **versioned PolicySpec tournaments** for production decisions you actually retune — not a mirror of every YAML knob, and not a clone of the accum enter inventory.

```text
ai-saham live judgment map  →  evidence_diagnostic_factor_accum.md
ml-saham product challenge  →  PolicySpec + protocol + English artifact
curriculum                  →  learn explore / demo / compare (never promotion authority)
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
| Hard filters (§3) | **P1 skipped (thin)** | Production floors often 0/off — no unused filter tournament |
| Accum sleeves (§4) | **Product** | 7 enabled: cons/streak/vwap/rsi/flow/**bci**/**sector_breadth**; **BB off** |
| BB (§4) | Disabled | Matches production BB-off — not inventing BB-on |
| BCI + sector breadth (§4) | **Product (P0)** | Enabled sleeves on `screener.accum.score_weights` |
| Signal raw score / groups (§5) | **Product (P2 thin)** | `signal.accum.raw_score` — raw_score + group features vs excess@H |
| Named setups / phase / readiness (§6–7) | **None** product | Parked; P4 later |
| Risk hard gates (§8) | **Product (P3 thin)** | `risk.accum.hard_gates` — gate_off ablation (not sleeve IC) |
| Diagnostic bags / MCE (§9) | **Diagnostic track** | `challenge diagnostic` display/promote-candidate — **not** Action |
| TradeSetup Action composition | **P4 deferred** | Different product; no fake ENTER accuracy path |

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

### P1 — Screen hard filters — **SKIPPED (thin / unused knobs)**

**Decision:** Do not ship filter tournaments while production floors stay 0/off. Revisit only when knobs are actually retuned.

---

### P2 — Signal score path — **shipped thin**

| policy_id | Focus | Status |
|-----------|--------|--------|
| `signal.accum.raw_score` | Production raw_score (+ group features) vs excess@H | **Shipped** |
| `signal.accum.flags` | raw − do-no-harm penalties vs `flags_off` | **Shipped (P2 deepen)** |
| `signal.accum.classification` | 70/45 band score vs `threshold_shift` (+5) | **Shipped (P2 deepen)** |
| `signal.accum.evidence_group_weights` | setup **0.60** / flow **0.40** vs equal / drop_setup / drop_flow | **Shipped** |

CLI: `challenge engine signal --scenario accum`.

---

### P3 — Risk hard gates — **shipped thin**

| policy_id | Against | Metric (not sleeve IC) |
|-----------|---------|-------------------------|
| `risk.accum.hard_gates` | `gate_off` / `gate_off:<gate>` | Mean excess among **allowed**; bandar/liquidity/fundamental/free_float/technical |

CLI: `challenge run risk.accum.hard_gates --against gate_off` · `gate_off:bandar_gate` · `challenge engine risk`.

---

### P4 — Setup readiness & Action — **deferred**

Different product from sleeve/signal IC. **Do not** ship rank-IC “ENTER” tournaments as a substitute.

| Prerequisite | Status |
|--------------|--------|
| Dense Action + path labels in captures | Required before any ENTER H0 |
| Real ENTER protocol (not sleeve IC) | Not started |
| Diagnostics as Action authority | **Never** by default (ADR-057) |

Operator ritual: [challenge_product.md](./challenge_product.md) § Operator ritual.

---

## Parallel track: diagnostic validity (shipped v1)

Explain-only bags are **not** P0–P4 PolicySpecs. They use a separate Challenge purpose:

**[challenge_diagnostic_validity.md](./challenge_diagnostic_validity.md)** — `KEEP_DISPLAY` / `DEMOTE_DISPLAY` / `PROMOTE_CANDIDATE` (never Action; promote only by starting a tune PolicySpec).

**Shipped bags:** `mce.screen_display`, `sector.peer_context`, `institutional.accumulation_bag`, `company_quality.bag` · CLI: `challenge diagnostic list|run|health` · `challenge health --with-diagnostics`.

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
P0 Accum sleeves honesty          ✅
P1 hard filters                   ⏭️ skipped (unused knobs)
P2 signal.accum.raw_score         ✅ thin
P3 risk.accum.hard_gates          ✅ thin (gate_off metric)
P4 readiness + Action protocol    ⏸️ deferred
diagnostic validity (parallel)    ✅ v1
```

Pre-open lane: maintain denser captures for existing IEV/directional policies — parallel.

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
