# Operator note: Challenge **champion** track

English only. **Shipped** for accum (M1+). Distinct from **tune** (factor / weight audit).

## Purpose

> Is there a **better scoring rule** than **production** under the same protocol — even if it is a learned black box?

| | **Tune** (shipped) | **Champion** (this track) |
|--|--------------------|---------------------------|
| Care about sleeves/weights? | **Yes** | **No** (internals optional) |
| Baseline | production | production |
| Typical against | equal_sleeves, ridge_reweight | **lgbm_reweight**, elastic_net_reweight |
| If WIN | retune weights / demote factor | human may **replace scorer** |
| Auto-promote | **Never** | **Never** |

Product map: [challenge_product.md](./challenge_product.md).

## Commands

```bash
# Preferred entry (champion banner + defaults)
ml-saham challenge champion screener.accum.score_weights
ml-saham challenge champion screener.accum.score_weights --model lgbm_reweight
ml-saham challenge champion screener.accum.score_weights --model elastic_net_reweight

# Same scorer via generic run
ml-saham challenge run screener.accum.score_weights --against lgbm_reweight

# Engine portfolio opt-in (M3)
ml-saham challenge engine screener --against lgbm_reweight
```

Requires `pip install -e ".[ml]"` (lightgbm + sklearn). Missing deps → **BLOCKED_POLICY** with install hint.

## Discipline

- Fit **only on fold train**; score **test** only (no full-panel fit for OOS IC).
- Min train rows (finite labels): max(25, n_features+5); else **BLOCKED_DATA**.
- Constant train labels → **BLOCKED_DATA**.
- Features: production **enabled sleeves** for accum (`weighted_sleeves`); for rank/raw policies, `feature_keys()`.

## Promote checklist (human only)

- [ ] Status is WIN (or strong multi-fold edge) under `accum_path_v1`
- [ ] Fold IC table reviewed; not one lucky fold
- [ ] Costs / gross disclaimer understood
- [ ] Memo written under `docs/decisions/` if considering ai-saham change
- [ ] **Do not** auto-write ai-saham YAML

## Not this track

- Factor KEEP/DEMOTE → `challenge factor`
- Equal/ridge weight audit → `challenge run --against equal_sleeves`
- Curriculum Default LightGBM demos → non-authority
