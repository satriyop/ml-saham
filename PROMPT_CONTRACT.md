# Prompt Contract

This contract binds AI coding agents working in `ml-saham`. It exists to prevent
data leakage, false production baselines, upstream writes, statistical
overclaiming, and product drift from challenge authority into curriculum demos.

## 1. Authority And Conflict Resolution

Repository-local sources are interpreted in this order:

1. `AGENTS.md` and `AGENT_QUICKSTART.md` define mandatory agent procedure.
2. Accepted ADRs and `BOUNDARY.md` define product/ownership intent.
3. Current executable code and tests define implemented behavior.
4. `DEFINITION_OF_DONE.md` defines the quality close gate.
5. `data_contract.md`, product/operator docs, and task contracts define scoped
   behavior.
6. Examples, roadmap text, archived output, and historical artifacts may lag.

Higher-level system/developer/user instructions still govern the agent. When
repo sources conflict, report the conflict and follow the newer accepted
contract or stop for clarification; do not silently pick the easiest source.

## 2. Mandatory Preflight

Before code changes, agents must:

- read `AGENT_QUICKSTART.md` and `AGENTS.md`;
- use the quickstart reading matrix;
- read `DEFINITION_OF_DONE.md` and relevant checklist sections;
- inspect the current implementation and focused tests;
- inspect `git status --short`;
- state semantic classifications, risks, assumptions, and the boundary plan;
- define required verification before editing.

For documentation-only work, read the edited documents and sources supporting
their code/data claims. Do not load unrelated governance documents by default.

## 3. Challenge-First Product Rule

- Challenge is the primary product. Curriculum is secondary onboarding.
- Extend `src/ml_saham/challenge/` for product policy/protocol/verdict work.
- Do not make a chapter registry, demo, or `learn compare` the challenge SSOT.
- Challenge outputs are English; learning narrative may be Indonesian.
- An ML model in a curriculum demo is not a production challenger until a
  versioned ChallengeSpec/Protocol/adapter and acceptance tests exist.

## 4. Upstream Read-Only Rule

Agents must not:

- write, migrate, repair, backfill, vacuum, attach writable databases to, or
  change persistent pragmas on ai-saham SQLite;
- import ai-saham packages or copy live business logic as an unversioned mirror;
- add provider/scraper/auth clients;
- write ai-saham YAML/code/config from a challenge result.

Use the existing read-only connection and centralized data/cohort helpers. If a
task requires an upstream change, create/handoff an ai-saham-owned task and stop
the ml-saham mutation.

Tests for upstream readers must use temporary fixtures and, when a real DB is
used, a before/after mutation tripwire.

## 5. Production Baseline Rule

`production` is a claim, not a convenient label.

Before allowing it, require:

- one explicit observation compatibility cohort;
- the production policy snapshot required by the active contract;
- canonical JSON/digest/identity validation;
- a separate versioned ml-saham challenge adapter supporting that policy's
  semantic contract;
- conformance coverage for counterfactual reproduction;
- no packaged/static fallback.

Observed production outputs should be preferred when recomputation is not
required. Missing or unverifiable identity is `BLOCKED_POLICY`, not
`BLOCKED_DATA`, and never an approximate run.

## 6. Protocol Immutability And Leakage Rule

Protocol owns universe/population, target, benchmark, horizons, costs, folds,
embargo, minimum N, metrics, and success law.

Agents must not:

- modify Protocol fields from CLI display logic;
- choose thresholds/grid/features after inspecting full OOS outcomes and report
  the same outcomes as unbiased;
- use random row splits for time-path labels;
- fit preprocessing/model/selection on the full panel;
- mix target and benchmark horizons or infer units from magnitude;
- silently reduce fold/min-N/win-margin requirements to get a verdict;
- convert a one-fold edge into `WIN`.

Material Protocol changes require a new version/clean break and updated artifact
identity. Use train-only fitting and ordered/purged walk-forward evaluation.

## 7. Cohort And Population Rule

- One panel/verdict uses one compatibility ID.
- Explicit selection is mandatory for production-facing runs and live audits.
- Do not pool cohorts, silently choose latest/largest, or substitute a cohort
  after lookup failure.
- Exploratory/curriculum default selection must disclose selected and excluded
  cohorts and cannot produce promotion-eligible output.
- Define sample grain and denominator before metrics.
- Feature windows are not independent observations unless Protocol says so.
- Candidate-only/broker-observable populations cannot support claims about
  unobserved full-universe recall.

## 8. Missingness And Exception Rule

Keep these distinct:

