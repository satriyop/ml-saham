# Operator note: `signal.accum.raw_score`

Thin P2 signal policy. English only. **Not** Action ENTER accuracy.

## Question

Does production **signal.raw_score** (on accum observations) still beat clean feature reweights on **rank IC vs excess return vs IHSG**, primary **H=10**?

## Commands

```bash
ml-saham challenge list
ml-saham challenge run signal.accum.raw_score --against equal_sleeves
ml-saham challenge run signal.accum.raw_score --against ridge_reweight
ml-saham challenge engine signal --scenario accum
```

## Baseline

`src/ml_saham/challenge/policies/signal_accum_raw_score.v1.json`  
`score_kind=raw_score_primary` · panel extracts `signal.raw_score` + group contribution features.

## Protocol

Same as accum path: `accum_path_v1` (H=10 primary; report 3/10/20).

## Not this policy

- Sleeve AccumScore weights → `screener.accum.score_weights`
- Risk hard blocks → `risk.accum.hard_gates`
- Display diagnostics → `challenge diagnostic`
