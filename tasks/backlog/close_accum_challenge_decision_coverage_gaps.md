# Close Accum Challenge Decision-Coverage Gaps (G0-G4)

Status: `READY_AFTER_IN_FLIGHT_HARDENING`

Source: code-first product-gap audit and roadmap revision on 2026-07-31.

Companion producer task:

- `~/dev/ai-saham/tasks/backlog/grow_snapshot_bound_accum_challenge_corpus.md`

## 1. Task Metadata

- Task type: ordered challenge-product program
- Priority: Critical
- Primary owner: `ml-saham`
- Cross-repo dependency: `ai-saham` owns observations, labels, production policy
  snapshots, and the shared SQLite database.
- Semantic classifications by checkpoint:
  - C0 readiness reporting: `CLI_CONTRACT`, `ARTIFACT_SCHEMA`
  - C1 risk decision quality: `PROTOCOL_CONTRACT`, `VERDICT_SEMANTICS`,
    `ARTIFACT_SCHEMA`
  - C2 hard-filter tournament: `POLICY_CONTRACT`, `PROTOCOL_CONTRACT`,
    `VERDICT_SEMANTICS`, `ARTIFACT_SCHEMA`
  - C3 configured group breadth: blocked architecture dependency; no challenge
    classification until ai-saham establishes a real production PolicySpec
  - C4 Action/readiness: `DATA_CONTRACT`, `PROTOCOL_CONTRACT`,
    `VERDICT_SEMANTICS`, `ARTIFACT_SCHEMA`
- This task-file creation is documentation-only and `NON_SEMANTIC`.
- Chosen decision: implement the checkpoints in order and stop at each explicit
  gate. Extend the existing `challenge health`, `challenge run`, `challenge
  engine`, and `vet` product surfaces; do not create a disconnected evaluator.
  Implement this option only.

Sequencing guard: current uncommitted snapshot/cohort/promotion hardening in the
shared worktree must be reviewed, owned, and landed or deliberately superseded
before C0 implementation starts. Do not edit over that work.

## 2. Problem Statement

The challenge lab has useful sleeve, signal, risk, factor, diagnostic, and
promotion-support paths, but it does not yet cover every material production
decision influence.

Current executable/data evidence:

- cohort `sha256:005363...` has 1,890 observations over 42 sessions but no
  required v2 policy snapshots, so production comparison correctly returns
  `BLOCKED_POLICY`;
- cohort `sha256:8ba8fc...` has 304 observations, one session, and all seven v2
  snapshots, but yields only one valid post-embargo OOS fold, so production
  verdicts remain `INCONCLUSIVE`;
- on that slice, risk gates block about 83% OOS and the allowed book is better
  than `gate_off`, while raw signal H10 IC is inconclusive;
- risk output does not quantify false-block cost, harmful allows, gate-family
  contribution, or multi-regime stability;
- screen hard-filter extraction/replay and v2 identity exist, but the challenge
  adapter lacks golden conformance and a registered tournament;
- sector/group breadth is configured and its pure applier can change Accum
  score, but current ai-saham production factories do not inject `idx_groups`;
  the executable path skips it, so no production challenge baseline exists;
- the active v2 cohort has no ENTER rows and only 11/304 rows with non-null
  readiness, so an Action verdict would currently be statistically dishonest.

The blocked/inconclusive outcomes are correct safeguards. The product gap is
the missing operational coverage and decision-specific protocols, not a need to
weaken those safeguards.

## 3. Product Questions And Nulls

### C1 risk gates

```text
Product question: Do production risk gates improve the H10 decision book versus
  a predeclared gate-off challenger without hiding costly false blocks?
H0 / comparison claim: Production does not improve net H10 decision quality
  versus the challenger, or the apparent improvement is unstable across folds.
Decision type: gate
Human decision supported: retain, investigate, or propose a separately reviewed
  change to one named risk gate.
What the result cannot authorize: disabling a safety gate or changing production.
```

### C2 screen hard filters

