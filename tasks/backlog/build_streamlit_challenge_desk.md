# Build the Streamlit Challenge Desk (Phases 0-4)

## 1. Metadata

```text
Title: Build the Streamlit Challenge Desk (Phases 0-4)
Status: READY
Type: feature
Priority: High
Primary owner: ml-saham
Semantic classifications: CLI_CONTRACT, NON_SEMANTIC; ARTIFACT_SCHEMA only in Phase 4
```

Source: objective Streamlit-versus-Textual product assessment on 2026-08-02.

Chosen decision: build a **local, single-user Streamlit Challenge Desk** as a
thin adapter over typed ml-saham application services. Implement this option
only. Do not substitute Textual, a notebook, a general FastAPI service, or a
React frontend inside this task.

Framework lock:

- Python 3.11+;
- optional dependency group `ui` with `streamlit>=1.43,<2`;
- launch through `ml-saham challenge desk`;
- bind to `127.0.0.1` by default;
- no remote hosting, authentication, or multi-user behavior;
- challenge-facing UI copy is English.

Phase progress:

| Phase | Deliverable | Initial state | May start when |
|---|---|---|---|
| 0 | ADR, application facade, dependency and launcher foundation | COMPLETED | Completed 2026-08-02 |
| 1A | Read-only Control Tower, cohort discovery, and Policy Catalog | COMPLETED | Completed 2026-08-02 |
| 1B | Typed cohort and Protocol readiness enrichment | DEFERRED_OPTIONAL | Not required for Phase 2+; enrich when C0 ships (`close_accum_challenge_decision_coverage_gaps.md`) |
| 2 | Explicit challenge setup and synchronous Result Inspector | COMPLETED | Completed 2026-08-02; no C0/1B dependency |
| 3 | Validated artifact history, comparison, and human-review handoff | COMPLETED | Completed 2026-08-02 |
| 4 | Durable local background jobs and operational hardening | READY_AFTER_MEASUREMENT | After Phase 3; only if measured runtimes justify jobs |

The task may be merged phase by phase. Each merge must update this table. The
task moves to `tasks/done/` only after Phase 4 is complete or an accepted ADR
explicitly removes Phase 4 after measured runtimes show it is unnecessary.

Sequencing guard: the shared worktree contains unrelated challenge, snapshot,
promotion, roadmap, and task changes. Inspect current status before every
phase, preserve all unrelated changes, and stage only files owned by that
phase. Do not use destructive cleanup.

## 2. Problem Statement

The shipped challenge product is command-driven. Operators must remember a
large CLI surface, manually carry exact compatibility IDs, read multiple text
reports, locate artifact directories, and mentally compare fold tables and
identity fields. This makes routine challenge management harder than the
underlying deterministic product needs to be.

Current executable behavior already provides PolicySpec tournaments, factor
validity, engine rollups, health reports, diagnostics, champion runs, immutable
artifacts, and promote packets. The missing product is a coherent visual
workbench over those capabilities, not another scorer or evaluator.

Relevant stale-document contradiction:

- `architecture.md` says “CLI is the product; no web/TUI in MVP”;
- `ux.md` and `docs/challenge_product.md` likewise describe CLI-only operation;
- those are valid descriptions of the shipped MVP, but they must be explicitly
  superseded by a new accepted UI ADR before Streamlit code lands.

The current blocked and inconclusive challenge outcomes are correct. The UI
must make their reasons more visible; it must never convert them to warnings or
success states.

## 3. Product Question And Null

This is product infrastructure, not a policy challenge.

```text
Product question: Can one operator discover, configure, run, inspect, reopen,
  and compare authoritative ml-saham challenges without memorizing CLI flags or
  losing identity and failure-state information?
H0 / comparison claim: Not applicable; the UI does not score market outcomes.
Decision type: product workflow / infrastructure
Human decision supported: which existing challenge result needs attention or
  a separately reviewed production-policy proposal.
What the result cannot authorize: a WIN, policy change, production Action,
  ai-saham write, or automatic promotion beyond existing challenge authority.
```

## 4. Desired Outcome And Phases

