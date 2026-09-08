# Agent Quickstart

Read this before every task. It is the mandatory entry point for agents working
in `ml-saham`. Longer governance files remain binding when the reading matrix
selects them.

## 1. Product Identity

`ml-saham` is:

1. an offline **challenge lab** for testing `ai-saham` policies, factors,
   gates, and challenger scorers under fixed protocols;
2. a secondary **learning/curriculum** surface that explains the methods.

It is not:

- a market-data ingestion service;
- a production signal, risk, TradeSetup, execution, or configuration engine;
- a writer or migration owner for `ai-saham` SQLite;
- an automatic tuning or promotion service;
- a place where a curriculum demo can silently become product authority.

Read `BOUNDARY.md` whenever work touches sibling data, policies, observations,
labels, production claims, or promotion.

## 2. Non-Negotiable Boundaries

### Sibling ownership

- `ai-saham` owns market/provider ingest, live engines, production config,
  observations, corpus labels, and the shared database schema.
- `ml-saham` owns offline panels, challenge protocols, challengers, metrics,
  verdicts, reports, and ml-saham-owned artifacts.
- Never import `ai-saham` Python modules. Exchange data through documented
  SQLite/export contracts only.
- Never add Stockbit, IDX, Yahoo, browser, token, or scraper integrations here.
- Never write, migrate, vacuum, repair, backfill, attach writable schemas to,
  or change pragmas persistently on the upstream database.
- Optional materialization may write only to an explicitly ml-saham-owned
  learning store or artifact directory.

### Challenge authority

- A challenge is a versioned comparison of a frozen baseline and named
  challenger under one fixed Protocol.
- `WIN`, `LOSE`, `INCONCLUSIVE`, `BLOCKED_DATA`, and `BLOCKED_POLICY` are
  contract states, not presentation choices.
- Never downgrade a blocked or inconclusive result to a warning plus success.
- Never call a baseline `production` without a verifiable production-policy
  identity for the selected cohort and a supported challenge adapter.
- Follow the closed production-baseline truth table in `PROMPT_CONTRACT.md`
  section 5. Never rewrite the requested baseline: omitted/explicit
  `production` without verified identity is `BLOCKED_POLICY`, while
  `static_reference` runs only when explicitly requested and is never
  promotion-eligible.
- Never use a packaged/static mirror as a silent fallback when a verified
  upstream policy contract is required.
- A result may create a human review memo or promote packet. It must never edit
  ai-saham YAML, SQLite, or live code.

### Curriculum wall

- `src/ml_saham/challenge/` is product challenge authority.
- `src/ml_saham/chapters/` is pedagogy. Its simplified calculations and
  `learn compare` results do not authorize policy verdicts.
- Shared pure metrics may be reused, but product feature meaning must be
  re-derived and contract-tested in the challenge path.
- Challenge-facing output and artifacts are English. Learning narrative may be
  Indonesian. Commands, flags, IDs, slugs, and code identifiers stay English.

## 3. Data Honesty And Leakage Rules

### Upstream reads

- Resolve upstream DB paths through the existing data boundary and open SQLite
  read-only (`mode=ro`/equivalent). Do not rely on filesystem permissions alone.
- Centralize `learning_observations` access through
  `ml_saham.data.observation_cohort`; do not add raw observation SQL to panels,
  chapters, CLI, or scorers.
- Schema/query/JSON/contract errors propagate or become a typed fail-closed
  state at the named application boundary. They are never interpreted as zero
  rows, zero signal, or ordinary missingness.
- Missing is not zero. Unsupported is not missing. Unavailable labels are not
  negative outcomes.

### Cohorts and population

- Never mix compatibility IDs in one panel, fold set, metric, or verdict.
- Production-facing challenges require an explicit compatibility ID. Do not
  auto-select largest/latest when publishing or reopening a policy verdict.
- Largest-cohort discovery is acceptable only for explicitly exploratory or
  curriculum output that visibly records the selected/excluded cohorts.
- Panel grain is explicit: ticker/session, observation, or another named unit.
  Feature windows must not multiply independent sample count unless the
  protocol explicitly defines them as units.
- Report denominator, exclusions, missingness, source-unavailable rows, and
  horizon-unavailable rows. Do not claim full-universe recall from a
  broker-observable or candidate-only population.

### Point-in-time and labels

- Distinguish economic date, fetched/available time, capture time, decision
  cutoff, label horizon, and label availability.
- Every feature must be knowable at or before its row cutoff. Later snapshots
  cannot be rebound to historical decisions because dates look compatible.
