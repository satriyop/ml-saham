# Operator note: `signal.accum.evidence_group_weights`

Production **evidence group weights** (not full Action desk). English only.

## Question

Does frozen **setup_quality 0.60 / flow_confirmation 0.40** (ai-saham `signal_engine.yaml` evidence_groups) still beat equal weights or drop-group ablations on **rank IC vs excess vs IHSG**, primary **H=10**?

## Commands

```bash
ml-saham challenge list
ml-saham challenge run signal.accum.evidence_group_weights --against equal_sleeves
ml-saham challenge run signal.accum.evidence_group_weights --against drop_setup
ml-saham challenge run signal.accum.evidence_group_weights --against drop_flow
ml-saham challenge engine signal --scenario accum
```

## Baseline

`src/ml_saham/challenge/policies/signal_accum_evidence_group_weights.v1.json`

| Group | Weight | Panel source |
|-------|--------|--------------|
| `setup_quality` | **0.60** | group_contributions |
| `flow_confirmation` | **0.40** | group_contributions (`institutional_flow` alias) |

Score = weight-mean of present group scores (renormalize if a group is missing).  
Sector / company_quality slots stay **disabled** (diagnostic registrations in production).

## Challengers

| Against | Meaning |
|---------|---------|
| `equal_sleeves` | Equal weight on enabled groups |
| `drop_setup` | Zero setup weight (flow-only, renormalized) |
| `drop_flow` | Zero flow weight (setup-only) |
| `ridge_reweight` | Ridge on group features → excess@H |

## Protocol

`accum_path_v1` (primary H=10).

## Never

- Treat WIN as “change DecisionPolicy ENTER” without a human memo  
- Confuse with AccumScore sleeves or diagnostic KEEP_DISPLAY  
