# ML-OOS-02 — DGP, effect, and acceptance target vet (2026-08-10)

**Status: BLOCKED TARGET CONTRACT / FOLLOW-UP REQUIRES VETTING**

Executable audit:

```bash
PYTHONPATH=src python scripts/report_ml_oos_02_target_vet.py
PYTHONPATH=src python scripts/report_ml_oos_02_target_vet.py --json
```

Audit identity: `policy_confirmation_target_contract_vet.v1`. The audit is
`MEASUREMENT_ONLY`; it does not inspect live outcomes, choose a session floor,
register `POLICY_CONFIRMATION_CONTRACTS`, or authorize Task 06.

## Objective conclusion

The current synthetic harness is suitable for screening interval machinery but
is not yet a simulation of the shipped proposal lifecycle. More interval
methods should not be added until the target contract is defined.

The executable audit returns `BLOCKED_TARGET_CONTRACT` for six blockers and one
warning:

| ID | Finding | Proposed follow-up requiring vetting |
|---|---|---|
| `DGP-01` | AR(1), noise, and sinusoidal heteroskedasticity values are candidate stress inputs with no accepted ACCUM-estimand basis. | Predeclare a conservative parameter envelope or estimate it on a design-only historical cohort that can never become confirmation evidence. |
| `DGP-02` | Cross-sectional width only changes a binomial valid-name count and variance scale. Ticker-level scores, targets, ties, cross-name dependence, and session IC are absent. | Generate decision-specific ticker/session inputs and calculate the session metric through shipped metric code. |
| `ESTIMAND-01` | Calibration pools the union of all outer test sessions into one mean interval. The real runner averages fold ICs, requires directional fold agreement, and applies a tail gate. | Build a lifecycle simulator that produces fold metrics and invokes the same aggregation contract. |
| `ESTIMAND-02` | The real runner's fold IC itself pools all ticker/session rows, conflicting with the outcome-blind decision that sessions are the inferential unit. | Choose and version a session-native fold estimand; keep existing exploratory artifacts historical. |
| `EFFECT-01` | The sole eligible alternative is `0.05` synthetic units, unbound to costs, turnover, tail risk, or an improvement worth human review. | Define a decision-specific smallest effect of interest in the exact metric unit. |
| `LAW-01` | `minimum_folds` checks formed geometry, not valid-fold count, fold agreement, or tail behavior. | Calibrate lifecycle-level false decisions and power after its estimand is frozen. |
| `LAW-02` | The 90% observed-session tolerance is dormant: every current interval method rejects any calendar gap. | Choose a complete-calendar contract or vet an explicit missing-data method; do not adopt a dormant tolerance. |

## Why this changes the interpretation of prior screens

The percentile, automatic-block, and studentized screens remain valid as
measurements of interval behavior under their stated generic session-mean DGP.
They do not establish whether the complete proposal lifecycle has acceptable
false-promotion or detection behavior. Their `0/4` outcomes therefore reject
immediate method adoption but cannot by themselves select the production
sample floor or prove that the lifecycle acceptance law is ideal.

This distinction follows the ADEMP requirement that aims, data-generating
mechanisms, estimands, methods, and performance measures be aligned and
reported explicitly. Morris, White, and Crowther also require Monte Carlo
uncertainty to be reported
([paper](https://doi.org/10.1002/sim.8086)). The existing harness already reports
Monte Carlo uncertainty; the open defect is alignment of the DGP and estimand
with the product decision.

The effect target must be defined by practical relevance before power analysis.
A smallest effect of interest is a contextual boundary, ideally tied to theory
or cost-benefit relevance, rather than a number selected because a test can
detect it (Lakens,
[paper](https://doi.org/10.1177/1948550617697177)). Here that means using the
exact challenge metric and binding costs, turnover, and tail non-inferiority as
applicable to the named decision type.

## Recommended implementation order

1. Select one decision type, initially a fixed challenger under
   `screener.accum.score_weights`; do not attempt one universal IC contract.
2. Resolve the current pooled-row runner conflict and define the per-session
   estimand from ticker-level score/target pairs, including its
   missing/constant-rank behavior.
3. Define the smallest effect that would justify human review, plus separate
   tail-risk and turnover constraints.
4. Define a DGP envelope for ticker/session inputs without using the eventual
   confirmation outcomes for design and confirmation.
5. Simulate the exact fold construction, embargo, per-fold metrics, fold
   agreement, tail gate, and final holdout lifecycle.
6. Only then revise the numerical acceptance law and compare existing interval
   candidates.

The first measurement-only follow-up is implemented in
[`ml_oos_02_session_estimand_candidate_2026-08-10.md`](./ml_oos_02_session_estimand_candidate_2026-08-10.md).
It defines a paired per-session rank-IC delta for the fixed
`screener.accum.score_weights` / `equal_sleeves` question, while leaving every
minimum-name, effect, fold, and tail decision unadopted.

No number or methodology in this document is adopted. The confirmation
registry remains empty, `accum_path_v1` remains `EXPLORATORY`, and Task 06
remains blocked.
