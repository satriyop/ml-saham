# VERDICT_SEMANTICS — symmetric directional folds (2026-08-09)

## Contract id

`verdict_semantics.symmetric_directional.v1`

Sealed into promote-evidence `content_digest` as `verdict_semantics_contract_id`.

## Change

| Direction | Before | After |
|---|---|---|
| Positive edge, folds &lt; min | INCONCLUSIVE (provisional WIN language) | INCONCLUSIVE: **insufficient case to replace production** |
| Negative edge, folds &lt; min | **LOSE** | INCONCLUSIVE: insufficient case (not statistical LOSE) |
| WIN | multi-fold + fold agree | unchanged bar, renamed field |
| LOSE | any baseline mean edge after thin pass | multi-fold + fold agree for baseline wins |

Protocol field: `min_folds_for_verdict` (replaces `min_folds_for_win`).

## Why

A single post-embargo fold must not be asymmetric: allowing LOSE while blocking WIN
biases toward production under thin calendars while still claiming a statistical
defeat of the challenger. Conservative production bias is expressed as
insufficient case language, not LOSE.

## Historical

Pre-contract sealed artifacts lack `verdict_semantics_contract_id` in the digest
material and fail closed on reopen (display-only / not promote-reopen eligible).

## Unchanged

- Geometry / embargo / session minima
- `evidence_grade=EXPLORATORY` authority separation
- No policy-grade sample floors invented
