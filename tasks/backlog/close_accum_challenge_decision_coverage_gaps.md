# Close Accum Challenge Decision-Coverage Gaps (G0-G4)

Status: `READY_FOR_PHASED_EXECUTION`

Source: code-first product-gap audit on 2026-07-31, rebased against current
executable code, focused tests, and read-only maintainer-DB evidence on
2026-08-02.

Companion producer task:

- `~/dev/ai-saham/tasks/backlog/grow_snapshot_bound_accum_challenge_corpus.md`

External C3 authority task:

- `~/dev/ai-saham/tasks/backlog/decide_accum_group_breadth_production_authority.md`

## 0. Rebase Lock And Checkpoint Availability (2026-08-02)

This program remains directionally correct, but checkpoints do not share one
blanket readiness state:

| Checkpoint | Current availability |
|---|---|
| C0 | Contract locked below. Implementation waits for the companion producer task to refresh and close its current code-hardening gate; do not bind to stale producer output. |
| C1 | Ready for protocol/metric implementation and deterministic fixtures. A confirmatory live result still requires multi-session depth. |
| C2 | Replay extraction, live-shaped goldens, and cohort-bound production adapter conformance are shipped. The locked tournament remains open and may build on C1. |
| C3 | Resolved externally by ai-saham ADR-062: the dormant score bonus is retired. No production PolicySpec or challenge implementation is authorized. |
| C4 | Data-blocked. Do not implement the Action verdict while per-fold ENTER/readiness support remains insufficient. |

The C0 projection has two independent axes and must never collapse them into
one inferred status:

1. **Producer handoff status** reports ai-saham observation, population,
   snapshot, and corpus-label authority using the producer vocabulary.
2. **Protocol readiness status** reports ml-saham's named Protocol inputs,
   candle/benchmark outcome coverage, folds, and decision-specific support.

`CHALLENGE_INPUT_READY` is not `READY_FOR_PROTOCOL`, and malformed or missing
ai-saham corpus labels do not become the outcome gate for `accum_path_v1`, whose
target is independently built from candles plus IHSG. A future Protocol that
explicitly names `label_source=corpus` may make those labels authoritative for
that Protocol only.

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
  - C3 configured group breadth: resolved as retired production policy
    (ADR-062) with ai-saham clean-removal of residual config/applier/transport;
    documentation-only close, with no challenge PolicySpec or baseline
  - C4 Action/readiness: `DATA_CONTRACT`, `PROTOCOL_CONTRACT`,
    `VERDICT_SEMANTICS`, `ARTIFACT_SCHEMA`
- This task-file revision is documentation-only and `NON_SEMANTIC`.
- Chosen decision: implement the checkpoints in order and stop at each explicit
  gate. Extend the existing `challenge health`, `challenge run`, `challenge
  engine`, and `vet` product surfaces; do not create a disconnected evaluator.
  Implement this option only.

Sequencing guard: snapshot/cohort/promotion hardening has continued in both
repositories. The current companion task still records an in-progress code
gate; C0 implementation must recheck that completion record and current
producer DTO before coding. C1 and C2 contract/conformance work may proceed in
parallel, but confirmatory verdicts remain data-dependent. Preserve the
unrelated Streamlit/Challenge Desk work in this repository and all unrelated
ai-saham worktree changes.

## 2. Problem Statement

The challenge lab has useful sleeve, signal, risk, factor, diagnostic, and
promotion-support paths, but it does not yet cover every material production
decision influence.

Current executable/data evidence, refreshed 2026-08-02:

- cohort `sha256:005363...` has 1,890 observations over 42 sessions and no
  required v2 policy snapshots. It remains ineligible for an active production
  comparison. Current strict producer readiness also reports historical corpus
  labels that fail the new calendar-bound label contract; never retrofit either
  snapshots or labels;
