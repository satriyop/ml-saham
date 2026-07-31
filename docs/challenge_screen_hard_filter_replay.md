# Challenge extract — accumulation screen hard-filter replay

**Status:** audit / extract-contract (not a shipped tournament)  
**Sibling task:** `ai-saham/tasks/backlog/parked_screen_filter_replay_contract.md`  
**Module:** `ml_saham.challenge.panel_screen_filters`

## Authority

| Role | Owner |
|------|--------|
| Live filter predicates & first-match order | **ai-saham** source |
| Capture / SQLite corpus | **ai-saham** |
| Read-only extract + pure classifier + this report | **ml-saham** |
| Tournament metrics / WIN·LOSE | **ml-saham** (blocked until decision checkpoint) |

Replay interpretation **C** (counterfactual non-zero policies on capture-neutralized ADR-056 rows), grounded in **A** (live ai-saham predicates). Matching capture’s all-pass outcome (**B**) is **not** the research objective.

## Four gates (first-match order)

| Order | Gate ID | ai-saham authority | ADR-056 path (window **7** only) | Enabled when | Reject when | Result |
|---:|---|---|---|---|---|---|
| 1 | `screen.accum.market_cap_floor` | `AccumulationCandidateStructuralFilter.apply` | `features_by_window.7.candidate.fundamentals.market_cap_idr` | floor `> 0` | fundamentals absent / value missing / value **&lt;** floor | `rejected_flow` |
| 2 | `screen.accum.piotroski_floor` | same | `…fundamentals.piotroski_f_score` | floor `> 0` | missing / **&lt;** floor | `rejected_flow` |
| 3 | `screen.accum.accum_score_floor` | `AccumulationCandidateSignalAssessor.assess` | `…candidate.accum_score` | `min_accum_score_enabled` | value **&lt;** floor | `rejected_flow` |
| 4 | `screen.accum.signal_score_floor` | same | `…signal.assessment.score` | `min_signal_score_enabled` | assessment absent / value **&lt;** floor | `rejected_signal` |

Verified against ai-saham (2026-07-31):

- Structural: `market_cap_idr < min` and `fscore < min` (equality **passes**).
- Signal assessor: accum then signal, first-match-wins.
- Not a gate: `min_net_buy_days` (broker-summary observability before candidate creation).

Classification outputs: `pass | rejected_flow | rejected_signal | unextractable_contract`.

## Missing-state truth table

| Situation | Extract state | Classify (when gate enabled) |
|-----------|---------------|--------------------------------|
| Recognized path, numeric value | `numeric` | compare to floor (`<` rejects) |
| Recognized path, JSON `null` or omitted fund key | `explicit_missing` | reject (structural / signal missing) |
| Missing `features_by_window` / window `7` / `candidate` | `unextractable_contract` | not treated as ordinary reject |
| Root/legacy fields only (no window pack) | `unextractable_contract` | forbidden fallback |

Windows **30** and **90** must not multiply N; only window **7** is the hard-filter sample unit.

## Cohort contract

```text
purpose              = ACCUMULATION_DISCOVERY
unit                 = unique (ticker, session_date)
canonical feature    = features_by_window["7"]
compatibility_id     = explicit caller-selected (required)
```

Initial measured cohort (reproducibility only; not a permanent default):

```text
compatibility_id = sha256:005363021f7f792071e43d12506aeefe474abf4fbd7d0a45f823b417e95e84c1
observations     = 1,890
sessions         = 42
tickers          = 45
```

Mixed cohorts without an explicit ID fail closed for this audit API.

## Denominator populations

1. **PIT membership** — not fully reconstructable from observation rows alone.  
2. **Capture-evaluated** — ADR-056 ticker/session rows in the selected cohort (replay denominator).  
3. **Corpus H10-label available** — capture-evaluated rows with AVAILABLE
   `price_path.accum_10d.v1` labels. This is **not** the future `accum_path_v1`
   tournament outcome (excess vs IHSG); naming it “metric-evaluable” would overclaim.

Do **not** claim full-universe recall.

## How to run

```bash
# Contract CI (no maintainer DB)
./scripts/check_challenge_contracts.sh

# Pure / offline tests
PYTHONPATH=src:. pytest tests/test_challenge_screen_filter_replay.py \
  tests/test_challenge_payload_contracts.py -q

# Live smoke (optional)
export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db
pytest tests/test_challenge_live_smoke.py -q -m live_db
```

Python API:

```python
from ml_saham.challenge.panel_screen_filters import (
    ScreenFilterPolicy,
    audit_screen_filter_cohort,
    classify_screen_filters,
    extract_screen_filter_inputs,
    sufficiency_verdict,
)

policy = ScreenFilterPolicy(
    min_market_cap_idr=1e12,
    min_piotroski=3,
    min_accum_score=50,
    min_accum_score_enabled=True,
    min_signal_score=40,
    min_signal_score_enabled=True,
)
summary = audit_screen_filter_cohort(
    db_path,
    compatibility_id="sha256:…",
    policy=policy,
)
print(sufficiency_verdict(summary), summary.extracted_count, summary.h10_available_count)
```

## Initial live audit snapshot (2026-07-31)

Maintainer DB cohort `sha256:005363021f7f792071e43d12506aeefe474abf4fbd7d0a45f823b417e95e84c1`:

| Metric | Value |
|--------|------:|
| selected_row_count | 1,890 |
| unique ticker/session | 1,890 |
| extracted_count | 1,890 |
| unextractable_count | 0 |
| Corpus H10-label AVAILABLE / UNAVAILABLE (selected units only) | 1,485 / 405 |
| market_cap numeric / explicit_missing | 765 / 1,125 |
| piotroski numeric / explicit_missing | 765 / 1,125 |
| accum_score / signal_score numeric | 1,890 / 1,890 |
| **Verdict** | **`SUFFICIENT_FOR_REPLAY`** |

Counterfactual smoke (non-tournament): floors market_cap 1e12, piotroski 3, accum 50 on, signal 40 on → class counts e.g. pass 82 / rejected_flow 1778 / rejected_signal 30 (illustrative only; not a WIN/LOSE claim).

## Sufficiency verdict rules

See task §9 / `sufficiency_verdict()`:

- **SUFFICIENT_FOR_REPLAY** when every selected unique unit extracts cleanly
  (unextractable count must be **exactly zero**), classifications reconcile 1:1,
  and when measured, corpus H10-label available + unavailable == selected.
- **INSUFFICIENT_NEEDS_CORPUS_EXTENSION** when required paths cannot be
  distinguished from schema failure, extract collapses, or H10 counts fail
  reconciliation against the **selected** observation_id set.
- Requested H10 measurement that cannot be performed because the label table or
  required columns are unavailable fails closed. Explicit `measure_h10=False`
  is the only supported way to skip that measurement.

Numeric null coverage (e.g. missing market_cap) is **not** automatically insufficient.

## Tournament checkpoint (not authorized here)

Still product-**SKIPPED** until exact floors/grid, binary winner definition, folds, and verified production policy snapshots are approved. Completing this audit does **not** unskip the tournament.

## Storage

- DB access: `ml_saham.data.aisaham_read.connect` (`mode=ro`)
- Zero writes to ai-saham production tables
- No per-threshold observation rows
