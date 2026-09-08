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

`src/ml_saham/challenge/policies/risk_accum_hard_gates.adapter.v1.json`  
(`supported_snapshot_contract=production_policy_snapshot.v2`)  
`score_kind=gate_block` · panel from observation `trade_setup.blocking_gates`.

Semantic engine contract stays `risk.hard_gates.accum.v1` on both sides.
The live disagreement is the snapshot artifact contract, not a copied gate config.

## Snapshot contract (live mismatch — stay blocked)

ai-saham writes active accum cohorts as `production_policy_snapshot.v4`
(nine-row closed set). ml-saham still verifies the historical seven-row
`production_policy_snapshot.v2` set. That is a live policy disagreement, not
documentation drift. `challenge health` stays `BLOCKED_POLICY` and names the
exact file plus one reconcile step:

`risk.accum.hard_gates: contract_id='production_policy_snapshot.v4' does not match 'production_policy_snapshot.v2' (file src/ml_saham/challenge/policies/risk_accum_hard_gates.adapter.v1.json supported_snapshot_contract=production_policy_snapshot.v2; producer contract=production_policy_snapshot.v4). Reconcile: set supported_snapshot_contract in src/ml_saham/challenge/policies/risk_accum_hard_gates.adapter.v1.json and SNAPSHOT_CONTRACT in src/ml_saham/challenge/production_policy_snapshots.py from production_policy_snapshot.v2 to production_policy_snapshot.v4 only as one reviewed closed-set bump — live policy disagreement, not documentation drift; do not copy ai-saham configs or auto-promote a champion.`

Do not retarget the adapter or `SNAPSHOT_CONTRACT` in a docs-only change.
Do not copy ai-saham configs into ml-saham as a promotion.

## Never

- Present this as Accum sleeve factor KEEP/DEMOTE  
- Auto-promote gate thresholds into ai-saham  
- Claim full Action ENTER desk accuracy (P4 deferred)