- cohort `sha256:58988d...` has 349 observations from one session and only a
  historical v1 snapshot set, so it remains `LEGACY_RAW_ONLY` producer history
  and ineligible for current production comparison;
- cohort `sha256:8ba8fc...` has 304 observations, one session, and all seven v2
  snapshots. Current ml-saham candle-based execution yields only one OOS fold:
  `screener.accum.score_weights` is `INCONCLUSIVE`; the `gate_off` risk
  challenger is `LOSE` because its allowed-book mean is worse than production;
  the hard-filter policy is `BLOCKED_POLICY` because its adapter lacks
  production conformance authority. Do not summarize these distinct states as
  "production verdicts remain INCONCLUSIVE";
- on that slice, risk gates block about 83% OOS and the production allowed book
  is better than `gate_off`, while the score tournament remains inconclusive;
- risk output does not quantify false-block cost, harmful allows, gate-family
  contribution, or multi-regime stability;
- screen hard-filter extraction, pure first-match replay, live-shaped goldens,
  and v2 identity exist. The challenge adapter still has an empty production
  `conformance_id`, supports no counterfactual challenger, and is not registered
  in the screener engine portfolio;
- sector/group breadth remains as dormant ai-saham removal debt, but ADR-062
  retires the score bonus from production policy. No production challenge
  baseline exists, and ml-saham must not reconstruct one from residual fields;
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

### C3 configured group breadth (closed: retired upstream)