- numeric zero;
- explicit missing/null;
- unavailable at horizon/cutoff;
- unsupported contract/path;
- malformed/corrupt canonical payload;
- empty but valid population;
- repository/programmer failure.

Only expected data absence may become typed missing/unavailable. Contract,
schema, JSON, non-finite numeric, identity, and invariant errors must propagate
or become the exact fail-closed status at the named challenge boundary.

Broad `except Exception: return []/0/None` behavior is forbidden in product
extraction and policy verification.

## 9. Panel And Extractor Rule

New/changed challenge extractors require:

- a live-shaped redacted golden;
- shipped-helper tests;
- explicit path, unit, horizon, cutoff, grain, missing behavior, and legacy
  fallback contract;
- wrong-path/malformed negative cases;
- updated data contract;
- passing challenge-contract script.

Do not reimplement a parser in tests. Do not use curriculum math as a product
feature without re-deriving its field meaning and contract.

## 10. Verdict Rule

- Verdicts are computed in challenge code, never invented by CLI rendering.
- Status enums and factor/diagnostic outcomes must be exhaustive and tested.
- Blocking conditions short-circuit before misleading metrics/artifact success.
- `WIN` requires the active Protocol's complete gate, including valid folds and
  stability. Current minimum is two valid OOS folds.
- Factor removal requires marginal/ablation and stability evidence; univariate
  correlation alone is insufficient.
- Diagnostic `PROMOTE_CANDIDATE` opens a design task; it does not grant score or
  Action authority.

## 11. Model And AI Rule

ML is a legitimate optional challenge implementation, but its use is governed:

- learned models fit inside train folds only;
- dependency absence fails explicitly with install guidance when the named
  challenger requires it;
- deterministic seeds and model parameters are recorded;
- no silent simpler-model fallback under the same challenger ID;
- model artifacts and feature contracts are versioned;
- explainability output does not override statistical gates.

Remote LLM/AI output may help author prose but cannot generate targets,
features, metrics, verdicts, policy identities, or automatic promotion. Any
AI-assisted user-facing narrative must be optional and visibly non-authoritative.

## 12. CLI Thinness And Language Rule

CLI may parse, resolve paths/dependencies, invoke challenge/curriculum functions,
render typed results, export, and map named errors.

CLI must not:

- query upstream observations ad hoc;
- choose cohorts, targets, folds, thresholds, or success rules;
- compute panel features/metrics/verdicts;
- reconstruct production policy;
- turn blocked results into successful exit/output semantics.

Challenge UI/reports/artifacts are English. Learning narrative may be
Indonesian. Identifiers and flags are English everywhere.

## 13. Artifact And Promotion Rule

Artifacts are immutable ml-saham-owned decision-support records. They must
carry the identities and counts required by the DoD and be written atomically.

Agents must not:

- overwrite a historical artifact to update its status;
- omit blocked/provisional state from exports;
- reopen legacy output with current default identities;
- write partial success after serialization/write failure;
- generate commands or code that directly applies a winner to ai-saham.

Promote packets are human checklists, never executable promotion plans.

## 14. Dependency And Performance Rule

- Justify new dependencies and keep optional ML extras optional.
- Do not add a network runtime dependency to challenge execution.
- Avoid loading the entire upstream DB when bounded cohort/date/column queries
  suffice.
- Avoid row-per-threshold/fold/run persistence in the shared database.
- Large panel/materialization work must state memory/storage estimates and use
  ml-saham-owned storage only.

## 15. Shared Worktree Rule

- Inspect status before edits and commits.
- Preserve unrelated modified/untracked files.
- Stage only task-owned files.
- No reset/restore/checkout/clean/broad stash without explicit approval and
  exact scope.
- No broad formatter over a dirty tree as a side effect.

## 16. Verification Rule

Use the quickstart verification matrix. Do not claim tests, live smoke, lint,
or read-only safety passed unless the exact command ran successfully.

The current repo has no green configured Ruff gate. Do not invent or falsely
report one. Enabling Ruff is a dedicated foundation task with baseline cleanup,
dependency/config, CI, and governance updates.

## 17. When To Stop

Stop and request clarification or a contract change if:

- the task requires upstream writes/imports/scrapers;
- policy, cohort, target, Protocol, or sample unit is materially unspecified;
- current code contradicts the task's premise;
- implementation would weaken leakage/verdict/read-only guards;
- a compatibility fallback or historical rewrite is required but not approved;
- unrelated worktree changes prevent safe scoped work.

When uncertainty is harmless, choose the simpler deterministic path and state
the assumption. Never resolve product/statistical ambiguity by guessing.
