# Operator note: `risk.accum.hard_gates`

Thin P3 **gate** policy. English only.

## Question

Does production hard-block (Bandar / Liquidity on `trade_setup`) improve the **open book** vs **gate_off** (never block), measured as **mean forward excess among allowed names** (primary H=10)?

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

## Baseline

`src/ml_saham/challenge/policies/risk_accum_hard_gates.adapter.v2.json`
`score_kind=gate_block` · panel from observation
`features_by_window.7.risk.gate_evaluations` (schema 15).

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
