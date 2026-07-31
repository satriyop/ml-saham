# Task Template

Every non-trivial `ml-saham` work item must be specified before implementation.
If the fields material to the task are unresolved, the task is not ready.

## 1. Metadata

```text
Title:
Status: DRAFT | READY | BLOCKED | DONE
Type: feature | bugfix | refactor | research | documentation
Priority: High | Medium | Low
Primary owner: ml-saham | ai-saham | cross-repo
Semantic classifications:
```

Use classifications from `AGENT_QUICKSTART.md`:
`DATA_CONTRACT`, `PANEL_SCHEMA`, `POLICY_CONTRACT`, `PROTOCOL_CONTRACT`,
`VERDICT_SEMANTICS`, `ARTIFACT_SCHEMA`, `CLI_CONTRACT`, `CURRICULUM_ONLY`, or
`NON_SEMANTIC`.

## 2. Problem Statement

State:

- what current executable behavior is wrong or missing;
- who/what is affected;
- evidence from current code, tests, data, or artifacts;
- why existing blocked/inconclusive behavior is or is not correct;
- relevant stale-doc contradictions.

Do not prescribe a solution in this section.

## 3. Product Question And Null

For challenge work, define before implementation:

```text
Product question:
H0 / comparison claim:
Decision type: rank | score | gate | size | label | diagnostic
Human decision supported:
What the result cannot authorize:
```

If H0/comparison cannot be stated, this is not a policy challenge. Reclassify
it as diagnostic, research, infrastructure, or curriculum work.

## 4. Desired Outcome

Describe observable behavior, contracts, statuses, and artifacts. Include:

- positive path;
- blocked/unavailable/malformed paths;
- exact output/status/exit behavior when user-facing;
- what is versioned or clean-broken;
- handoff to ai-saham, if any, without automatic writes.

## 5. Non-Goals

Explicitly exclude at least:

- upstream ingest/schema/config writes unless this is an ai-saham-owned task;
- sibling Python imports;
- auto-promotion;
- protocol/grid invention outside the named decision;
- curriculum authority over challenge results;
- compatibility fallback or historical rewrite unless explicitly approved.

Add task-specific exclusions.

## 6. Authority And Boundary Assessment

Answer:

```text
ai-saham-owned inputs:
ml-saham-owned outputs:
Upstream DB access mode:
Any ml-saham-owned writes:
Production behavior affected: Yes/No
Auto-promotion possible: No
External/network dependency: Yes/No, why
```

State the implementation plan:

```md
Boundary plan:
- Data/read boundary:
- Challenge contracts and orchestration:
- Evaluation/statistics:
- Artifacts:
- CLI:
- Curriculum:
```

## 7. Data Contract

For every input/target, specify:

```text
Source owner/table/export:
Required columns/payload paths:
Purpose and compatibility_id:
Sample unit/grain:
Population/denominator:
Economic date:
Available-at/cutoff rule:
Missing vs unavailable vs unsupported behavior:
Units:
Cardinality and dedupe key:
Legacy fallback, if accepted:
```

State whether the upstream source is semantically equivalent to any source it
replaces. Similar names are not evidence. Check cardinality, owner, aggregation,
PIT behavior, field meaning, local sample, and display/JSON naming.

## 8. Policy And Adapter Contract

When a production baseline or counterfactual is involved:

```text
Production policy_id/version:
Snapshot contract/id/digest:
Selected compatibility_id:
Challenge adapter id/version:
Supported semantic contracts:
Baseline fields:
Challenger ids and definitions:
Missing/mismatch status: BLOCKED_POLICY
Golden conformance vectors:
```

Keep production identity separate from ml-saham extraction, aliases, scoring
dispatch, and Protocol.

## 9. Protocol And Leakage Contract

Specify before outcome inspection:

```text
Protocol id/version:
Universe/population:
Target and benchmark:
Horizons and primary horizon:
Costs:
Fold construction:
Embargo:
Train-only transforms/model fitting:
Minimum N and valid folds:
Primary and secondary metrics:
Success/LOSE/INCONCLUSIVE rules:
Multiplicity/search rule:
Seed policy:
```

Changing any of these materially requires `PROTOCOL_CONTRACT` and a version
bump or clean break.

## 10. Failure And Exception Contract

Name exact behavior for:

- missing table/column;
- empty selected cohort;
- mixed/wrong cohort;
- malformed JSON or non-finite numeric;
- missing/invalid snapshot;
- unsupported adapter/semantic contract;
- horizon unavailable;
- insufficient N/folds;
- artifact write failure;
- programmer/invariant errors.

Do not allow broad exception handling to convert contract corruption into an
ordinary empty panel.

## 11. Artifact And Output Contract

Specify:

```text
Artifact schema/version:
Artifact ID inputs:
Required identity fields:
Data range/population counts:
Fold/metric tables:
Human checklist language:
CLI/JSON/Markdown outputs:
Reopen behavior for historical artifacts:
Atomic/immutable write behavior:
```

Challenge artifacts are English and never apply production changes.

## 12. Storage And Performance

- Estimate upstream reads and ml-saham-owned writes.
- State whether panels remain in memory or are materialized.
- Never write one upstream row per threshold/fold/run.
- Define bounded queries and indexes relied upon.
- For shared DB reads, define a no-mutation tripwire.
- State expected artifact/database growth and cleanup/retention ownership.

## 13. Testing Expectations

List exact tests for:

- happy path;
- negative/fail-closed paths;
- identity/provenance;
- PIT/leakage and train-only fitting;
- units/horizon/benchmark;
- cohort non-mixing;
- deterministic seed/reproduction;
- artifact round trip/atomicity;
- CLI status/exit behavior;
- upstream read-only tripwire.

Name exact commands selected from the verification matrix. New/changed panels
require live-shaped goldens and shipped-extractor tests.

## 14. Acceptance Criteria

Use checkboxes with observable outcomes. Include:

- [ ] exact desired behavior and negative states;
- [ ] no upstream writes/imports/scrapers;
- [ ] no leakage or identity inference;
- [ ] no curriculum or static-fallback authority;
- [ ] no auto-promotion;
- [ ] focused/current CI/full relevant gates;
- [ ] `python -m compileall -q src tests` for Python;
- [ ] `git diff --check`;
- [ ] docs and completion record updated;
- [ ] unrelated worktree changes preserved.

## 15. Documentation Impact

State required changes to:

- ADR-001/ADR-002 or new ADR;
- `BOUNDARY.md`;
- `data_contract.md`;
- challenge product/extract/operator docs;
- `README.md`/CLI help;
- artifacts/protocol/policy docs;
- sibling task/contract.

## 16. Agent Execution Instructions

Before editing, require the implementer to:

1. read the harness-selected sources;
2. inspect current code/tests and both worktrees when cross-repo;
3. restate hard invariants and forbidden interpretations;
4. list exact expected files and production composition/call paths;
5. identify the foundation checkpoint before broad integration;
6. stop if current code contradicts the task materially.

## 17. Do Not Interpret This As

List plausible but forbidden shortcuts, especially:

- warning-and-continue instead of blocking;
- implicit largest/latest cohort selection;
- static production mirror fallback;
- test-only parser instead of shipped extractor;
- random split or global preprocessing;
- artifact success after partial failure;
- writing ai-saham DB/YAML;
- auto-promoting a result.

## 18. Completion Record

```text
Completed date:
Commits:
Selected cohort/policy/protocol/adapter identities:
Data/population/fold counts:
Artifact IDs:
Commands and outcomes:
Live read-only smoke/tripwire:
Known limitations/unrelated failures:
Downstream human decision status:
```

## Final Readiness Gate

A task is `READY` only when the implementer is not left to invent the sample
unit, policy identity, target, fold law, missing behavior, verdict rule, write
target, or cross-repo ownership boundary.
