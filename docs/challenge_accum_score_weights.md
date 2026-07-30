# Operator note: `screener.accum.score_weights`

ADR-002 first production challenge. English only.

## Question

Does **production AccumScorePolicy** component weights still beat clean challengers on **rank IC of score vs excess return vs IHSG**, primary horizon **H=10** sessions (also report 3 and 20)?

## Commands

```bash
ml-saham doctor --deep
ml-saham vet
ml-saham challenge list
ml-saham challenge run screener.accum.score_weights --against equal_sleeves
ml-saham challenge run screener.accum.score_weights --against ridge_reweight
```

## Baseline

Frozen snapshot: `src/ml_saham/challenge/policies/accum_score_weights.v1.json`  
Mirrored from ai-saham `ScoreAccumUseCase.AccumScorePolicy` defaults, with **P0 honesty**:

| Sleeve | Enabled | Notes |
|--------|---------|--------|
| consistency, streak, vwap_discount, rsi_headroom, foreign_flow_ratio | yes | Original weighted book |
| **bci** (`inst`) | **yes (P0 polish)** | Production `BciEvidencePolicy` cluster=**12.5** / stable=4.2; sleeve weight = **12.5** |
| **sector_breadth** | **yes (P0)** | Soft +**10** when peer breadth high (extractable) |
| bb_squeeze | **no** | Production `BollingerSqueezePolicy.enabled=False` |

`max_score` mirror: **100** (production AccumScorePolicy). Hash bumped on P0 polish.

## Protocol `accum_path_v1`

| Item | Value |
|------|--------|
| Primary horizon | 10 sessions |
| Report horizons | 3, 10, 20 |
| Label | excess close-to-close vs IHSG (session index) |
| Split | time-ordered purged folds |
| Outcomes | WIN / LOSE / INCONCLUSIVE / BLOCKED_DATA / BLOCKED_POLICY |

## Decision memos

| Date | Memo |
|------|------|
| 2026-07-29 | [Path A real-DB decision](./decisions/accum_score_weights_2026-07-29.md) — KEEP production; no promote |

## Never

- Auto-promote weights into ai-saham  
- Treat curriculum `learn compare accum-policy` as product authority (synthetic demo)

## Artifacts

`artifacts/challenge/screener.accum.score_weights/<timestamp>/`

- `manifest.json`, `metrics.json`, `weights.json`, `summary.md`
