# Golden challenge payloads (live-shaped)

Static JSON shaped like **ai-saham** production captures. Used by
`tests/test_challenge_payload_contracts.py` so extract/verdict regressions
do **not** depend on a maintainer DB or only on `build_mvp_fixture`.

| File | Contract |
|------|----------|
| `accum_adr056_window.json` | ADR-056 `features_by_window` + `accum_score_breakdown` |
| `signal_adr056_window.json` | Nested `features_by_window.*.signal` (no top-level `signal`) |
| `open_30m_metrics.json` | `price_path.open_30m` metrics; `*_return_pct` = **percent points** |
| `iev_multi_capture_day.json` | Multi `collected_at` same date: early / NCP / post-open |

Tickers/dates are synthetic or redacted; structure and units match live.
