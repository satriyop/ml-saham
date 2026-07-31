# Challenge product roadmap

**Status:** Living plan (not a ship gate)  
**Date:** 2026-07-31
**Audience:** maintainer + agents expanding ADR-002 PolicySpecs

Shipped catalog: [challenge_product.md](./challenge_product.md)  
Engine gaps: [engine_factor_map.md](./engine_factor_map.md)  
Live enter-stack inventory (ai-saham): `docs/evidence_diagnostic_factor_accum.md`  
Root pointer: [roadmap.md](../roadmap.md) · Curriculum catalog: [chapters.md](../chapters.md) (orthogonal — learning)

**Never auto-promote into ai-saham.** Challenge output = human decision support only ([BOUNDARY.md](../BOUNDARY.md)).

---

## North star

Give every material production influence an explicit validation owner and
method. Ship **versioned PolicySpec tournaments** for independently tunable
decisions; use factor validity, gate evaluation, Action protocols, diagnostic
validity, or PIT/data-quality contracts where those are the correct tests.

The goal is complete **decision coverage**, not a mechanical one-inventory-row
to one-PolicySpec mapping. An inventory row may be a policy lever, a component,
a derived result, a display-only diagnostic, or a raw input; treating all five
as equivalent tournaments would duplicate correlated tests and apply the wrong
metric to gates, diagnostics, and Action.

```text
ai-saham live judgment map  →  evidence_diagnostic_factor_accum.md
ml-saham product challenge  →  PolicySpec + protocol + English artifact
curriculum                  →  learn explore / demo / compare (never promotion authority)
```

| Question | Product answer today |
|----------|----------------------|
| Whole material enter stack has explicit validation coverage? | **No — product gaps are tracked below** |
| What is product-challenged on the **accum** journey? | Accum sleeves, signal policies, and risk gates; diagnostics use a separate display-validity track |
| Screen hard filters? | Snapshot identity + replay extract shipped; production tournament still `BLOCKED_POLICY` |
| Can challenge tune “should we ENTER this ticker?” | **No** — Action/readiness protocol and usable corpus are both missing |
| Pre-open? | Separate lane (2 policies already shipped) |

---

## Validation coverage standard

Every inventory item that can materially affect eligibility, score, readiness,
risk, or final Action must map to one of these owned validation surfaces. “Not
a PolicySpec” must never mean “not validated.”

| Production role | Required validation surface |
|-----------------|-----------------------------|
| Independently tunable score/rank policy | PolicySpec tournament under a fixed Protocol |
| Component inside a score | Factor validity plus ablation/permutation and fold stability |
| Eligibility or risk veto | Gate evaluation: harmful allow, false block/opportunity cost, block rate, and stability |
| Setup readiness / final Action | Dedicated Action protocol with outcome definition and class/population reporting |
| Display-only diagnostic | Diagnostic validity; no Action authority without a new production PolicySpec |
| Raw enrichment / source field | PIT, availability, reconciliation, and data-quality contract |
| Derived or duplicated representation | Extract/conformance test; do not create a duplicate tournament |

## Current product gaps — priority order

Live counts below are a **2026-07-31 22:49 WIB maintainer-DB snapshot**, not
permanent acceptance constants.