### Phase 0 - accepted architecture and thin application boundary

1. Add an accepted ADR that supersedes only the old “no UI in MVP” constraint.
   It must preserve challenge-first, read-only upstream access, deterministic
   challenge authority, English challenge copy, and human-only promotion.
2. Add `streamlit>=1.43,<2` under an optional `ui` dependency. Core CLI and
   headless challenge installation must continue to work without Streamlit.
3. Add `ml-saham challenge desk` as a launcher only. It:
   - gives the exact install hint `pip install -e ".[ui]"` when unavailable;
   - starts the packaged app with the current Python interpreter;
   - binds to `127.0.0.1` by default;
   - supports `--port` and `--no-browser`;
   - rejects non-loopback binding in this task;
   - propagates startup failure and process exit status;
   - never scrapes or executes challenge CLI output.
4. Introduce a typed `ChallengeWorkbenchService` (name may change only in the
   ADR) and immutable request/response DTOs in a non-UI module. Both Typer and
   Streamlit may call this application boundary; neither UI owns product rules.
5. Add an empty but tested Streamlit shell with navigation, page title,
   upstream DB path shown as read-only, artifact root, product-boundary banner,
   and a non-authoritative curriculum exclusion notice.

Phase 0 is foundation only. It must not expose fake placeholder metrics or a
partially functioning Run button.

### Phase 1A - read-only Control Tower, cohort discovery, and Policy Catalog

Ship these workspaces:

1. **Control Tower**
   - renders already shipped challenge health/result states through the
     application service;
   - displays `WIN`, `LOSE`, `INCONCLUSIVE`, `BLOCKED_DATA`, and
     `BLOCKED_POLICY` verbatim with text/icon plus color;
   - visually separates tuning, factor, champion, and diagnostic tracks;
   - labels diagnostics as display/promote-candidate only, never Action.
2. **Cohort Discovery**
   - lists purpose-family compatibility IDs without selecting one as authority;
   - shows only authoritative factual inventory already available through a
     typed application/data boundary, such as observation count, distinct
     economic sessions, and date range;
   - requires the user to select an exact compatibility ID before enabling an
     authoritative challenge action;
   - never defaults to largest/latest, including when only one cohort exists.
3. **Policy Catalog**
   - uses the same registry behind `challenge list`;
   - shows policy ID, decision type, protocol, supported baseline and
     challengers, adapter identity, and registry-owned support/unsupported
     reason; it does not claim cohort-specific readiness or eligibility;
   - does not create a parallel inventory or UI-only aliases.

Phase 1A does not claim producer handoff or Protocol readiness. When C0 has not
shipped, readiness-derived fields render an explicit typed `NOT_IMPLEMENTED`
or unavailable state and no readiness badge, eligible banner, estimated fold
count, or inferred blocker is shown. The UI must not replace C0 with direct SQL,
presentation logic, CLI scraping, or approximate readiness rules.
`NOT_IMPLEMENTED` is UI capability availability only; it is not a challenge
verdict, producer readiness status, or Protocol readiness status.

### Phase 1B - typed cohort and Protocol readiness enrichment

After C0 ships, enrich the Phase-1A workspaces with its authoritative typed
projections:

- producer handoff status and machine-readable reasons;
- snapshot completeness and corpus-label integrity under the producer contract;
- Protocol target availability, expected post-embargo fold depth, and support;
- Action/readiness coverage as descriptive evidence, never Action authority;
- the exact distinction between producer readiness and ml-saham Protocol
  readiness.

Phase 1B is **optional enrichment only**. It does not block Phase 2, 3, or 4.
Until C0 ships, readiness remains explicit `NOT_IMPLEMENTED` (not inferred).
C1–C4 in `close_accum_challenge_decision_coverage_gaps.md` unlock their own
challenge capabilities; they do not block already registered challenge
execution in the Desk.

### Phase 2 - explicit Run Challenge and Result Inspector

Phase 2 may start after Phase 1A. It exposes only challenges whose existing
registry, adapter, Protocol, baseline verification, and orchestration already
form an executable contract. A challenge that depends on unfinished C0-C4 work
remains absent or explicitly unavailable under an application-owned reason; the
UI never fills that product gap.

