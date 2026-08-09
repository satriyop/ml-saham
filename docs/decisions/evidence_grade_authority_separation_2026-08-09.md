# Evidence-grade authority separation (2026-08-09)

## Problem

After ML-OOS-01/v5, folds can be geometry-valid and sealable. After geometry
simulation, Protocol carried session minima derived only from first possible
folds (e.g. accum 1 train / 7 test sessions). Those values are structural
geometry minima, not policy-grade sample floors — but promote reopen could
still treat verified production-identity + WIN as a policy handoff packet.

## Fix (no statistical guessing)

| Field | Current `accum_path_v1` | Role |
|---|---|---|
| `evidence_grade` | `EXPLORATORY` | Authority class of the result |
| `policy_confirmation_contract_id` | `""` (none) | Must be registered for `POLICY_GRADE` |
| `geometry_min_*_sessions` | 1 / 7 | Structural fold acceptance only |

Promote / reopen path: `validate_policy_grade_eligibility` fails closed on
`EXPLORATORY` or unknown confirmation contract. Registry
`POLICY_CONFIRMATION_CONTRACTS` is empty until ML-OOS-02 confirmation design.

Challenge execution remains runnable. Artifacts still seal for audit.

## Not a protocol fork

Still `accum_path_v1`. No `accum_path_v2`. Authority is grade + confirmation
contract, not a silent reinterpretation of geometry minima as sample floors.
