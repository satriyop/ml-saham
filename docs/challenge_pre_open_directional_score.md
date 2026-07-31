# Operator note: `screener.pre_open.directional_score`

ADR-002 pre-open **observation** policy (Path B2). English only.  
Sibling: [IEV rank](./challenge_pre_open_iev_rank.md) (dense table track).

## Question

Does production pre-open **directional `signal.raw_score`** beat feature-based challengers on **same-session open-path** labels (`pre_open_session_v1`)?

## Data-tolerant product

| Environment | Expected |
|-------------|----------|
| Fixture / dense PRE_OPEN captures | Full tournament WIN / LOSE / INCONCLUSIVE |
| Thin maintainer DB (few PRE_OPEN rows) | **`BLOCKED_DATA`** with clear notes — **not a bug** |

When ai-saham densifies `PRE_OPEN_AUCTION_DIRECTION` (+ optional `open_30m` outcomes), re-run the same command — no redesign.

## Commands

```bash
ml-saham challenge list
ml-saham challenge run screener.pre_open.directional_score --against equal_sleeves
ml-saham challenge run screener.pre_open.directional_score --against ridge_reweight
```

## Baseline

Frozen: `src/ml_saham/challenge/policies/pre_open_directional_score.v1.json`  
- **Production:** `signal.raw_score` (fallback `signal.score`)  
- **Features (challengers):** book_pressure, delta_iev_ratio, iep_gap_pct, iev_intensity, spread_pct, opening_broker_backing_score, fvwap_discount_pct  
- Source purpose: `PRE_OPEN_AUCTION_DIRECTION`  
- Labels (same-horizon only):
  - Prefer corpus `price_path.open_30m` → stock **open→09:30** (from `close_proxy_09_30` / `opening_price`, or `*_return_pct` as **percent points ÷ 100**). **Not** excess vs full-day IHSG (would mix horizons; daily candles lack IHSG 09:30).
  - Else candle **open→close − IHSG open→close** (both full session).  


## Protocol

Shared **`pre_open_session_v1`** with IEV rank (H=0 = same-session open path).

## Factor validity

**Not supported in v1** (cannot ablate sleeves inside opaque raw_score).  
`challenge factor screener.pre_open.directional_score …` → `BLOCKED_POLICY`.

## Never

- Auto-promote into ai-saham  
- Treat thin-DB BLOCKED as production failure  
- Use multi-day H=10 close as primary for this policy  

## Related

- [ADR-002](./adr/ADR-002-ideal-challenge-system.md)  
- [engine_factor_map](./engine_factor_map.md)  
- [pre-open IEV rank](./challenge_pre_open_iev_rank.md)  