1. Add a challenge setup form with explicit fields:
   - purpose/scenario;
   - exact population identity or compatibility ID;
   - policy ID;
   - baseline (`production` or explicit `static_reference`);
   - supported challenger;
   - read-only Protocol identity and summary;
   - artifact root and write/no-write choice, defaulting to the existing
     product behavior.
2. Selector changes may refresh eligibility previews but may never start a
   challenge. Execution occurs only from one submitted, immutable request.
3. Stamp an application-owned request ID over every material request field.
   Streamlit reruns with the same submitted request must not execute it twice.
   A deliberate rerun requires an explicit **Run again** action and a new run
   attempt ID; it does not alter challenge identity rules.
4. Call existing runner/orchestration functions through
   `ChallengeWorkbenchService`; do not call Typer functions, shell out to
   `ml-saham challenge ...`, or parse Rich/text output.
5. Render a Result Inspector containing:
   - authoritative status and reasons;
   - primary metric and secondary horizons;
   - fold-by-fold table and minimum-fold rule;
   - baseline-versus-challenger comparison;
   - denominators, exclusions, missingness, and population range;
   - observation/population, production snapshot, policy, adapter, Protocol,
     baseline, challenger, artifact schema, and source identities;
   - artifact location and human-only next step.
6. `BLOCKED_*` and `INCONCLUSIVE` render as completed product states, not UI
   exceptions. Contract corruption and programmer errors render a safe error
   reference and remain distinct from those states.

Phase 2 is intentionally synchronous. Show elapsed time and progress states,
but do not invent percentage completion when the underlying operation cannot
report it.

### Phase 3 - artifact history, comparison, and human-review handoff

1. Add **Artifact History** backed by a canonical ml-saham artifact reader.
   The UI may not glob JSON and treat successful parsing as valid reopening.
2. Show historical artifacts as historical output. Unsupported schemas,
   missing `baseline_id`, incomplete population identity, or failed current
   production re-verification must not acquire promotion eligibility.
3. Add side-by-side comparison only when the service proves compatible policy,
   decision type, Protocol, population meaning, horizons, and metric semantics.
   Incompatible artifacts may be inspected separately but receive no computed
   delta or winner banner.
4. Add a **Create human review packet** action that invokes the existing
   promote-packet application path. Preserve its schema and live read-only
   production-identity verification. The action never edits ai-saham.
5. Provide downloads for existing validated JSON/Markdown files. Do not create
   a second export schema solely for Streamlit.

### Phase 4 - durable local jobs and operational hardening

Phase 4 begins only after Phase 3 records representative run duration and
memory measurements. If the ADR retains this phase:

1. Add an ml-saham-owned local job store under
   `<artifacts-root>/challenge/jobs/<job_id>/job.json`.
2. Lock operational schema `challenge_desk_job.v1` with:
   - `schema_version=1`, job ID, immutable request ID and request payload;
   - `QUEUED | RUNNING | SUCCEEDED | FAILED | CANCEL_REQUESTED | CANCELLED`;
   - created/started/finished timestamps;
   - worker PID or equivalent local execution identity;
   - artifact ID/path only after successful artifact commit;
   - typed failure category and sanitized detail.
3. Persist job records atomically with a temporary sibling and rename. A job
   record is operational metadata, never challenge evidence or promotion
   authority.
4. Execute application-service calls in an isolated local worker process. Do
   not store a live thread/future only in `st.session_state`.
5. Support refresh/reconnect, one active attempt per request, cancellation,
   stale-worker detection, and late-result protection. Cancellation must never
   turn a partial artifact into a successful pack.
6. Add responsive, accessibility, failure, packaging, and clean-install gates.

## 5. Non-Goals

- No ai-saham database write, migration, repair, vacuum, backfill, schema
  ensure, or persistent PRAGMA.
- No ai-saham Python import, scraper, provider, token, or network integration.
- No auto-promotion or direct write to ai-saham YAML/code/configuration.
- No production trading cockpit, screen/fetch/plan/Action workflow, or live
  signal operation.