- Horizon and benchmark must match. Never subtract a full-day benchmark from a
  partial-session stock return.
- Units are explicit and unconditional. Do not infer percent versus fraction
  from numeric magnitude.
- Accum lookbacks 7/30/90 are features; challenge outcome horizons are 3/10/20
  with primary H=10 unless a versioned Protocol says otherwise.
- ai-saham corpus outcome labels and ml-saham protocol targets are distinct
  products unless a Protocol explicitly names the corpus-label source.

### Statistical validity

- No random row shuffle for time-dependent labels.
- Fit scalers, imputers, feature selection, models, thresholds, and calibration
  only on training data inside each fold.
- Use ordered walk-forward/purged splits and the protocol embargo.
- Do not inspect OOS outcomes to choose the challenger, threshold grid, feature
  set, primary metric, or success rule and then report that same OOS result as
  confirmatory.
- Report fold count and fold-wise results. Current product law requires at
  least two valid OOS folds for `WIN`; a one-fold edge is provisional
  `INCONCLUSIVE`.
- Respect minimum N, missingness, tail, stability, and multiplicity rules. Do
  not select the best of many trials without recording the search and applying
  the protocol's selection discipline.
- Seeds are explicit where algorithms are stochastic. Same inputs, identities,
  config, dependency versions, and seed must reproduce the same result.

## 4. Contract And Identity Discipline

A challenge result must keep these concepts separate:

- observation cohort identity;
- verified production policy snapshot identity and digest;
- ml-saham challenge adapter ID/version;
- Protocol ID/version;
- baseline and challenger IDs;
- panel/data range and population identity;
- source/code revision and relevant dependency versions;
- artifact ID/schema.

Value-equivalent reconstructed objects are not identity-equivalent. Do not
discard provenance early, re-query a replacement row, or combine these concepts
inside one overloaded `hash` string.

Every semantic identity must change when any material dimension it claims to
cover changes. Require mutation tests for each dimension; a non-empty or
hash-shaped ID is not evidence that the correct material was bound. Keep
membership identity separate from input-content/batch identity when their
material sets differ.

When reopening an artifact, validate its schema and identities. Historical
artifacts may be displayed as historical output but must not acquire current
promotion eligibility through fallback/default values.

## 5. Module Boundaries

This repository is not a clone of ai-saham's production hexagonal layout. Use
its actual boundaries:

| Area | Owns | Must not own |
|---|---|---|
| `data/` | Read-only upstream connection, schema checks, cohort selection, row extraction | Metrics, verdicts, CLI rendering, upstream writes |
| `challenge/` | Specs, policies, protocols, panels, challengers, orchestration, verdict contracts | Provider ingest, ai-saham behavior, curriculum shortcuts |
| `eval/` | Reusable pure/statistical calculations | Product-specific identity defaults or CLI policy |
| `artifacts/` | ml-saham-owned serialization/writes | Production promotion or upstream DB writes |
| `cli/` | Parse, resolve dependencies, call product functions, render/map errors | Feature math, cohort policy, protocol mutation, verdict invention |
| `ui/` | Thin local presentation, navigation, form state, launcher | Direct SQL/artifact parsing, CLI scraping, metrics, readiness, verdicts, identity inference |
| `chapters/` | Learning narrative and demos | Challenge registry or promotion authority |

Prefer typed immutable contracts and explicit function parameters. Do not add a
DI framework or global service locator. CLI construction may remain pragmatic,
but non-trivial product decisions belong in challenge/data/eval modules.

## 6. Semantic Change Classification

Before changing challenge behavior, classify the work using one or more:

- `DATA_CONTRACT`: upstream table/column/path, availability, cohort, PIT, unit,
  or missingness meaning changes.
- `PANEL_SCHEMA`: sample unit, feature/target shape, extraction path, or panel
  population changes.
- `POLICY_CONTRACT`: baseline/challenger definition or production-policy
  verification changes.
- `PROTOCOL_CONTRACT`: universe, target, horizon, costs, fold, embargo, min-N,
  metric, or success law changes.
- `VERDICT_SEMANTICS`: status/factor verdict calculation or blocking behavior
  changes.
- `ARTIFACT_SCHEMA`: persisted/exported result shape or identity changes.
- `CLI_CONTRACT`: command, flag, exit code, output language, or JSON shape
  changes.
- `CURRICULUM_ONLY`: learning narrative/demo behavior changes with no challenge
  authority.
- `NON_SEMANTIC`: comments/docs/refactor only; computed panels, metrics,
  verdicts, identities, and outputs remain unchanged.

