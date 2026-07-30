# Operator note: `challenge engine screener`

ADR-002 **engine portfolio** for the screener stack. English only.

## Question

How are **registered screener PolicySpecs** doing under a shared challenger, optionally filtered by **ai-saham scenario** (`accum` | `pre-open`)?

## Commands

```bash
ml-saham challenge engine list
ml-saham challenge engine screener
ml-saham challenge engine screener --scenario accum
ml-saham challenge engine screener --scenario pre-open
ml-saham challenge engine screener --against equal_sleeves --export-json /tmp/screener.json
```

Default `--against` is **`equal_sleeves`** (shared across the portfolio).  
**Champion opt-in:** `--against lgbm_reweight` or `elastic_net_reweight` runs the **champion** scorers on each policy (still production baseline; not the tune default).

## Vocabulary (ai-saham-aligned)

| Term | Meaning |
|------|---------|
| **Engine** | `screener` (later: signal, risk, …) |
| **Scenario** | `accum` \| `pre-open` (same word as research CLI / ADR-047) |
| **Policy** | One PolicySpec; dig with `challenge run <policy_id>` |

Not `--track`. Not curriculum `compare` (learning only).

## Registry (v1)

| Scenario | Policies |
|----------|----------|
| `accum` | `screener.accum.score_weights` |
| `pre-open` | `screener.pre_open.iev_rank`, `screener.pre_open.directional_score` |

Omit `--scenario` → all of the above.

## Rollup honesty

- Per-row status: WIN / LOSE / INCONCLUSIVE / BLOCKED_* / ERROR  
- **No single engine WIN/LOSE** in v1 — only counts + notes  
- Thin data (e.g. directional_score) may **BLOCKED_DATA** while other rows still report  
- Portfolio exit **0** if resolve OK (even with blocked rows); exit **2** only for unknown engine/scenario  

## Never

- Auto-promote into ai-saham  
- Average ICs across different protocols/horizons  
- Treat curriculum `compare` as engine portfolio authority  

## Related

- [ADR-002](./adr/ADR-002-ideal-challenge-system.md)  
- Policies: [accum](./challenge_accum_score_weights.md) · [IEV rank](./challenge_pre_open_iev_rank.md) · [directional](./challenge_pre_open_directional_score.md)  