- No curriculum dashboard in this task.
- No new scoring, folds, metrics, verdicts, readiness laws, policy aliases, or
  challenger definitions in UI code.
- No implicit largest/latest cohort or replacement population selection.
- No static production mirror fallback or historical artifact upgrade.
- No CLI-output scraping, `shell=True`, or UI-owned SQL.
- No remote bind, TLS, authentication, multi-user tenancy, shared job queue,
  FastAPI service, Redis, Celery, container platform, or cloud deployment.
- No custom JavaScript/Streamlit component in Phases 0-3.
- No replacement or deprecation of the CLI; the CLI remains the automation,
  scripting, recovery, and CI surface.

## 6. Authority And Boundary Assessment

```text
ai-saham-owned inputs: observations, candles/benchmark data, corpus labels,
  production policy snapshots, compatibility identities, Action/readiness fields
ml-saham-owned outputs: existing challenge results/artifacts/promote packets;
  Phase-4 operational job records only
Upstream DB access mode: SQLite URI read-only through existing data adapters
Any ml-saham-owned writes: existing artifact root; Phase-4 job records under it
Production behavior affected: No
Auto-promotion possible: No
External/network dependency: No; localhost HTTP serves the Streamlit UI only
```

Boundary plan:

- Data/read boundary: reuse named read-only repositories/projections; no UI SQL.
- Challenge contracts and orchestration: existing authority; add a typed
  application facade without changing outcomes.
- Evaluation/statistics: not changed and never recomputed by the UI.
- Artifacts: reuse authoritative writers/readers; add only the Phase-4
  operational job schema if retained.
- CLI: add the `challenge desk` launcher; existing challenge commands and JSON
  remain stable.
- Curriculum: not touched.
- UI: thin Streamlit adapter over typed DTOs; owns layout and interaction state
  only.

### Authority matrix

| Artifact/boundary | Authority owner/source | Identity/coverage shown | Missing state | Invalid/conflicting state | UI may act when |
|---|---|---|---|---|---|
| Policy catalog | `challenge.policies.registry` and supported adapters | exact policy, adapter and Protocol IDs | unavailable catalog | typed application error | service returns a valid catalog row |
| Cohort discovery | Existing typed application/data boundary over ai-saham read-only contracts | purpose, compatibility ID, factual population/date coverage only | unavailable inventory; no inferred readiness | typed contract error; never empty/ready fallback | user explicitly selects an exact identity; discovery alone grants no eligibility |
| Cohort/Protocol readiness | C0 application projection over ai-saham read-only contracts | producer handoff plus Protocol-specific label/snapshot/fold/support coverage | `NOT_IMPLEMENTED`/unavailable until C0 ships | `BLOCKED_DATA` or `BLOCKED_POLICY` reasons | C0 returns an authoritative typed projection for the exact selected identity |
| Production baseline | verified ai-saham snapshot consumer | snapshot ID/digest, policy/version/semantic contract, compatibility ID | `BLOCKED_POLICY` | `BLOCKED_POLICY` | current supported snapshot and adapter verify |
| Protocol | ml-saham Protocol registry | exact Protocol ID, horizons, embargo, folds, minimum N | unsupported | blocked before execution | registry resolves the selected policy contract |
| Challenge result | existing ml-saham runner/orchestrator | all result and population identities | typed blocked/inconclusive | safe application/programmer error | service returns a complete typed result |
| Artifact reopen | canonical ml-saham artifact reader plus current authority checks | schema, content, population and production bindings | historical/unavailable | fail closed; never promotion eligible | supported schema and required identities validate |
| Promote packet | existing promote application path | verified production baseline and current upstream identity | ineligible human review | blocked | existing promote contract accepts the artifact |
| UI job record | ml-saham Phase-4 job store | operational request/attempt identity only | no recorded job | FAILED/stale; never evidence | only to manage execution, never to grant verdict authority |

## 7. Data Contract

The UI introduces no independent upstream data contract. Every page consumes
typed service DTOs built by existing or separately accepted application/data
projections.