| Priority | Gap | Current evidence | Owner / exit condition |
|----------|-----|------------------|------------------------|
| **G0** | Snapshot-bound corpus depth | Historical cohort `sha256:005363…` has 1,890 rows / 42 sessions but 0/7 v2 snapshots, so production comparison correctly returns `BLOCKED_POLICY`. Active v2 cohort `sha256:8ba8fc…` has 304 rows / 1 session / 7 snapshots and yields only one valid OOS fold. | **ai-saham:** accumulate prospective v2-bound observations across enough independent sessions/regimes. **ml-saham:** keep explicit-cohort and snapshot gates. Exit only when the fixed protocol yields at least two valid post-embargo OOS folds; never retrofit snapshots onto the historical cohort. |
| **G1** | Screen hard-filter tournament | Four-gate extract and pure replay are shipped; v2 policy identity is verified. The local adapter has no conformance evidence, is not in the screener engine portfolio, and execution returns `BLOCKED_POLICY`. | **ml-saham:** lock challenger/grid, population, outcome, false-block/opportunity-cost metrics, folds, and adapter golden conformance; then register the PolicySpec. Defaults being mostly off is not a reason to leave material eligibility logic permanently unvalidated. |
| **G2** | Configured group-breadth authority | The pure applier can add a breadth bonus, but current production factories do not inject `idx_groups`; `_ticker_to_group` is empty and the executable path skips it. ADR-059 v2 therefore correctly excludes it. The configured mapping is conglomerate/group membership, not the sector-universe index. | **ai-saham architecture first:** decide whether this is a real production policy, define group-vs-sector meaning, PIT membership, overlap and scoring order, then activate it explicitly or retire the dead configuration. Only an activated policy may receive a new snapshot and ml-saham counterfactual. |
| **G3** | Risk gate decision quality | Current lane reports mean H10 excess among allowed rows. On the current v2 slice production blocks 83% OOS and outperforms `gate_off`, but the report does not establish false-block cost, harmful-allow rate, or regime stability. | **ml-saham:** add a versioned gate protocol/report for blocked-book outcomes, opportunity cost, gate-family attribution, and multi-fold stability without weakening safety constraints. |
| **G4** | Setup readiness and final Action | These paths materially cap/override ENTER, but there is no Action Protocol. Corpus is not ready: historical cohort has only 8 ENTER and 86/1,890 non-null readiness rows; active v2 cohort has 0 ENTER and 11/304 non-null readiness rows. | **ai-saham:** produce dense PIT-bound readiness/Action observations and compatible outcomes. **ml-saham:** define a real Action H0, population, class handling, costs, and walk-forward protocol. Rank IC is not an acceptable substitute. |

Historical/no-snapshot observations remain useful for extract validation,
replay, and explicitly non-production research. They cannot be relabeled as a
verified production baseline.

---

## Coverage snapshot (accum enter stack)

Legend: **Product** = ADR-002 `challenge run` / `factor` / `engine` / `champion` / `health` · **Curriculum** = learn labs only · **None** = no dedicated product or lab for that role.