```text
Product question: Does each configured first-match screen hard filter improve
  H10 decision quality relative to its predeclared off/threshold challenger?
H0 / comparison claim: The filter does not improve H10 decision quality after
  opportunity cost, harmful allows, fold stability, and multiplicity are counted.
Decision type: gate
Human decision supported: retain or nominate one filter configuration for review.
What the result cannot authorize: changing ai-saham YAML or live filtering.
```

### C3 configured group breadth (blocked)

```text
Product question: none yet; current production composition skips the configured
  applier because no group mapping is injected.
H0 / comparison claim: undefined until ai-saham establishes production behavior.
Decision type: blocked architecture dependency
Human decision supported: none.
What the result cannot authorize: treating configured or isolated-test behavior
  as a production baseline.
```

### C4 Action/readiness

```text
Product question: Does final production Action/readiness partition future H10
  outcomes better than its locked comparison once class support is sufficient?
H0 / comparison claim: ENTER/readiness states add no stable net H10 decision
  value over the locked pre-Action comparison.
Decision type: gate
Human decision supported: investigate Action composition and nominate a change.
What the result cannot authorize: issuing trades or changing Action authority.
```

C0 is readiness infrastructure, not a policy challenge and has no WIN/LOSE.

## 4. Desired Outcome And Ordered Checkpoints

### C0 - challenge readiness visibility

Extend existing `vet` and/or `challenge health` composition so a selected
ACCUM cohort reports, in table and JSON/artifact form:

- exact `compatibility_id`; never implicit largest/latest selection;
- observation count, distinct session count, min/max economic date;
- required snapshot contract, verified policy IDs, and `7/7` completeness;
- label/outcome availability by H3/H10/H20;
- protocol-estimated post-embargo valid fold count;
- Action distribution and readiness present/missing counts;
- explicit status: `BLOCKED_POLICY`, `BLOCKED_DATA`, `READY_FOR_PROTOCOL`, or
  `INCONCLUSIVE_DEPTH` with machine-readable reasons.

This report is read-only and does not itself produce a challenge verdict.

### C1 - deepen risk-gate decision quality (first scoring deliverable)

Version a gate-decision protocol derived from `accum_path_v1` with primary H10,
H3/H20 secondary reporting, 20-session embargo, chronological expanding folds,
and at least two valid OOS folds for WIN. Lock before outcome inspection:

- production and `gate_off`/one named `gate_off:<gate_key>` challengers;
- allowed-book and blocked-book population counts and mean/median H10 excess;
- false-block rate = blocked rows with H10 excess greater than zero;
- harmful-allow rate = allowed rows with H10 excess at or below zero;
- opportunity cost = mean H10 excess of blocked rows, shown with denominator;
- per-gate first blocker and overlapping-block attribution;
- fold-by-fold block rate and every primary metric;
- a multiplicity rule for named-gate comparisons.

Do not reuse rank IC as the gate verdict. WIN requires a locked improvement
criterion, required fold agreement, sufficient population on both sides, and no
material regression in the safety metric. Otherwise return `LOSE` or
`INCONCLUSIVE` with reasons.

### C2 - complete the screen hard-filter tournament

Use only verified `screener.accum.hard_filters` v2 cohort snapshots and the
shipped first-match replay. Before engine registration:

- add live-shaped golden vectors for market-cap, Piotroski, Accum-score, and
  Signal-score filters, including missing/provider error actions and order;
- prove the adapter reproduces the frozen production result for every vector;
- predeclare the off/threshold grid, population denominator, H10 target,
  multiplicity law, minimum per-side support, and verdict rule;
- emit the C1 decision-quality metrics, including rejected/control populations;
- register the PolicySpec only after conformance and protocol tests pass.

Snapshot absence/mismatch, unsupported semantics, missing control population,
or inadequate folds returns `BLOCKED_POLICY`/`BLOCKED_DATA`; never approximate.

### C3 - challenge group/sector breadth only after production authority exists

Remain `BLOCKED_POLICY`. The companion `ai-saham` corpus task explicitly does
not publish v3 because current production factories leave `_ticker_to_group`
empty and skip the applier. A snapshot of configuration intent would be false
production authority.