```text
Source owner/table/export: ai-saham-owned tables through existing ml-saham
  read-only adapters; ml-saham challenge/artifact registries and readers
Required columns/payload paths: exactly those named by each existing challenge,
  factual cohort-discovery boundary, C0 readiness when available, snapshot, and
  artifact contract; UI does not add SQL paths
Purpose and compatibility_id: explicit purpose-family identity; no implicit ID
Sample unit/grain: inherited and displayed from the selected challenge/Protocol
Population/denominator: inherited and displayed without UI recomputation
Economic date: inherited min/max and fold dates
Available-at/cutoff rule: inherited PIT contract
Missing vs unavailable vs unsupported behavior: preserved as distinct typed states
Units: inherited and labeled from result DTOs; no magnitude inference
Cardinality and dedupe key: inherited population keys; request attempt has its own ID
Legacy fallback: none
```

If a required UI field does not exist in an authoritative DTO, extend the
owning application/domain result deliberately and version a persisted schema
when material. Do not reconstruct the field from rendered text or a nearby
value.

## 8. Policy And Adapter Contract

```text
Production policy_id/version: selected exact catalog identity
Snapshot contract/id/digest: verified by existing snapshot consumer
Selected compatibility_id: explicit user selection for purpose-family cohorts
Challenge adapter id/version: existing supported adapter
Supported semantic contracts: existing registry/snapshot contract only
Baseline fields: production or explicit static_reference; never silently remapped
Challenger ids and definitions: existing registry for selected policy only
Missing/mismatch status: BLOCKED_POLICY
Golden conformance vectors: existing policy-specific gates remain mandatory
```

The UI must render but never manufacture these identities.

## 9. Protocol And Leakage Contract

No Protocol behavior changes are authorized. The setup page renders a
read-only summary of the exact existing Protocol. Universe/population, target,
benchmark, horizons, costs, fold construction, embargo, train-only fitting,
minimum N/folds, metrics, verdict law, multiplicity rule, and seeds remain
owned by the selected Protocol and challenger implementation.

Changing any of those during UI work requires stopping this task and creating
a separately reviewed semantic task with the correct version bump.

## 10. Failure And Exception Contract

- Missing DB/path/table/column: typed unavailable/error state; never empty zero.
- Empty selected cohort: `BLOCKED_DATA` or the existing exact state.
- Missing/mixed/wrong cohort: `BLOCKED_POLICY` or existing family guard; never
  auto-select a replacement.
- Malformed JSON/non-finite numeric: contract error, not a blank chart.
- Missing/invalid snapshot or unsupported adapter: `BLOCKED_POLICY`.
- Horizon unavailable or insufficient N/folds: existing
  `BLOCKED_DATA`/`INCONCLUSIVE` behavior.
- Artifact write failure: run is not presented as successfully persisted; show
  the exact typed application failure.
- Unsupported/historical artifact: display-only when safely readable, never
  silently upgraded or promotion eligible.
- Streamlit rerun: does not duplicate a submitted challenge.
- Worker/job failure: Phase-4 job becomes `FAILED`; no success artifact link.
- Programmer/invariant error: sanitized UI error with correlation/reference
  ID, complete server-side traceback for local operator diagnostics, and no
  conversion to a product verdict.

No broad `except Exception` may turn corruption into an empty table or blocked
market-data state. A top-level presentation catch may sanitize the page only
after preserving the application error category and diagnostic traceback.

## 11. Artifact And Output Contract

```text
Challenge artifact schema/version: unchanged; current writer/reader authority
Artifact ID inputs: unchanged existing challenge identity dimensions
Required identity fields: cohort/population, snapshot, policy, adapter,
  Protocol, baseline, challenger, source and artifact schema identities
Data range/population counts: rendered from authoritative result/artifact
Fold/metric tables: rendered, not recalculated
Human checklist language: English
CLI/JSON/Markdown outputs: unchanged
Reopen behavior: supported current artifacts validate; historical artifacts
  remain historical/display-only; invalid artifacts fail closed
Atomic/immutable write behavior: existing artifact rules; Phase-4 job record
  uses atomic replace and cannot modify challenge artifacts
```

Streamlit download responses are transports for existing validated files, not
new authoritative exports.