| Inventory area (ai-saham) | Status | Notes |
|---------------------------|--------|--------|
| Hard filters (§3) | **Replay shipped; tournament gap (G1)** | Verified v2 identity + pure first-match replay; adapter conformance/verdict not shipped |
| Accum sleeves (§4) | **Product, partial full-book coverage** | 6 verified components: cons/streak/vwap/rsi/flow/**bci**; **BB off**; sector breadth excluded (G2) |
| BB (§4) | Disabled | Matches production BB-off — not inventing BB-on |
| BCI (§4) | **Product (P0)** | Enabled verified component on `screener.accum.score_weights` |
| Configured group breadth (§4) | **Authority gap (G2)** | Pure applier exists, but production composition supplies no mapping and skips it; no challenge baseline yet |
| Signal raw score / groups (§5) | **Product (P2 thin)** | `signal.accum.raw_score` — raw_score + group features vs excess@H |
| Named setups / phase / readiness (§6–7) | **Product gap (G4)** | Material Action cap; sparse readiness corpus and no Action Protocol |
| Risk hard gates (§8) | **Product, thin (G3)** | `gate_off` ablation shipped; blocked-book cost and stability incomplete |
| Diagnostic bags / MCE (§9) | **Diagnostic track** | `challenge diagnostic` display/promote-candidate — **not** Action |
| TradeSetup Action composition | **Product gap (G4)** | Different decision type; current v2 corpus has zero ENTER rows |

Pre-open (not this inventory): `screener.pre_open.iev_rank`, `screener.pre_open.directional_score` — keep on a **separate lane**.

---

## Principles (how we expand)

1. **One PolicySpec = one falsifiable H0** under a fixed protocol (ADR-002).  
2. Prefer **ablations, reweights, gate off, threshold shifts** over new curriculum chapters.  
3. **Decision type matches the production knob** (`score` / `rank` / `gate` / later `action`) — do not force rank IC onto gates.  
4. **Data readiness gate:** observation (or cache) fields must already be capturable; else `BLOCKED_DATA` is honest, not a ship failure of the *idea*.  
5. Curriculum (`accum-macro`, `accum-deep`, …) may **demo** full-stack ideas; it never defines the challenge catalog.  
6. Diagnostics (ADR-057) stay **explain-only** unless production wires them into score/Action.
7. Every material production influence has a named validation method and owner,
   even when it is not a PolicySpec.
8. Historical breadth never overrides identity: no snapshot inference, fallback,
   or retrospective production eligibility.

---

## Phases

### P0 — Close the AccumScore lab — **partial; G2 remains**

**Goal:** PolicySpec mirrors production Accum book more honestly; docs stop over-claiming.

| # | Work | Exit when |
|---|------|-----------|
| P0.1 | **BCI (`bci` / `inst`) as enabled sleeve** | **Done** — enabled weight 8.3; factor list + extract via `inst` |
| P0.2 | **Configured group-breadth bonus** authority decision | **Open (G2)** — currently skipped by production composition; activate/retire through ai-saham architecture before any snapshot/challenge |
| P0.3 | **Coverage note in product docs** | **Done** — this file + product/engine map |
| P0.4 | Optional: **BB sleeve** enable only if production re-enables BB | Still off (matches production) |

**Protocol:** keep `accum_path_v1` (excess vs IHSG, primary H=10).  
**Surfaces:** existing `challenge run` / `factor` / `champion` / `engine screener --scenario accum`.  
**Non-goal:** Action ENTER accuracy.

Suggested policy evolution:

- Prefer **extend** `screener.accum.score_weights` v1 → v2 (same `policy_id`, version/hash bump) when still “weighted sleeves.”  
- Split a new policy only if decision type changes (e.g. pure gate).

---

### P1 — Screen hard filters — **replay shipped; tournament open (G1)**

The four-gate extract, missing-state contract, cohort reconciliation, pure
first-match replay, and v2 production identity are shipped. The production
tournament is not: adapter conformance, challenger/grid, winner law,
blocked-book outcomes, and engine registration remain open. Mostly-off default
floors lower urgency but do not remove the validation obligation for logic that
can reject candidates when enabled.

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

### P3 — Risk hard gates — **shipped thin; deepen open (G3)**

| policy_id | Against | Metric (not sleeve IC) |
|-----------|---------|-------------------------|
| `risk.accum.hard_gates` | `gate_off` / `gate_off:<gate>` | Mean excess among **allowed**; bandar/liquidity/fundamental/free_float/technical |

CLI: `challenge run risk.accum.hard_gates --against gate_off` · `gate_off:bandar_gate` · `challenge engine risk`.

Deepening exit: report allowed and blocked books, false-block/opportunity cost,
harmful allows, named gate-family attribution, block-rate stability, and at
least two valid OOS folds under a versioned gate protocol.

---

### P4 — Setup readiness & Action — **product gap, data-blocked (G4)**

Different product from sleeve/signal IC. **Do not** ship rank-IC “ENTER” tournaments as a substitute.

| Prerequisite | Status |
|--------------|--------|
| Dense Action + path labels in snapshot-bound captures | Missing: active v2 cohort has 0 ENTER; readiness non-null on 11/304 rows |
| Real ENTER protocol (not sleeve IC) | Not started |
| Diagnostics as Action authority | **Never** by default (ADR-057) |

Do not implement the Action verdict until the positive population, decision
cutoff, outcome/cost definition, class handling, and walk-forward split can be
specified without leakage. This is an acknowledged product gap, not a claim
that the full ENTER desk is already covered.

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
| Create one production PolicySpec per row of `evidence_diagnostic_factor_accum.md` | Rows have different roles; use the validation coverage standard above. Every material influence still needs an owner and method. |
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
5. **Production baseline** source (verified upstream snapshot plus frozen observed output where required).
6. **Challengers** (ablation-first).  
7. **Engine portfolio registration** yes/no.  
8. **Curriculum** only if the *problem* is non-obvious (never as promotion path).

---

## Suggested build order (one line)

```text
G0 v2 corpus time/fold depth      🚧 producer accumulation required
P0 Accum sleeves honesty          🚧 configured group-breadth authority gap (G2)
P1 hard filters                   🚧 replay shipped; tournament blocked (G1)
P2 signal policies                ✅ thin
P3 risk hard gates                🚧 thin; decision-quality metrics open (G3)
P4 readiness + Action protocol    ⛔ data/protocol blocked (G4)
diagnostic validity (parallel)    ✅ v1 display authority only
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
