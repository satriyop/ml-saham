# Operator note: `signal.accum.raw_score`

Thin P2 signal policy. English only. **Not** Action ENTER accuracy.

## Question

Does production **SignalEngine score** on accum observations still beat clean feature reweights on **rank IC vs excess return vs IHSG**, primary **H=10**?

Live captures store score under **`features_by_window.<window>.signal`** (`assessment.score` / `raw_exact_score`), not top-level `signal.raw_score`.

Regression: `tests/fixtures/golden/signal_adr056_window.json` + `tests/test_challenge_payload_contracts.py`.

## Commands

```bash
ml-saham challenge list
ml-saham challenge run signal.accum.raw_score --against equal_sleeves
ml-saham challenge run signal.accum.raw_score --against ridge_reweight
ml-saham challenge engine signal --scenario accum
```

## Baseline

`src/ml_saham/challenge/policies/signal_accum_raw_score.v1.json`  
`score_kind=raw_score_primary` · panel extracts window `signal` score + group contribution features (`panel_signal.py`).

## Protocol

Same as accum path: `accum_path_v1` (H=10 primary; report 3/10/20).

## Related signal policies (P2 deepen)

| policy_id | Against | Note |
|-----------|---------|------|
| `signal.accum.flags` | `flags_off` | raw − flag penalties (10/8/12) |
| `signal.accum.classification` | `threshold_shift` | 70/45 band scores vs +5 floors |
| `signal.accum.evidence_group_weights` | `equal_sleeves` / `drop_setup` / `drop_flow` | production setup **0.60** / flow **0.40** |

```bash
ml-saham challenge run signal.accum.flags --against flags_off
ml-saham challenge run signal.accum.classification --against threshold_shift
ml-saham challenge run signal.accum.evidence_group_weights --against equal_sleeves
ml-saham challenge run signal.accum.evidence_group_weights --against drop_setup
ml-saham challenge engine signal --scenario accum
```

Operator note: [challenge_signal_evidence_group_weights.md](./challenge_signal_evidence_group_weights.md)

## Not this policy

- Sleeve AccumScore weights → `screener.accum.score_weights`
- Risk hard blocks → `risk.accum.hard_gates`
- Display diagnostics → `challenge diagnostic`