## 12. Storage And Performance

- Keep Phase-1A factual/catalog queries and Phase-1B readiness queries bounded,
  and cache only immutable or explicitly TTL-scoped DTOs. Cache keys must
  include DB path/identity and all material selection fields.
- Never cache a verified production-policy conclusion across a changed DB
  authority identity without revalidation.
- Phase-2 panels may remain in memory as existing runners define; the UI must
  not materialize them into ai-saham SQLite.
- Record Phase-2/3 elapsed time and peak-process memory for representative
  health, single-policy, factor, and engine runs before Phase 4.
- Phase-4 job growth is under the ml-saham artifact root. Retention is manual in
  v1; the UI may list old jobs but must not delete artifacts.
- Every upstream-read integration test uses a no-mutation tripwire over relevant
  file metadata and SQLite schema/page/count state.

## 13. Testing Expectations

### Phase 0

- ADR/doc link validation and stale CLI-only prose superseded coherently.
- Core install/import works without Streamlit.
- UI extra imports successfully with the locked supported range.
- launcher missing-extra hint, loopback default, non-loopback rejection,
  argument forwarding, and child exit propagation.
- architecture guard: `src/ml_saham/ui/` does not import `sqlite3`, data adapter
  implementations, Typer command functions, scorers, metrics, panels, or
  ai-saham modules.
- Streamlit `AppTest` shell smoke.

### Phase 1A

- AppTest navigation and page rendering for shipped health/result states,
  factual cohort inventory, malformed contracts, and unavailable inventory.
- No cohort preselection; Run action disabled until explicit selection.
- catalog equality test against the canonical service/registry.
- diagnostic status is textually separated from Action/tune authority.
- absent C0 renders no inferred readiness, eligibility, fold estimate, or
  blocker; readiness fields are explicitly unavailable.
- read-only upstream tripwire.

### Phase 1B

- AppTest rendering for producer handoff and Protocol readiness states,
  including blocked-policy, blocked-data, collecting/inconclusive-depth, ready,
  malformed, and unavailable fixtures.
- producer and Protocol readiness remain separate typed fields and vocabularies.
- UI values equal the authoritative C0 DTO without presentation recomputation.
- read-only upstream tripwire.

### Phase 2

- form-to-request mapping mutation tests for every material identity/option.
- duplicate Streamlit rerun cannot execute the same attempt twice.
- explicit Run-again creates a new attempt without changing product identity.
- result tables equal authoritative service DTO values, including folds,
  missingness, denominators, and all identities.
- blocked/inconclusive paths are ordinary rendered states; corruption is not.
- representative real CLI and UI calls over the same fixture yield equivalent
  typed result/export fields.

### Phase 3

- artifact round trip, immutable content, unsupported schema, missing and empty
  `baseline_id`, population mismatch, snapshot mismatch, and historical-only
  behavior.
- compatible comparison succeeds; each incompatible identity axis disables
  computed deltas.
- promote packet uses the existing validator and read-only current-authority
  check; no UI bypass.
- downloads reproduce exact validated bytes.

### Phase 4

- job state transition table, atomicity, process crash, stale PID, cancellation,
  late success after cancellation, duplicate attempt, reconnect, and restart.
- partial/cancelled work cannot expose a success artifact.
- responsive browser tests at 1280x720 and 1440x900, plus a 390px narrow state
  with usable stacked controls and no hidden blocker text.
- keyboard navigation, visible focus, semantic labels, text/icon-plus-color
  status, and light/dark theme checks.
- clean wheel/install test with `[ui]` and without `[ui]`.

Per Python phase, run at minimum:

```bash
python -m compileall -q src tests
pytest -q <phase-focused-test-files>
pytest -q
git diff --check
```

Run `./scripts/check_challenge_contracts.sh` whenever an application-service
extraction touches challenge composition or product output, even if metrics are
intended to remain unchanged. Run the applicable current CI commands from
`.github/workflows/ci.yml`. Ruff is not a gate until the separate Ruff
foundation described in `AGENT_QUICKSTART.md` lands.

## 14. Acceptance Criteria

### Phase 0

