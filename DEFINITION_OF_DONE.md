# Definition of Done

This is the minimum quality bar for `ml-saham`. A task is not complete merely
because its happy-path command runs.

The DoD applies to the active task and all behavior it changes. Pre-existing
transition debt does not authorize new violations, but unrelated work need not
repair the entire repository. If touched behavior depends on that debt, the
task must resolve it or explicitly remain incomplete/blocked.

## 1. Contract Correctness

A change is done only when:

- it implements the exact accepted task and no hidden expansion;
- inputs, outputs, statuses, identities, and failure behavior are explicit;
- unsupported or inconsistent states fail closed;
- edge cases and negative cases are tested;
- current documentation describes the shipped behavior truthfully.

For challenge work, `BLOCKED_DATA`, `BLOCKED_POLICY`, and `INCONCLUSIVE` are
valid correct outcomes. Fabricated success is not.

## 2. Repository Boundary

- `ai-saham` remains the sole owner/writer of production config, market ingest,
  observations, corpus labels, and shared SQLite migrations.
- Upstream SQLite is opened and exercised read-only.
- No `ai-saham` Python import, scraper, provider client, or credential handling
  is added.
- ml-saham writes only its own artifacts, exports, progress, or explicitly
  ml-saham-owned learning store.
- No result automatically changes production behavior.

Any task violating these rules requires an accepted boundary/ADR change before
implementation.

## 3. Reproducibility

The same data, cohort, policy snapshot, adapter, Protocol, code/dependency
versions, configuration, and seed produce the same panel, metrics, and verdict.

Done requires:

- deterministic serialization and stable artifact identity where persisted;
- explicit random seeds for stochastic algorithms;
- recorded data range, population, exclusions, and relevant versions;
- no hidden current-time, network, global-state, or mutable-default dependency;
- no silent degraded-model fallback.

## 4. Point-In-Time And Leakage Safety

- Features are available by the decision cutoff.
- Ordered/purged walk-forward folds are used for time-dependent targets.
- Preprocessing, feature selection, calibration, and fitting occur inside the
  training fold only.
- Embargo and minimum sample rules follow the versioned Protocol.
- OOS results are not reused to choose the policy, grid, feature set, primary
  metric, or success rule and then reported as confirmatory.
- Target and benchmark share a horizon and unit.
- Missing, unavailable, unsupported, and negative remain distinct.

A leakage finding is a correctness failure, not a caveat to append after a
`WIN`.

## 5. Cohort, Policy, Protocol, And Adapter Identity

- One compatibility cohort per panel/verdict; no pooling.
- Production-facing runs select the cohort explicitly.
- `baseline=production` has a verifiable, cohort-bound upstream snapshot and a
  supported local adapter; no static fallback.
- Policy snapshot, challenge adapter, Protocol, challenger, population, and
  artifact identities remain separate and are carried into result/artifact
  surfaces.
- Historical/legacy artifacts remain historical and cannot acquire current
  eligibility through default values or translation.

## 6. Statistical And Verdict Integrity

- Metric choice matches decision type; IC is not a universal metric.
- Fold-wise evidence, valid-fold count, sample count, missingness, and stability
  are reported.
- A `WIN` satisfies the Protocol's minimum folds, margin, agreement, tail, and
  other gates. Current challenge law requires at least two valid OOS folds.
- Search breadth/multiplicity is recorded and governed.
- Factor DROP/DEMOTE decisions use ablation/stability evidence, not only
  univariate association.
- A thin or unsupported run remains blocked/inconclusive.

## 7. Architecture And Module Ownership

- `data/` owns read-only upstream access and cohort extraction.
- `challenge/` owns product policies, protocols, panels, challengers,
  orchestration, and verdict contracts.
- `eval/` contains reusable calculations without hidden product defaults.
- `artifacts/` writes only ml-saham-owned outputs.
- `cli/` parses, wires, invokes, renders, and maps errors; it does not invent
  feature math, protocol policy, or verdicts.
- `chapters/` remains pedagogical and cannot define challenge authority.
- Application behavior is testable without invoking the CLI.

## 8. Data And Persistence

- Schema, field paths, units, sample grain, PIT semantics, and missing behavior
  are explicit and versioned when material.
- Reads go through the canonical data/cohort helpers.
- Writes are scoped, atomic where needed, and idempotent or immutable by
  contract.
- Upstream read-only tripwires prove no file/page/count mutation for relevant
  data work.
- Artifact writes do not partially publish a successful result on failure.
- Market/provider data is not committed or redistributed.

## 9. Extract And Fixture Quality

Every new/changed product extractor has:

- a live-shaped redacted golden;
- a test calling shipped extraction code;
- explicit primary/legacy paths, units, PIT, horizon, sample unit, and missing
  behavior;
- adversarial wrong-path/malformed/missing fixtures;
- an updated `data_contract.md` row when the contract changes;
- a passing `./scripts/check_challenge_contracts.sh`.

Synthetic fixtures prove determinism and edge cases. Optional live smoke checks
representativeness; neither substitutes for the other.

## 10. Tests And Current Gates

Done requires the verification matrix in `AGENT_QUICKSTART.md`.

For Python changes, always run:

```bash
python -m compileall -q src tests
git diff --check
```

Run focused tests, affected CI commands, and the challenge-contract script when
applicable. Broad/shared changes require full `pytest -q`. Live-data claims
require the marked live smoke when the maintainer DB is available, with an
upstream mutation tripwire.

The repository does not yet have an accepted green Ruff baseline. Do not claim
one. Once the dedicated Ruff foundation change lands and updates this file,
whole-repo Ruff check and format become mandatory.

## 11. Documentation And Product Language

- Challenge-facing reports, statuses, metrics, and artifacts are English.
- Learning narrative may be Indonesian; identifiers remain English.
- New/changed commands, config, artifact fields, and limitations are documented.
- Examples use current commands and do not imply automatic promotion.
- Stale adjacent comments/docs encountered in the touched scope are corrected
  or softened after verification.

## 12. Shared Worktree And Delivery

- `git status --short` was inspected before editing and committing.
- Unrelated changes were preserved.
- No destructive cleanup or broad formatting was used.
- Only task-owned files are staged/committed.
- The final report names changed files, exact commands/results, limitations,
  and commit ID when committed.

## Final Gate

The task is done only if the implementer can answer all three:

1. What exact policy question or learning outcome does this change serve?
2. Why is the result point-in-time, reproducible, and free of silent fallback?
3. How is it prevented from writing or automatically influencing production?
