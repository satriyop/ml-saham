# AI Agent Preflight And Close Checklist

Use this checklist with `AGENT_QUICKSTART.md`. Select the relevant sections; do
not load unrelated documents merely to tick boxes.

## 1. Context

- [ ] I read `AGENT_QUICKSTART.md` and `AGENTS.md`.
- [ ] I selected task-specific sources from the reading matrix.
- [ ] For code, I read the DoD, relevant prompt contract, current code, and
      focused tests.
- [ ] I inspected `git status --short` and identified unrelated changes.
- [ ] I understand challenge-first, curriculum-second product priority.

## 2. Scope And Classification

- [ ] The requested behavior and non-goals are explicit.
- [ ] I classified all material changes using the quickstart taxonomy.
- [ ] Version bump/clean break is defined for material contract changes.
- [ ] I stated risks, stale-doc conflicts, assumptions, and the boundary plan.
- [ ] The task is sufficiently specified under `TASK_TEMPLATE.md`.

## 3. Sibling Boundary

- [ ] ai-saham-owned inputs and ml-saham-owned outputs are named.
- [ ] Upstream SQLite is opened read-only.
- [ ] No upstream migration/write/repair/vacuum/persistent pragma is added.
- [ ] No ai-saham Python import or copied unversioned business logic is added.
- [ ] No provider/scraper/auth/network ingest is added.
- [ ] No auto-write to production YAML/code/database is possible.
- [ ] Real-DB operations have a no-mutation tripwire when relevant.

## 4. Data And Cohort

- [ ] Purpose and explicit compatibility ID are defined.
- [ ] One cohort only; no silent pooling/substitution/largest-latest selection.
- [ ] Sample unit, dedupe key, population, denominator, and exclusions are
      explicit.
- [ ] Observation access uses `ml_saham.data.observation_cohort`.
- [ ] Required paths/columns, cardinality, units, and missing behavior are
      documented.
- [ ] Missing, unavailable, unsupported, malformed, empty, and zero remain
      distinct.
- [ ] Any source replacement is proven semantically equivalent or renamed.

## 5. Point-In-Time And Targets

- [ ] Economic date, available-at, capture time, cutoff, horizon, and label
      availability are not conflated.
- [ ] Every feature is knowable at/before cutoff.
- [ ] Target and benchmark use the same horizon/session definition.
- [ ] Units are explicit; no magnitude heuristic.
- [ ] Feature lookback windows do not multiply sample N incorrectly.
- [ ] Corpus labels and Protocol targets are not silently conflated.

## 6. Production Policy And Adapter

- [ ] `baseline=production` has a verified cohort-bound snapshot.
- [ ] Snapshot canonical bytes/digest/identity are validated, not trusted labels.
- [ ] Production snapshot and challenge adapter are separate typed concepts.
- [ ] Adapter supports the exact policy and semantic contract.
- [ ] Counterfactual reproduction has golden conformance coverage.
- [ ] Observed production output is preferred when recomputation is unnecessary.
- [ ] Missing/mismatch/unsupported returns `BLOCKED_POLICY` before panel work.
- [ ] No static/package fallback can rescue failed verification.

## 7. Protocol And Leakage

- [ ] Protocol ID/version is explicit.
- [ ] Universe, target, benchmark, horizons, primary metric, costs, folds,
      embargo, min N, and success law are frozen before evaluation.
- [ ] Splits are ordered/purged, never random rows for path labels.
- [ ] All preprocessing, selection, calibration, and model fit are train-only.
- [ ] OOS outcomes were not used to choose the evaluated hypothesis/grid.
- [ ] Search breadth/multiplicity handling is recorded.
- [ ] Stochastic algorithms have fixed recorded seeds.
- [ ] At least two valid OOS folds are required for current `WIN` semantics.

## 8. Panel And Extract Contract

- [ ] Live-shaped redacted golden added/updated.
- [ ] Test calls shipped extractor/classifier code.
- [ ] Primary and accepted legacy paths are explicit.
- [ ] Wrong/root-only/malformed paths do not produce false-clear zeros.
- [ ] PIT, unit, horizon, benchmark, grain, and missing behavior are asserted.
- [ ] `data_contract.md` extract row is current.
- [ ] `./scripts/check_challenge_contracts.sh` passes.

## 9. Metrics And Verdicts

- [ ] Metric matches decision type.
- [ ] Fold-wise N/metric/stability evidence is present.
- [ ] `WIN` satisfies every Protocol gate.
- [ ] Thin/single-fold/unstable evidence remains `INCONCLUSIVE` or blocked.
- [ ] Factor verdict uses ablation/marginal contribution and stability, not only
      univariate IC.
- [ ] Diagnostic promotion remains candidate-only and non-authoritative.
- [ ] CLI does not compute or reinterpret verdicts.

## 10. Model Discipline

- [ ] Optional dependency requirement is explicit and fails with an install hint.
- [ ] No silent fallback model under the same challenger ID.
- [ ] Parameters, feature contract, seed, and dependency versions are recorded.
- [ ] Fit/predict boundaries are tested per fold.
- [ ] Remote AI/LLM is absent from targets, metrics, verdicts, and promotion.

## 11. Artifacts And Writes

- [ ] Artifact schema/version and ID inputs are explicit.
- [ ] Cohort, snapshot, adapter, Protocol, baseline/challenger, range, counts,
      folds, code/dependency, and seed identities are carried as applicable.
- [ ] Writes target only ml-saham-owned paths/stores.
- [ ] Writes are atomic/immutable and failure cannot publish success.
- [ ] Reopening legacy artifacts preserves their historical eligibility.
- [ ] Promote packet is a human checklist, not an executable production patch.

## 12. Module And CLI Boundaries

- [ ] Data SQL/cohort logic lives in `data/`.
- [ ] Challenge policy/protocol/orchestration lives in `challenge/`.
- [ ] Reusable calculations in `eval/` do not hide product defaults.
- [ ] CLI only parses, wires, invokes, renders, exports, and maps named errors.
- [ ] Curriculum code does not define challenge authority.
- [ ] Challenge copy is English; learning narrative may be Indonesian.

## 13. Tests And Gates

- [ ] Focused happy and negative tests pass.
- [ ] Identity/provenance/cohort/PIT/leakage cases are tested.
- [ ] Affected commands from `.github/workflows/ci.yml` pass.
- [ ] Broad/shared changes ran full `pytest -q`.
- [ ] `python -m compileall -q src tests` passes for Python changes.
- [ ] `git diff --check` passes.
- [ ] Live smoke ran for maintainer-data claims when DB was available, with
      selected ID and mutation tripwire recorded.
- [ ] I did not claim Ruff passed; no accepted gate exists yet. If this is the
      Ruff foundation task, config/dependency/baseline/CI/governance all land
      together and whole-repo check+format pass.

## 14. Documentation And Delivery

- [ ] ADR/boundary/data/product/extract/artifact/operator docs are updated as
      required.
- [ ] Adjacent stale claims in touched scope are fixed or softened.
- [ ] Unrelated worktree changes remain untouched.
- [ ] Only task-owned files are staged/committed.
- [ ] Final report includes exact commands/results, limitations, files, and
      commit ID when committed.
- [ ] No acceptance item remains open while the task is called complete.

## Mandatory Preflight Statement

Before coding, an agent should be able to state:

> I am operating under the ml-saham agent harness. I will keep ai-saham access
> read-only, preserve explicit cohort/policy/protocol/adapter identities, enforce
> point-in-time and verdict gates, keep curriculum non-authoritative, prevent
> auto-promotion, and protect unrelated worktree changes.