- [x] Accepted ADR locks Streamlit, localhost/single-user scope, thin-adapter
      boundaries, phase plan, and superseded MVP prose.
- [x] Optional UI dependency does not burden core/headless installs.
- [x] `ml-saham challenge desk` starts the packaged app on loopback and fails
      clearly when the UI extra is missing.
- [x] Typed application facade exists; UI contains no product decisions.
- [x] Shell AppTest and launcher/architecture tests pass.

### Phase 1A

- [x] Control Tower, cohort discovery, and Policy Catalog render authoritative
      existing DTOs without claiming C0 readiness.
- [x] Exact compatibility identity is explicit and never preselected.
- [x] Shipped blocked/inconclusive results remain visible and machine-consistent.
- [x] Missing C0 produces explicit unavailable readiness fields, not inferred
      readiness, eligibility, fold counts, or blocker reasons.
- [x] No parallel policy inventory exists.
- [x] Phase 1A locks: historical tower only; no Run; ACCUM+PRE_OPEN inventory;
      sessions/date_range/readiness = `NOT_IMPLEMENTED`.

### Phase 1B

- [ ] C0 producer-handoff and Protocol-readiness DTOs render without UI
      recomputation and remain visibly separate.
- [ ] All readiness blocker reasons remain visible and machine-consistent.
- [ ] No UI readiness computation exists.

### Phase 2

- [x] One explicit immutable request launches a challenge exactly once.
- [x] Result Inspector exposes folds, denominators, missingness, and every
      authority identity needed to understand the verdict.
- [x] UI and CLI results share `run_policy_challenge` over deterministic fixtures.
- [x] No selector change, page rerun, or browser refresh silently starts work.
- [x] Phase 1B deferred optional; readiness remains NOT_IMPLEMENTED.
- [x] Verb scope v1: policy_run only (factor/engine/champion/health stay CLI).

### Phase 3

- [x] Artifact history reopens only through authoritative validation.
- [x] Historical/incompatible artifacts never gain current eligibility or a
      computed cross-contract winner.
- [x] Human review packet reuses the existing promote path and never writes
      ai-saham.
- [x] Exact-byte downloads of validated pack files only.

### Phase 4

- [ ] Durable jobs survive Streamlit reruns/reconnects and handle cancellation,
      failure, stale workers, and late results without false success.
- [ ] Responsive/accessibility/package acceptance is automated and green.

### Global

- [ ] No upstream writes/imports/scrapers/network integrations were added.
- [ ] No leakage, identity inference, static fallback, or cohort mixing exists.
- [ ] No curriculum output grants challenge authority.
- [ ] No auto-promotion or production behavior change is possible.
- [ ] Challenge artifacts and existing CLI/JSON contracts are unchanged unless
      a separately accepted versioned task authorizes a change.
- [ ] Focused tests, applicable contract gates, full relevant CI, and full
      `pytest -q` pass for every phase.
- [ ] `python -m compileall -q src tests` and `git diff --check` pass.
- [ ] Docs, phase table, and completion record are updated after each merge.
- [ ] Upstream SQLite and unrelated worktree changes are proven untouched.

## 15. Documentation Impact

Phase 0 must update:

- add a new UI ADR and link it from `docs/adr/README.md`;
- `architecture.md` to show CLI and Streamlit as peer adapters over one service;
- `ux.md` to define the Challenge Desk and retain CLI automation/recovery;
- `README.md` and `docs/challenge_product.md` with install/launch/operator flow;
- `AGENT_QUICKSTART.md`, `AGENTS.md`, `DEFINITION_OF_DONE.md`, and
  `AI_AGENT_CHECKLIST.md` only where UI-specific mandatory gates/boundaries must
  become durable agent law;
- `pyproject.toml` for the optional dependency and launcher behavior.

Later phases update `docs/challenge_health.md` and artifact/operator docs when
their corresponding UI paths ship. `BOUNDARY.md` and `data_contract.md` change
only if wording is needed to document the new consumer; no ownership or schema
change is authorized. No ai-saham companion task is required because this UI
does not change its producer contract or state.

## 16. Agent Execution Instructions