Only after a separate ai-saham architecture task decides and implements the
actual production concept (conglomerate-group versus sector breadth), PIT
membership identity, overlap rule, scoring order, and Action interaction may a
producer snapshot follow. Then ship a separate adapter, golden conformance
vectors, and locked challengers. Never reconstruct the rule from observations
or current YAML.

### C4 - Action/readiness only after a hard data gate

Do not implement an Action verdict until C0 proves all of:

- full compatible snapshot set;
- at least two valid post-embargo folds;
- non-zero and protocol-sufficient ENTER/non-ENTER support in each required
  test fold;
- typed readiness coverage sufficient for each reported state;
- H10 outcomes available under one locked PIT/benchmark contract.

When the gate passes, add an Action-specific protocol and artifact. If any class
or readiness state lacks support, return `BLOCKED_DATA`; do not merge classes,
impute readiness, or substitute signal IC.

## 5. Non-Goals

- No writes, migrations, repair, or snapshot synthesis in `ai-saham` SQLite.
- No sibling Python imports, scrapers, providers, or network fetch.
- No auto-promotion or automatic production configuration change.
- No v1 snapshot fallback, current-policy mirror, historical reinterpretation,
  implicit cohort selection, or compatibility inference.
- No challenge of inventory rows that cannot state a decision, H0, outcome,
  PIT population, and production identity.
- No curriculum demonstration as challenge authority.
- No Action protocol while its explicit data gate is unsatisfied.

## 6. Authority And Boundary Assessment

```text
ai-saham-owned inputs: observations, path labels, candles/benchmark data,
  production policy snapshots, Action/readiness payload fields
ml-saham-owned outputs: readiness reports, panels, adapters, protocols,
  verdicts, immutable challenge artifacts
Upstream DB access mode: SQLite read-only
Any ml-saham-owned writes: artifacts only under this repository
Production behavior affected: No
Auto-promotion possible: No
External/network dependency: No
```

Boundary plan:

- Data/read boundary: explicit-cohort, read-only, PIT extraction and snapshot
  verification; no repair or second source.
- Challenge contracts and orchestration: ordered C0-C4 gates using existing
  challenge/health/vet composition roots.
- Evaluation/statistics: versioned gate, score, and later Action protocols.
- Artifacts: versioned immutable English reports with full identities/counts.
- CLI: extend existing surfaces; no alternate scoring in the adapter.
- Curriculum: not touched; may link to shipped artifacts only.

## 7. Data Contract

```text
Source owner/table/export: ai-saham learning_observations,
  learning_policy_snapshots, learning_outcome_labels, candles
Required payload: features_by_window.7/30/90, shared.current_price,
  risk gate outcomes, screen hard-filter inputs/results, production Action,
  typed setup_readiness fields; sector breadth only under its new snapshot
Purpose and compatibility_id: ACCUMULATION_DISCOVERY, explicitly selected
Sample unit/grain: one ticker-session observation
Population/denominator: the complete selected compatible cohort after only
  protocol-declared availability exclusions
Economic date: observation session_date
Available-at/cutoff: values frozen by the producer at that session; forward
  outcomes start after it and folds obey embargo
Missing/unavailable/unsupported: distinct typed states; never numeric zero
Units: returns/excess are fractions; preserve source units for all inputs
Cardinality/dedupe: one row per observation identity/ticker/session
Legacy fallback: none
```

## 8. Policy, Protocol, Failure, And Artifact Contracts

- Verify snapshot digest, closed policy set, semantic contract, observation
  binding, compatibility ID, and adapter support before panel construction.
- Changing a protocol, metric threshold, grid, or verdict rule requires a new
  protocol identity. Changing output shape requires a new artifact schema.
- Missing table/column: fail closed, not an empty successful panel.
- Empty/mixed cohort or malformed/non-finite payload: fail closed with the
  corresponding data/contract reason.
- Missing/invalid/unsupported snapshot or adapter: `BLOCKED_POLICY`.
- Insufficient outcomes, side population, class support, or folds:
  `BLOCKED_DATA` or `INCONCLUSIVE` as declared by the protocol; never WIN.
