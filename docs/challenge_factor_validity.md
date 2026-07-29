# Operator note: factor validity (`challenge factor`)

ADR-002 factor track. English only. Does **not** edit ai-saham config.

## Question

Does this **enabled** AccumScore sleeve still earn its place under `accum_path_v1` (primary **H=10**)?

## Commands

```bash
ml-saham challenge factor screener.accum.score_weights --list-factors
ml-saham challenge factor screener.accum.score_weights --factor consistency
ml-saham challenge factor screener.accum.score_weights --factor cons   # alias
ml-saham challenge factor screener.accum.score_weights --factor streak
```

## Methods (v1)

1. **Univariate:** rank IC of factor values vs excess return vs IHSG  
2. **Drop ablation:** production score with factor zeroed; `ΔIC = IC_full − IC_drop`  
   (positive Δ ⇒ removing the factor hurts ⇒ supports KEEP)

No permutation / residual / collinearity matrix in v1.

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `KEEP` | Ablation shows material, stable help |
| `DEMOTE` | Weak/unstable or likely redundant |
| `DROP_CANDIDATE` | Little marginal value + weak univariate — human may remove |
| `INCONCLUSIVE` | Conflicting folds / signals |
| `BLOCKED_*` | Data or policy/factor not eligible |

## Protocol

Same as policy tournament: `accum_path_v1`, horizons 3/10/20, primary 10.

## Artifacts

`artifacts/challenge/factor/<policy_id>/<factor>/<timestamp>/`