```text
Product question: none; ai-saham ADR-062 retires the configured score bonus.
H0 / comparison claim: none; there is no production behavior to challenge.
Decision type: no production policy
Human decision supported: none.
What the result cannot authorize: treating configured or isolated-test behavior
  as a production baseline, or reconstructing a challenger from residual fields.
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

Extend the typed challenge/workbench application boundary used by `vet`,
`challenge health`, and the optional Challenge Desk so a selected ACCUM cohort
reports, in table and JSON/artifact form. UI/CLI adapters must not query SQLite,
scrape another command, or compute readiness.

### C0A - producer handoff projection

Report the upstream producer facts without recreating ai-saham policy:

The projection independently validates authoritative SQLite rows through the
existing read-only data boundary under the locked cross-repo contract. It must
not import ai-saham Python, invoke/scrape the ai-saham CLI, trust a persisted
status string, or make ai-saham write a second handoff artifact merely for this
UI/report.

- exact `compatibility_id`; never implicit largest/latest selection;
- observation count, distinct session count, min/max economic date;
- required snapshot contract, verified policy IDs, and `7/7` completeness;
- corpus-label availability/integrity by H3/H10/H20, explicitly labeled as
  ai-saham producer labels rather than `accum_path_v1` targets;
- Action distribution and readiness present/missing counts;
- upstream producer status: `LEGACY_RAW_ONLY`, `BLOCKED_POLICY`, `COLLECTING`,
  or `CHALLENGE_INPUT_READY`, plus exact machine-readable reasons;
- ml interpretation mapping, without converting producer readiness into a
  verdict or fold claim.

### C0B - ml-saham Protocol readiness projection

For one explicitly selected PolicySpec/Protocol combination, report:

- verified production snapshot and supported adapter identity;
- Protocol ID, target source, benchmark, primary/secondary horizons, embargo,
  minimum N, and minimum folds for WIN;
- candle/IHSG target availability and exclusions under that Protocol;
- protocol-estimated post-embargo valid fold count;
- explicit status: `BLOCKED_POLICY`, `BLOCKED_DATA`, `READY_FOR_PROTOCOL`, or
  `INCONCLUSIVE_DEPTH` with machine-readable reasons.

The C0A and C0B statuses must be separate fields in JSON/artifacts. The report
is read-only and does not itself produce a challenge verdict. Producer corpus
label availability may gate C0B only when the selected Protocol explicitly
declares the corpus label source.

### C1 - deepen risk-gate decision quality (first scoring deliverable)

Implementation status (2026-08-11): the measurement-only
`gate_decision_quality.v1` report is shipped in the working implementation. It
adds fold-wise and pooled H3/H10/H20 allowed/blocked books, false blocks,
harmful allows, opportunity cost, and authoritative audit-order first/overlap
attribution. It deliberately does not change WIN/LOSE. C1 remains open until a
separately vetted versioned gate verdict law locks material improvement,
per-side support, safety regression, fold agreement, and named-gate
multiplicity before confirmatory outcome inspection.

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

Implementation status (2026-08-11): adapter v2 production conformance is
shipped. Its immutable vectors are observed from ai-saham's real deterministic
core-probe screen path, cover pass plus all four first-match gates, and produce
a content-derived `conformance_id`. Policy composition additionally binds that
producer behavioral digest to the selected snapshot-set digest and observation
schema version through the ADR-068 compatibility formula. A different cohort
therefore remains `BLOCKED_POLICY`. The tournament is still open: no challenger
grid, multiplicity/support/safety law, or PolicySpec registration has landed.

Use only verified `screener.accum.hard_filters` v2 cohort snapshots and the
shipped first-match replay. Existing foundation, already complete:

- live-shaped extraction/replay golden vectors cover market-cap, Piotroski,
  Accum-score, and Signal-score filters, missing states, and first-match order;
- shipped pure replay and cohort reconciliation fail closed on unsupported
  payloads and do not multiply sample N by feature window.

Remaining before engine registration:

- [x] establish a non-empty versioned production adapter `conformance_id` by
  proving the adapter/replay reproduces producer-observed frozen results and
  binding that evidence to the exact behavioral cohort;
- predeclare the off/threshold grid, population denominator, H10 target,
  multiplicity law, minimum per-side support, and verdict rule;
- emit the C1 decision-quality metrics, including rejected/control populations;
- register the PolicySpec only after conformance and protocol tests pass.

Snapshot absence/mismatch, unsupported semantics, missing control population,
or inadequate folds returns `BLOCKED_POLICY`/`BLOCKED_DATA`; never approximate.

### C3 - closed without a challenge

ai-saham ADR-062 retires the dormant group-breadth score bonus. C3 therefore
ships no PolicySpec, adapter, challenger, snapshot expectation, or verdict.
Residual configuration, observation fields, and isolated applier behavior are
not a production baseline and must never be reconstructed here.

A future PIT-governed group/sector diagnostic would be a new producer contract,
not a continuation of C3. ml-saham may challenge that diagnostic only after
ai-saham publishes its exact provenance contract; it remains non-authoritative
unless a later explicit production-promotion decision exists.

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
  typed setup_readiness fields; no retired group-breadth reconstruction
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

Label-source separation is normative:

| Readiness fact | Authority | May gate |
|---|---|---|
| Corpus label availability/integrity | ai-saham `learning_outcome_labels` producer contract | C0A producer handoff; C0B only for a Protocol that explicitly names `label_source=corpus` |
| `accum_path_v1` H3/H10/H20 excess | ml-saham Protocol over read-only candles + IHSG | C0B and C1/C2 challenge folds |

Do not infer one from the other or use a producer status as a substitute for
Protocol extraction.

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

- [ ] C0 reports producer handoff and Protocol readiness as two separate typed
      axes with explicit label sources and no inferred status conversion.
- [ ] C1 reports allowed and blocked books, false blocks, harmful allows,
      opportunity cost, attribution, and multi-fold stability.
- [x] C2 foundation has live-shaped extract/replay goldens and shipped pure
      first-match replay.
- [x] C2 establishes cohort-bound production adapter conformance authority.
- [ ] C2 registers the locked challenger grid, Protocol, and tournament.
- [x] C3 is closed without a challenge under ai-saham ADR-062; configured dead
      code is never challenged or reconstructed as production.
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
- the companion `ai-saham` task completion evidence for C0/C4 gates and the
  accepted ADR-062 close for C3.

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
