# Roadmap — `ml-saham`

Personal IDX **challenge lab** (`ai-saham` sibling). Challenge first; learning second.

| Priority | Axis | Job |
|----------|------|-----|
| **1** | **Challenge** | Policy tournaments on read-only SQLite — **tune** + **champion** + **diagnostic** |
| **2** | **Learning** | `ml-saham learn …` onboarding — **not** promotion authority |

---

## Where to go

| Doc | Role |
|-----|------|
| **[docs/challenge_product.md](./docs/challenge_product.md)** | Shipped product map + commands |
| **[docs/challenge_product_roadmap.md](./docs/challenge_product_roadmap.md)** | **Decision-coverage gaps + PolicySpec expansion (G0–G4 / P0–P4)** — living product roadmap |
| **[challenge_acceptance.md](./challenge_acceptance.md)** | ADR-002 done definition |
| [docs/adr/ADR-001-challenge-first-product-axis.md](./docs/adr/ADR-001-challenge-first-product-axis.md) | Challenge > learning |
| [docs/adr/ADR-002-ideal-challenge-system.md](./docs/adr/ADR-002-ideal-challenge-system.md) | Ideal challenge system |
| [BOUNDARY.md](./BOUNDARY.md) · [data_contract.md](./data_contract.md) | Repo split + SQLite surfaces |
| [chapters.md](./chapters.md) · [ux.md](./ux.md) | Curriculum design (secondary) |
| [problem_backlog.md](./problem_backlog.md) | Small backlog of possible factors/labs |

Historical curriculum phase checklists (MVP / v1.1 / phase-2): local **`archive/`** (gitignored), not product gates.

---

## North star (one screen)

```text
doctor / vet
  → challenge list                         # catalog entry point
  → challenge health --with-diagnostics    # weekly tower
  → challenge engine signal|risk …         # dig only when retuning
  → English artifacts + human decision memos
  → never auto-promote · diagnostics never set Action
```

**Operator ritual SSOT:** [docs/challenge_product.md](./docs/challenge_product.md) (§ Operator ritual).

Learning: `ml-saham learn list|explore|demo|compare`.

| Purpose | Question | Status |
|---------|----------|--------|
| **Tune** | Factor worth? Weights / combo sensible? | **Shipped** (accum sleeves + signal raw_score) |
| **Champion** | Better score rule than production (same protocol)? | **Shipped** (accum default) |
| **Gate** | Hard-block open-book quality vs gate_off? | **Shipped thin** (`risk.accum.hard_gates`) |
| **Eligibility** | Screen hard-filter counterfactual? | **Replay shipped; tournament `BLOCKED_POLICY`** |
| **Diagnostic** | Display / promote-candidate bags (never Action) | **Shipped** (v1, 4 bags) |

Roadmap status: **not full ENTER coverage**. G0 snapshot-bound corpus depth,
G1 hard-filter tournament, G2 configured group-breadth authority, G3 risk
decision-quality metrics, and G4 readiness/Action remain open.
Details: **[docs/challenge_product_roadmap.md](./docs/challenge_product_roadmap.md)**.

Not investment advice. Artifacts never write ai-saham YAML/code.
