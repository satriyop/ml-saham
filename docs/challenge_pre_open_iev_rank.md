# Operator note: `screener.pre_open.iev_rank`

ADR-002 second production challenge (Path B). English only.

## Question

Does **production IEV official rank** beat clean feature-based challengers on **same-session open→close rank IC** (excess vs IHSG), protocol **`pre_open_session_v1`**?

Primary metric uses horizon sentinel **H=0** = same trading session open→close (not multi-day close).

## Commands

```bash
ml-saham doctor
ml-saham challenge list
ml-saham challenge run screener.pre_open.iev_rank --against equal_sleeves
ml-saham challenge run screener.pre_open.iev_rank --against ridge_reweight
```

## Baseline

Frozen snapshot: `src/ml_saham/challenge/policies/pre_open_iev_rank.v1.json`  
Production score = `official_rank_score` (higher is better rank within capture batch).  
Challenger features: `log_iev` (= log1p volume), raw `iev`, `iep` (within-date z equal / ridge).

**Not used:** `iev / iep - 1` — IEV is volume, IEP is price; that ratio is meaningless.

## Protocol `pre_open_session_v1`

| Item | Value |
|------|--------|
| Primary | same-session open→close (H=0 sentinel) |
| Label | open_to_close_excess_vs_ihsg |
| Data | `iev_snapshot_history` (preferred) or `iev_snapshots` + `candles` |
| Split | time-ordered folds, embargo 1 session |
| Outcomes | WIN / LOSE / INCONCLUSIVE / BLOCKED_DATA / BLOCKED_POLICY |

### Capture batch PIT (NCP decision window)

If history has multiple `collected_at` per date, pick **one** batch (do not mix tickers across times):

1. Prefer **`is_ncp_locked = 1`**
2. Else prefer capture clock in **[08:45, 09:00)** (pre-open / NCP)
3. Else largest batch (legacy fallback; note if post-open)

Tie-break: latest `collected_at`.

## Factor validity

**Not supported yet** for this policy (`panel_kind=iev_rank`).  
`challenge factor screener.pre_open.iev_rank …` returns `BLOCKED_POLICY`.

## Smoke note (maintainer DB, 2026-07-29)

- Panel ≈ **473** rows · **73** tickers · **21** dates (`iev_snapshot_history`, largest batch/day)  
- **3** time folds formed  
- Production same-session IC slightly negative on this sample; equal_sleeves did not beat it (`LOSE` for equal)  
- Ridge mean IC higher but **tail gate** / fold mix → not a promotion case  
- **Promotion:** NO  

## Sibling

Observation / raw_score track: [challenge_pre_open_directional_score.md](./challenge_pre_open_directional_score.md)

## Never

- Auto-promote rank/feature weights into ai-saham  
- Use multi-day H=10 close labels for this protocol  
- Treat curriculum `pre-open-*` demos as the product challenge  

## Related

- [ADR-002](./adr/ADR-002-ideal-challenge-system.md)  
- [engine_factor_map](./engine_factor_map.md)  
- Accum sibling: [challenge_accum_score_weights](./challenge_accum_score_weights.md)  