Before each phase, the implementer must:

1. read `AGENT_QUICKSTART.md`, `AGENTS.md`, this task, and the reading-matrix
   sources selected for that phase;
2. inspect current code/tests, recent relevant commits, and shared-worktree
   status before editing;
3. restate that this is an offline challenge lab, ai-saham owns upstream state,
   the UI is a thin adapter, results are deterministic human decision support,
   and no auto-promotion is possible;
4. state semantic classifications, stale-contract findings, assumptions, exact
   files, composition roots, and the mandatory boundary plan;
5. complete the prior phase foundation and focused tests before broad UI work;
6. define every DTO and identity field before rendering it;
7. stop if implementation would require UI SQL, a new verdict/readiness rule,
   an upstream write, an inferred production identity, a weakened block, a new
   artifact meaning, or a remote-service architecture.

## 17. Do Not Interpret This As

- permission to wrap each Typer command in a subprocess and scrape its output;
- permission to move scoring, chart aggregation, readiness, or verdict logic
  into Streamlit pages;
- permission to preselect the largest/latest/only cohort for convenience;
- permission to call a static fixture “production” when snapshot verification
  fails;
- permission to render `BLOCKED_*` as a warning while enabling promotion;
- permission to parse raw artifacts without schema and identity validation;
- permission to compare metrics across incompatible Protocols or populations;
- permission to let browser refresh execute a challenge again;
- permission to use `st.session_state` as the sole durable job queue;
- permission to import ai-saham, mutate its DB/config, fetch provider data, or
  create a trading cockpit;
- permission to auto-promote a WIN or diagnostic `PROMOTE_CANDIDATE`;
- permission to delete or rewrite unrelated shared-worktree changes.

## 18. Completion Record

```text
Phase 0 completed date/commit: 2026-08-02 / working tree (phase-0 shell)
Phase 1A completed date/commit: 2026-08-02 / desk phase 0+1A commit
Phase 1B completed date/commit: DEFERRED_OPTIONAL (not required)
Phase 2 completed date/commit: 2026-08-02 / 6b81e97
Phase 3 completed date/commit: 2026-08-02 / (this implementation)
Phase 4 completed date/commit or accepted removal ADR:
Selected UI/Streamlit version: streamlit>=1.43,<2; verified with 1.60.0
Application facade and DTO contracts: ChallengeWorkbenchService + Phase-1A
  PolicyCatalogRow, CohortInventory*, HistoricalResultRow, ControlTowerSnapshot,
  DiagnosticCatalogRow, CapabilityField (NOT_IMPLEMENTED readiness)
Selected cohort/policy/protocol/adapter identities used in acceptance:
  fixture ACCUM sha256:aaa/bbb + PRE_OPEN sha256:pre1; catalog == list_policies()
Data/population/fold counts used in acceptance:
  factual observation_count only; sessions/date_range NOT_IMPLEMENTED
Artifact/job schema identities: historical manifests only; no Phase-4 job schema
Commands and outcomes: Phase-0+1A desk tests 22 passed with [ui]; compileall ok
Live read-only smoke/tripwire: service methods do not create missing DB paths
Representative duration/memory measurements:
Known limitations: AppTest requires optional [ui]; curriculum phase demos may
  still fail without ml extras (unrelated)
Downstream human decision status:
```

## Final Readiness Gate

Phases 0, 1A, 2, and 3 are complete. Phase 1B remains deferred optional. Phase
4 starts only after measured runtimes justify durable jobs. Unfinished C0–C4
capabilities remain unavailable rather than being recreated in the UI.

### Phase 1A implementation locks (applied)

1. Control Tower = validated historical packs only (including health index
   expansion); no live challenge execution.
2. Cohort inventory fields = purpose family, compatibility_id, observation
   count, max_captured_at; sessions/date_range/readiness = `NOT_IMPLEMENTED`.
3. Policy Catalog DTO from registry/adapters only; readiness `NOT_IMPLEMENTED`.
4. No Run control in Phase 1A.
5. Cohort discovery families = ACCUM + PRE_OPEN only.
6. Path selection = launch-time / env only.
