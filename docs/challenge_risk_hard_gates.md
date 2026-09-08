# Operator note: `risk.accum.hard_gates`

Thin P3 **gate** policy. English only.

## Question

Does production hard-block improve the H10 decision book versus `gate_off`
without hiding costly false blocks or harmful allows?

## Commands

```bash
ml-saham challenge run risk.accum.hard_gates --against gate_off
# per-gate ablation (P3 deepen)
ml-saham challenge run risk.accum.hard_gates --against gate_off:bandar_gate
ml-saham challenge run risk.accum.hard_gates --against gate_off:liquidity_gate
ml-saham challenge engine risk --scenario accum
```

`ridge_reweight` / `equal_sleeves` remap to `gate_off` with a note (UX: no sleeve-IC theater).

Enabled gates: bandar, liquidity, fundamental, free_float, technical (when present on observations).

## Metric (not sleeve KEEP/DEMOTE)

| Field | Meaning |
|-------|---------|
| Primary | Mean excess among rows **allowed** (not blocked) |
| block_rate | Share blocked under production vs gate_off (0) |
| WIN/LOSE | Same fold/margin rules as other challenges, higher primary better |

The sealed result also carries descriptive `gate_decision_quality.v1` metrics
for H3/H10/H20 and every primary fold:

| Field | Denominator / meaning |
|---|---|
| allowed / blocked books | Labeled rows on each decision side; count, mean, median excess |
| false-block rate | Blocked rows with excess > 0, divided by labeled blocked rows |
| harmful-allow rate | Allowed rows with excess <= 0, divided by labeled allowed rows |
| opportunity cost | Mean excess of the blocked book, with its denominator |
| first blocker | First blocked enabled audit row in `gate_evaluations` order |
| overlap attribution | Every enabled gate firing on a blocked row; totals may overlap |

Missing horizon outcomes are excluded, never converted to zero. A side with no
labeled rows reports a `null` rate rather than a false 0%. These metrics are
measurement-only: the current verdict still uses the existing allowed-book
primary law. A new material-improvement/safety law and named-gate multiplicity
rule must be predeclared and vetted before these fields may affect WIN/LOSE.

## Baseline

`src/ml_saham/challenge/policies/risk_accum_hard_gates.adapter.v2.json`
(`supported_snapshot_contract=production_policy_snapshot.v4`)
`score_kind=gate_block` · panel from observation
`features_by_window.7.risk.gate_evaluations` (schema 15).

A snapshot `contract_id` other than `production_policy_snapshot.v4` stays
`BLOCKED_POLICY` and names that adapter file plus one reviewed closed-set bump
of `supported_snapshot_contract` together with `SNAPSHOT_CONTRACT`. Do not copy
ai-saham configs or auto-promote a champion.

| Outcome | Component |
|---------|-----------|
| `triggered` | 1.0 (genuine gate fire) |
| `blocked_on_missing` | 1.0 (gate's own missing-data policy blocked) |
| `pass` / `skipped` / `not_evaluated` | 0.0 |

`skipped` is critical: an aggregate `unevaluable_policy=block` may still put a
gate name in coarse `gate_triggered` / `blocking_gates`, but the audit row stays
`skipped`/`triggered=false` and must **not** count as a genuine hard-gate fire.

Missing or malformed `risk.gate_evaluations` → row unextractable (no first-enabled-gate fallback).

## Never

- Present this as Accum sleeve factor KEEP/DEMOTE
- Auto-promote gate thresholds into ai-saham
- Claim full Action ENTER desk accuracy (P4 deferred)
- Attribute per-gate blocks from `trade_setup.blocking_gates` alone on current schema