A contract change requires a version bump or explicit clean break. Do not label
a behavior change `NON_SEMANTIC` merely because existing tests pass.

## 7. Clean-Break And Compatibility Rules

- Preserve historical artifacts as historical truth; never rewrite them to
  look current.
- Removed policy/protocol/field identities must not survive as silent aliases,
  fallback paths, dual writes, or auto-upgrades unless an accepted migration
  contract explicitly requires it.
- Legacy payload fallback is allowed only when a current accepted contract
  names the exact field, scope, and sunset behavior. New product work must not
  broaden legacy fallback opportunistically.
- Never auto-select a different cohort, snapshot, policy, adapter, or protocol
  because the requested one is missing.
- A task that needs compatibility must state why quarantine/rebuild is not
  sufficient and define negative tests.

## 8. Challenge Extract Gate

Any new or changed product panel/extractor must follow
`docs/challenge_extract_contract.md`:

- real/live-shaped redacted golden JSON;
- tests call shipped extraction/classification code, not a test reimplementation;
- explicit primary and legacy paths;
- units, horizon, benchmark, PIT/capture, missing behavior, and sample unit;
- empty/wrong-path inputs fail closed rather than produce false zero rates;
- `data_contract.md` extract table updated when contracts change;
- `./scripts/check_challenge_contracts.sh` passes.

For upstream DB work, add a read-only tripwire that compares relevant file
metadata and SQLite page/count state before and after the operation.

## 9. Verification Gate

Inspect `git status --short` before edits and before commits. Preserve unrelated
changes and stage only owned files.

### Mandatory current gates

| Change | Required verification |
|---|---|
| Documentation only | `git diff --check`; validate referenced local paths/commands |
| Challenge panel/extractor/protocol/verdict | focused tests; `./scripts/check_challenge_contracts.sh`; affected ADR-002 acceptance tests |
| Cohort/upstream data reader | observation cohort guards; focused read-only tests; contract script; live smoke when a maintainer DB is available |
| CLI/output | focused CLI tests and representative `CliRunner`/command smoke |
| Streamlit/UI | focused facade/launcher/AppTest tests; architecture import guard; core install/import without UI extra; responsive/browser tests when layout becomes material |
| Artifact schema/writer | focused round-trip, reopen, immutability, failure/atomicity tests |
| Curriculum only | focused phase/chapter tests; prove challenge registry/output unchanged |
| Broad/shared Python change | full `pytest -q` in addition to focused/current CI gates |

Every Python change must also run:

```bash
python -m compileall -q src tests
git diff --check
```

CI's current executable gate is `.github/workflows/ci.yml`. At minimum, do not
close Python work unless every affected CI command passes locally or an exact,
unrelated environment failure is documented.

### Push CI gate

A SHA is not eligible for `main` until GitHub Actions is green on it. Local
focused tests and CI-equivalent commands are necessary, not sufficient. This
rule is the same in sibling `ai-saham`.

Workflow `.github/workflows/ci.yml` runs on every branch push and on pull
requests. GitHub ruleset `main requires CI` rejects updates to `main` whose
SHA lacks a green `challenge + core tests` check. A new commit therefore
cannot be pushed straight to `main`.

1. Push owned commits to a working branch (or open a PR).
2. Wait until a workflow run exists for the SHA
   (`gh run list --commit <sha>`).
3. Watch it to completion: `gh run watch --exit-status <run-id>`.
4. Required workflow here is `.github/workflows/ci.yml`
   (`challenge + core tests`).
5. After it is green, update `main` (fast-forward that SHA, or merge the PR).
6. If CI fails, fix and push the branch again. Do not report the task done on
   a pending or red run. Do not leave `main` red.

### Ruff foundation gap

This repository currently has no accepted Ruff dependency/configuration or
green whole-repo Ruff baseline. Agents must not claim Ruff passed and must not
invent a one-off rule set in an unrelated task.

Activating Ruff is a separate foundation change that must:

1. define and document the rule set;
2. make `ruff check src/ tests/` and `ruff format --check src/ tests/` green;
3. add Ruff to development dependencies and CI;
4. update this quickstart, DoD, and checklist atomically.

After that lands, whole-repo Ruff becomes mandatory for every Python change.

### Existing transition debt is scoped, not permission

Some shipped paths and older docs still use static policy mirrors or implicit
largest-cohort selection. A verified production-policy snapshot consumer is an
active clean-break direction, not a reason to relabel the existing behavior as
already verified.