- Artifact write failure: command fails and no partial-success manifest remains.
- Programmer/invariant error: propagate; do not convert to ordinary missing.
- Artifact identity includes cohort, snapshot IDs/digests, adapter, protocol,
  challenger grid, source data range, population/fold counts, and code
  provenance. Historical reopen never re-resolves current policy.

## 9. Storage And Performance

- Use bounded cohort/snapshot/label/candle reads and existing relevant indexes.
- Keep panels in memory unless measurement proves materialization necessary.
- Write only atomic ml-saham artifacts, never one DB row per fold/threshold.
- Run the upstream no-mutation tripwire around live smoke checks.

## 10. Testing Expectations

Each checkpoint must include independent happy-path and adversarial tests for
identity, cohort non-mixing, PIT cutoff, missing fields, non-finite values,
unsupported snapshots/adapters, insufficient folds/classes, deterministic
reproduction, CLI JSON/status, artifact round trip/atomicity, and upstream
read-only behavior.

New/changed extractors must use live-shaped goldens and the shipped extractor.
Required close commands for affected Python work:

```bash
./scripts/check_challenge_contracts.sh
python -m compileall -q src tests
pytest -q
git diff --check
```

If the full suite is deferred, record the exact reason and focused commands;
do not claim the checkpoint complete.

## 11. Acceptance Criteria

- [ ] C0 makes cohort/snapshot/session/fold/Action/readiness readiness explicit.
- [ ] C1 reports allowed and blocked books, false blocks, harmful allows,
      opportunity cost, attribution, and multi-fold stability.
- [ ] C2 ships hard-filter conformance plus a registered locked tournament.
- [ ] C3 remains blocked until ai-saham first establishes executable production
      behavior and then publishes its verified snapshot; configured dead code
      is never challenged as production.
- [ ] C4 cannot run before its Action/readiness data gate passes.
- [ ] No upstream writes/imports/scrapers, leakage, identity inference,
      curriculum authority, or auto-promotion.
- [ ] All relevant contract, focused, full CI, compile, and diff gates pass.
- [ ] Roadmap/product/data/CLI/artifact docs and completion record are updated.
- [ ] Unrelated shared-worktree changes are preserved.

## 12. Documentation Impact

Update as each checkpoint lands:

- `docs/challenge_product_roadmap.md`, `roadmap.md`, `problem_backlog.md`;
- `docs/challenge_product.md`, `docs/challenge_extract_contract.md`,
  `data_contract.md`;
- ADR-001/ADR-002 or a new ADR for new protocol/authority decisions;
- CLI help and artifact/protocol/policy documentation;
- the companion `ai-saham` task completion evidence for C0/C3/C4 gates.

## 13. Agent Execution Instructions

Before editing, read `AGENT_QUICKSTART.md`, `AGENTS.md`, this task, the challenge
product/extract/data contracts, relevant PolicySpecs/adapters/protocols/tests,
and the companion producer task. Restate invariants, exact files, composition
paths, selected semantic classifications, and the foundation checkpoint.

Stop if current code/data materially contradicts an identity, metric, or
population assumption. Do not silently weaken this contract.

## 14. Do Not Interpret This As

- Do not warn and continue after policy/provenance failure.
- Do not auto-select the largest or latest cohort.
- Do not use a static production mirror or current YAML fallback.
- Do not build test-only parsers instead of shipped extractors.
- Do not use random splits, global preprocessing, or single-fold WIN.
- Do not treat a high block rate alone as gate quality.
- Do not disable a safety gate because a challenger wins.
- Do not equate diagnostics or `PROMOTE_CANDIDATE` display with Action.
- Do not write `ai-saham` DB/YAML or auto-promote a result.

## 15. Completion Record

```text
Completed date:
Commits:
Checkpoint statuses C0-C4:
Selected cohort/policy/protocol/adapter identities:
Data/population/fold/class counts:
Artifact IDs:
Commands and outcomes:
Live read-only smoke/tripwire:
Known limitations/unrelated failures:
Downstream human decision status:
```