Apply the DoD to the active task and every path it changes. An unrelated small
fix does not have to repair the entire repository, but it must not extend,
normalize, or rely on known transitional behavior. When touching one of these
paths, follow its current accepted task/ADR and add the required fail-closed
cutover. Record material pre-existing violations instead of silently
grandfathering or opportunistically fixing them outside scope.

### Live DB tests

`tests/test_challenge_live_smoke.py -m live_db` is required when a change makes
claims about the maintainer corpus and the DB is available. It is never a
substitute for deterministic fixtures/goldens. Record the selected cohort and
prove the upstream DB was unchanged.

## 10. Shared Worktree Safety

- Treat all existing modified/untracked files as user or other-agent work.
- Never use `git reset`, `git checkout --`, `git restore`, `git clean`, broad
  stash, or deletion to obtain a clean tree without explicit approval and
  exact file scope.
- Do not overwrite an uncommitted file merely because a committed version is
  easier to understand.
- Formatting/bulk rewrites must not touch unrelated files.
- Stage and commit only files owned by the active task.

## 11. Dependency-Ordered Authority Harness

Any task that creates or changes readiness, eligibility, production-baseline
verification, challenge handoff, artifact reopen, verdict, or promotion must
contain a completed task-specific authority matrix before coding. Inventory
every upstream/reference artifact and every field that can grant, deny, group,
or identify authority; do not leave source, coverage, identity, missing state,
or failure behavior to implementer judgment.

Required implementation order:

1. Lock the authority owner/source and missing/failure semantics.
2. Lock data/artifact schema, identity, compatibility, and cross-repo blast
   radius.
3. Implement or verify the canonical upstream producer contract.
4. Implement persistence/export and genuinely read-only retrieval.
5. Implement extractors, challengers, validators, reopen, and promotion
   consumers.
6. Wire every CLI, artifact, batch, and alternate production composition root.
7. Run real producer/export -> read-only load -> extraction -> artifact/reopen
   round trips, independent mutation tests, and complete close gates.

Do not tighten a consumer before proving its canonical producer/export emits
the required contract. Do not substitute a static mirror, reconstructed value,
or existing provider merely because its return type fits.

Minimum authority-matrix rows:

| Artifact / boundary | Authority owner/source | Exact identity and coverage | Integrity/lineage proof | Missing state | Invalid/conflicting state | May contribute when |
|---|---|---|---|---|---|---|
| Upstream observation/label/population | Exact ai-saham producer and read-only contract | Schema/contract, cohort, population, cutoff/session/horizon, row keys | Recompute/verify identity and digest; preserve exact consumed rows | Typed blocked/insufficient state | Wrong schema/cohort/population/PIT/linkage fails closed | Every consumed row and its population/PIT meaning verifies |
| External/reference authority | Named calendar, benchmark, embargo/session, or other reference owner | Source contract/version, coverage bounds, revision/completeness identity, consumed keys | Prove the exact interval/set complete; absence is not proof of holiday, zero, or non-membership | Unproven coverage is distinct from authoritative empty | Stale, partial, future-dependent, ambiguous, or mismatched authority fails closed | Exact consumed coverage and revision are proven through a read-only path |
| Production policy snapshot/baseline | Authoritative ai-saham snapshot store | Snapshot ID/digest, compatibility cohort, purpose, adapter and policy versions | Re-resolve from upstream read-only DB; no hash-shape or packaged-mirror proof | Historical/display-only or `BLOCKED_POLICY` as locked | Missing DB authority, mismatch, fallback, or unsupported contract blocks | Current supported production identity verifies |
| Challenge panel/protocol/verdict | Named ml-saham extractor and Protocol | Panel grain, feature/target/horizon, split/embargo, adapter/protocol IDs | Preserve upstream lineage through folds and artifact identity | Exact `BLOCKED_DATA`/`INCONCLUSIVE` behavior | Leakage, pooling, identity loss, insufficient folds, or semantic mismatch blocks | All upstream authority and Protocol gates pass |
| Artifact/export/reopen/promotion | Named ml-saham writer and reader | Artifact schema/ID, cohort, population, snapshot, protocol, baseline/challenger, revisions | Round-trip and re-resolve production authority; immutable content digest | Historical artifacts remain ineligible | Unsupported schema or any identity mismatch blocks reopen/promotion | Current artifact and authoritative upstream identities both verify |
| Repository/transport boundary | Named port and concrete adapter | DB/file URI, row keys, serialized identity fields, connection mode | Prove no upstream writes and no replacement rows/defaults | Missing file/table/row is explicit | Query/schema/serialization errors fail closed | Exact authoritative rows arrive through the permitted read-only path |

Enforcement rules:

- Read-only applies transitively to every constructor, connection factory,
  context manager, lazy initializer, schema ensure, migration, repair hook,
  directory creation, attach, and persistent PRAGMA. Tests must prove missing
  paths remain missing and upstream file metadata, schema, page/count state,
  and rows remain unchanged; use SQLite `mode=ro`/query-only where applicable.
- For every tightened consumer invariant, tests must use a real canonical
  producer/export artifact or shared golden emitted by it, then read,
  deserialize, extract, write/reopen where applicable, and validate it through
  the real downstream boundary. Hand-built consumer-shaped happy paths are not
  sufficient.
- Producer and consumer must use the same cohort, population, session, horizon,
  cutoff, policy, and provenance axes. Value-equivalent reconstruction is not
  lineage equivalence.
- Derive calendar, benchmark, embargo/session, and other reference coverage
  from the exact consumed rows/artifacts. Test newest immature rows, older
  mature rows, unavailable future dates, holidays/interior gaps, and cohorts
  with different ranges. Never request hypothetical future coverage for an
  artifact that does not yet exist.
- Before changing a shared or cross-repo schema/version, inventory every
  producer, consumer, compatibility hash, command, Protocol, and artifact that
  imports it. Use a purpose-specific version when the change is purpose-specific
  unless every affected workflow is explicitly authorized to fork.
- Close-gate evidence must be rerun after the final production/test edit and on
  the exact commit/state claimed complete. Any later code, fixture, composition,
  schema, dependency, or golden change invalidates earlier green output.

## 12. Required Reading Matrix

Always read:

- `AGENT_QUICKSTART.md`;
- `AGENTS.md`;
- the active task/specification.

For code changes, also read:

- `DEFINITION_OF_DONE.md`;
- relevant `PROMPT_CONTRACT.md` sections;
- relevant `AI_AGENT_CHECKLIST.md` sections;
- current code and focused tests.

| Task area | Additional required reading |
|---|---|
| Repo ownership, upstream DB, observations, labels, production claims | `BOUNDARY.md`, `data_contract.md` |
| Challenge policy/protocol/verdict/engine | ADR-001, ADR-002, `docs/challenge_product.md`, `challenge_acceptance.md` |
| Panel/extractor/payload path | `docs/challenge_extract_contract.md`, relevant row in `data_contract.md`, goldens and payload tests |
| Cohort selection | `BOUNDARY.md`, `data_contract.md`, `src/ml_saham/data/observation_cohort.py`, cohort guard tests |
| Production policy snapshot/baseline | ADR-002 plus the active cross-repo snapshot contract/task; inspect current consumer code and tests |
| PIT, labels, horizons, folds, leakage | ADR-002, `data_contract.md`, relevant Protocol and verdict tests |
| Artifact/export/promote packet | `artifacts.md`, ADR-002 artifact sections, writer/reopen/promote tests |
| CLI/product vocabulary | `README.md`, `docs/challenge_product.md`, relevant CLI tests |
| Curriculum | ADR-001, `chapters.md`, registry, affected chapter/phase tests |
| Architecture/module boundary | `architecture.md`, `BOUNDARY.md`, current imports and architecture/guard tests |
| Streamlit/Challenge Desk | ADR-003, `ux.md`, `architecture.md`, typed workbench facade, launcher/UI tests |
| Task scoping or handoff | `TASK_TEMPLATE.md` |

Read only the relevant ADRs under `docs/adr/`; use `docs/adr/README.md` as the
index. Trust current executable code/tests for implemented behavior, accepted
ADRs for intended contracts, then current product/data docs. Flag drift rather
than silently choosing whichever source is convenient.

## 13. Before Editing

1. Identify task type and semantic classifications.
2. Read the selected sources.
3. Inspect current code/tests and `git status --short`.
4. State risks, ambiguities, assumptions, and the boundary plan.
5. Define sample unit, population, identities, missing/failure states, and
   write targets when data is involved.
6. Pick focused tests plus the required matrix gates.
7. Stop if the contract would permit leakage, upstream writes, identity
   inference, silent fallback, or auto-promotion.

## 14. Final Reporting

Lead with the result. Report:

- what changed and why;
- semantic classifications and contract/version changes;
- tests/gates run with exact outcomes;
- live DB/cohort evidence when used;
- any known limitations or unrelated failures;
- files/commit IDs when committed;
- GitHub Actions conclusion on the pushed SHA when a push happened;
- confirmation that upstream SQLite and unrelated worktree changes were not
  modified.

Do not call work complete when a mandatory acceptance item remains open, or
when GitHub Actions is still pending or red on a commit that updated `main`.
