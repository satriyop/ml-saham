# Consume Verified `ai-saham` Production Policy Snapshots

Status: `DONE_WITH_PRE_EXISTING_REPOSITORY_GATE_FAILURES`

Source: code-first re-vet of ADR-002 section 3.1 on 2026-07-31.
Retargeted 2026-07-31 to **snapshot v2 / seven rows** per locked clarifications
on the companion activation task (do not merge a v1-only consumer).

Companion producer tasks:

- historical v1 producer (done):
  `~/dev/ai-saham/tasks/done/export_verified_policy_snapshot_for_ml_challenges.md`
- completed cohort activation (v2 + hard filters):
  `~/dev/ai-saham/tasks/backlog/activate_screen_hard_filter_tournament_cohort.md`

Primary owner of this task: **`ml-saham`** — read-only verification, challenge
binding, counterfactual adapter conformance, and challenge artifact provenance.

Upstream owner: **`ai-saham`** — sole production-policy snapshot and shared
SQLite writer.

## 1. Task Metadata

- Task type: Feature / clean-break consumer migration
- Priority: High
- Semantic classification: `NON_SEMANTIC` for `ai-saham` production decisions.
  This changes which offline challenges are eligible to claim
  `baseline=production`; it does not change live SignalEngine, RiskEngine,
  TradeSetup, configuration, or Action.
- Required upstream contract for **active production eligibility**:
  `production_policy_snapshot.v2` (exactly seven rows).
- Historical `production_policy_snapshot.v1` (six rows) may be parsed/displayed
  only as **explicitly non-eligible** for current `baseline=production`.
  **No v1 fallback** for active production challenges.
- Chosen decision: replace handwritten packaged production mirrors with the
  exact closed **seven-row** accumulation snapshot set defined below, read from
  `ai-saham` SQLite. Keep ML panel extraction and counterfactual scoring in a
  separate, versioned challenge adapter. Implement this option only.
- Hard-filter replay adapter/conformance remains a **downstream** tournament
  slice after this consumer lands verified snapshot binding.

## 2. Problem Statement

Current `PolicySnapshot` objects are loaded from packaged JSON under
`src/ml_saham/challenge/policies/`. Their declared hashes are trusted strings,
not recomputed content identities. They are not bound to the selected
`learning_observations.compatibility_id` and mix two authorities:

1. production-policy identity and material parameters owned by `ai-saham`;
2. panel extraction, aliases, scorer dispatch, and challenge protocol wiring
   owned by `ml-saham`.

Therefore a challenge can report `baseline=production` while evaluating a
manually maintained mirror that may differ from the production policy that
created the selected corpus cohort.

This is particularly unsafe for counterfactual questions such as reweighting,
dropping a factor, disabling flags, shifting classification thresholds, or
turning off gates. Those questions require both a verified production policy
definition and proof that the local counterfactual adapter reproduces its
declared semantic contract.

## 3. Desired Outcome

- Challenge preparation selects exactly one accumulation compatibility cohort.
- Every production policy required by the selected challenge is loaded from
  `ai-saham`'s `learning_policy_snapshots` table for that exact cohort.
- Canonical JSON SHA-256, artifact contract, decision type, observation
  contract, compatibility ID, policy ID, and semantic engine contract are
  validated before panel/scoring work begins.
- Missing, malformed, mismatched, unsupported, or unverifiable snapshots return
  `BLOCKED_POLICY`, not `BLOCKED_DATA`, and never fall back to packaged mirrors.
- Frozen production scores/actions stored in observations are used as the
  baseline when the question does not require recomputation.
- Counterfactual calculations use a separate `ChallengePolicyAdapter` whose
  version and conformance evidence are recorded.
- Every result/artifact identifies the observation cohort, verified upstream
  policy snapshot, local adapter, and protocol independently.
- ADR-002 section 3.1 describes the implemented separation truthfully.

## 4. Non-Goals

- No writes to the `ai-saham` database or production YAML.
- No imports from the `ai-saham` Python package.
- No scrapers, providers, network fetch, or snapshot repair in this repository.
- No automatic production promotion or configuration patch after WIN.
- No inference or reconstruction of snapshots for historical cohorts that do
  not contain them.
- No fallback to packaged JSON, documented constant maps, today's config, or a
  different compatibility cohort.
- No pre-open or swing consumer migration in this slice.
- No inclusion of diagnostic-only MCE, sector, institutional, or
  company-quality bags as production policy.
- No change to challenge Protocol horizons, folds, labels, embargo, or minimum
  N except where necessary to carry separate identities in artifacts.
- No fix for the nested risk/diagnostic payload extractors in this task; those
  remain separate correctness work and must not be hidden by this migration.

## 5. Hard Invariants

1. Shared `ai-saham` SQLite is opened read-only.
2. Cohorts are never mixed. Snapshot lookup uses the already selected
   observation `compatibility_id`.
3. Snapshot digest is recomputed from canonical payload bytes; the stored digest
   is never trusted without verification.
4. Unsupported schema or semantic contract fails closed.
5. Production snapshot and challenge adapter are different typed objects.
6. `panel_kind`, payload extraction aliases, scorer dispatch, challenger
   definitions, folds, and metrics never enter the upstream production
   snapshot.
7. Production material parameters and missing-data/availability rules are never
   sourced from an ML adapter.
8. `baseline=production` is forbidden unless the required upstream snapshot is
   verified for the selected cohort.
9. Counterfactual reproduction is forbidden unless the adapter supports the
   snapshot's semantic contract and has golden-vector conformance coverage.
10. No challenge result can directly change production behavior.
11. All **seven** active v2 rows must have one identical `compatibility_id`,
    `material_config_hash`, purpose, observation-contract binding, and
    `contract_id = production_policy_snapshot.v2`.
12. Snapshot digests are projections of the existing cohort identity, not
    inputs folded back into it. `ml-saham` validates the stored binding and
    producer artifact; it does not recompute a cohort from today's config.
13. Canonical payload verification uses the exact byte contract below; parsing
    JSON and hashing a differently formatted serialization is forbidden.
14. Active production eligibility requires snapshot **v2**; historical v1 rows
    never rescue a missing/incomplete v2 set.

## 6. Architecture Impact Assessment

- New dependency: No.
- Affects determinism: No production effect; challenge eligibility becomes
  deterministic and stricter.
- Persistence change: No. This repository reads the new upstream table and
  continues writing only its own artifacts.
- Warm-up data: No.
- Policy/orchestration in CLI adapter: No.

```md
Layer plan:
- Domain/types: split verified ProductionPolicySnapshot identity/parameters
  from ML-owned ChallengePolicyAdapter metadata.
- Challenge application: resolve required snapshots after cohort selection;
  validate contracts/digests; gate execution with BLOCKED_POLICY; bind snapshot
  and adapter identities into results.
- Data/infrastructure: read-only ai-saham snapshot-table reader; no writes and no
  producer-policy interpretation.
- Adapter/CLI: render BLOCKED_POLICY and provenance fields only; no fallback or
  snapshot assembly.
```

## 7. AI Usage Declaration

No AI involved. Snapshot verification, adapter dispatch, challenge gating, and
artifact identity are deterministic and offline.

## 8. Authority Considerations

- Production policy authority remains entirely in `ai-saham`.
- This repository owns offline challenge evaluation, not live scoring.
- A challenge WIN remains human decision support only.
- Diagnostic verdicts remain display/promote-candidate decisions and never
  become Action authority through this task.
- `BLOCKED_POLICY` means the production comparison cannot be established;
  callers must not downgrade it to a warning or run an approximate baseline.

## 9. Required Type Separation

Replace the current overloaded shape conceptually with two objects.

### Closed active policy set (`production_policy_snapshot.v2`)

Active production challenges require exactly these **seven** rows for a verified
accumulation cohort. A missing required row is `BLOCKED_POLICY`. Unknown extra
policy IDs are ignored for v2 and must not be selected without a contract
amendment. Historical six-row v1 sets are **not** sufficient for
`baseline=production`.

| Exact `policy_id` | `decision_type` | Policy version | Consumer behavior |
|---|---|---|---|
| `screener.accum.score_weights` | `score` | existing `v1` | Component-score production identity and counterfactual adapter |
| `signal.accum.evidence_group_weights` | `score` | existing `v1` | Evidence-group production identity and counterfactual adapter |
| `signal.accum.flags` | `score` | existing `v1` | Flag production identity and counterfactual adapter |
| `signal.accum.classification` | `score` | existing `v1` | Classification-threshold production identity and counterfactual adapter |
| `risk.accum.hard_gates` | `gate` | existing `v1` | Gate production identity and named gate-off adapter |
| `signal.accum.raw_score` | `score` | existing `v1` | Identity-only; baseline reads frozen observation output, never reconstructs raw scoring |
| `screener.accum.hard_filters` | `gate` | `v1` | Screen hard-filter production identity; hard-filter tournament adapter is a downstream slice |

Exact common binding:

- `contract_id = "production_policy_snapshot.v2"` for all seven rows;
- `purpose = "ACCUMULATION_DISCOVERY"`;
- individual `policy_version` as in the table (unchanged policies remain policy
  version `v1`; the artifact contract is v2);
- `learning_observation_contract_id =
  "learning_observation.accumulation_discovery.v2"`;
- `producer_observation_contract = "accumulation-discovery.v2"`.

Hard-filter semantic contract (seventh row):

- `semantic_engine_contract_id = "screen.accum.hard_filters.v1"`;
- payload must include floors, enabled states, first-match order, and the
  locked missing/provider action vocabulary from the ai-saham activation task.

Sector breadth is explicitly outside the closed snapshot set. Remove/disable the
current mirrored `sector_breadth` production component during cutover. A
challenger/factor query for it returns `BLOCKED_POLICY`; no `+10 when present`
fallback is allowed.

#### Historical v1 (non-eligible)

`production_policy_snapshot.v1` six-row sets may remain readable for audit /
display only. They must never:

- satisfy active production eligibility;
- fall back when v2 is missing or incomplete;
- be dual-written or inferred under a new compatibility ID.

For `signal.accum.raw_score`, the exact observed baseline field is
`features_by_window.<canonical_window>.signal.raw_exact_score`. The rounded
`features_by_window.<canonical_window>.signal.assessment.score` is a
classification/display companion and must not replace the raw-score baseline.

### `VerifiedProductionPolicySnapshot`

The upstream contract fields (v1 and v2 row shape) are exactly:

```text
snapshot_id
schema_version
contract_id
purpose
learning_observation_contract_id
producer_observation_contract
compatibility_id
policy_id
policy_version
decision_type
semantic_engine_contract_id
material_config_hash
canonical_payload_json
payload_digest
source_revision              # provenance only
created_at
```

This type must not contain ML panel/extraction/protocol fields. Adding an
upstream field requires an artifact-contract amendment/version bump.

### Exact upstream identity and canonicalization checks

Implement the upstream algorithms without importing sibling Python:

- `snapshot_id` is lowercase SHA-256 of the upstream canonical JSON for
  `{contract_id, identity}`, where identity contains exactly purpose,
  `learning_observation_contract_id`, `producer_observation_contract`,
  compatibility ID, and policy ID. This is the behavior of upstream
  `stable_learning_id`; payload digest is not part of the ID.
- Parse `canonical_payload_json`, recursively preserve nulls, stringify mapping
  keys, reject NaN/infinity, serialize with ASCII escaping, sorted keys, and
  separators `(",", ":")`; require byte-for-byte equality with the stored
  string.
- `payload_digest` is lowercase SHA-256 of those UTF-8 bytes, with no prefix.
- `material_config_hash` must match `sha256:[0-9a-f]{64}` and be identical
  across all **seven** active v2 rows.
- For active eligibility, `contract_id` must be
  `production_policy_snapshot.v2` and `snapshot_id` must recompute with that
  contract in `stable_learning_id`.
- Validate the frozen non-ASCII/null/bool/float example supplied by `ai-saham`
  before accepting the canonicalizer as conformant.

### `ChallengePolicyAdapter`

The locally owned adapter contract fields are:

```text
adapter_id
adapter_version
supported_policy_id
supported_snapshot_contract
supported_semantic_engine_contract_ids
panel_kind
score_kind
component extraction paths / aliases
supported challengers
```

The adapter ID/version must be included in the challenge artifact. Supporting a
policy ID alone is insufficient; semantic contract support must be explicit.

`Protocol` remains separate and owns universe, target/labels, horizons, folds,
embargo, costs, min N, and evaluation PIT rules.

## 10. Challenge Preparation Contract

For an accumulation PolicySpec claiming production comparison:

1. Resolve one observation compatibility cohort using the shared cohort helper.
2. Require and validate the exact **seven-row** `production_policy_snapshot.v2`
   set above. A PolicySpec uses its corresponding row, but verified-cohort
   readiness requires the closed set so partial producer installation is
   visible immediately.
3. Read snapshots matching
   `(ACCUMULATION_DISCOVERY, compatibility_id, policy_id)` with
   `contract_id = production_policy_snapshot.v2`.
4. Recompute canonical payload digest and validate every identity field.
5. Resolve one local adapter supporting each policy and semantic contract.
6. Only then build the panel and folds.

Return `BLOCKED_POLICY` before panel execution when any of these conditions
holds:

- required upstream table is absent;
- required snapshot is absent;
- only historical v1 / six-row set is present for the cohort;
- partial six-of-seven v2 set;
- duplicate/conflicting snapshot exists;
- stored digest does not match canonical payload;
- purpose, observation contract, cohort, or policy identity mismatches;
- snapshot contract is not `production_policy_snapshot.v2` for active eligibility;
- semantic engine contract is unsupported by the adapter;
- counterfactual requested without conformance evidence;
- sector-breadth challenger/factor requested under the closed set.

`BLOCKED_DATA` remains reserved for valid-policy runs lacking usable rows,
labels, dates, folds, or minimum N.

## 11. Baseline And Counterfactual Rules

### Observed baseline

When the question is whether a challenger ranks or gates better than what was
actually produced, use the frozen observation score/action/gate result. Do not
recompute production merely because parameters are available.

### Counterfactual baseline

Recomputation is allowed only for a declared intervention such as:

- equal/reweighted sleeves;
- drop-factor ablation;
- flags off;
- classification threshold shift;
- named risk gate off;
- screen hard-filter floor / enablement change (downstream hard-filter
  tournament adapter; not required to ship full tournament metrics in this
  consumer task, but must not claim production hard-filter baseline without
  the verified seventh row).

The unchanged leg must reproduce the declared upstream semantic contract on
golden vectors. If exact reproduction is not possible from the captured facts,
that challenger is `BLOCKED_POLICY`; do not approximate silently.

## 12. Packaged Policy JSON Disposition

Current JSON files under `src/ml_saham/challenge/policies/` must cease being
production authority after cutover.

Allowed dispositions:

- convert ML-only fields into explicit `ChallengePolicyAdapter` specs;
- retain narrowly scoped immutable test fixtures with names making fixture
  status explicit;
- remove production parameter/hash copies that are supplied by verified
  snapshots.

Forbidden:

- fallback to these files when an upstream snapshot is missing;
- displaying their handwritten `hash` as verified production identity;
- using their material values for a different or unknown cohort.

## 13. Artifact Contract

Every policy challenge, factor challenge, engine portfolio row, health result,
champion result, and promote packet that claims a production comparison must
carry:

```text
observation_compatibility_id
production_snapshot_id
production_snapshot_digest
production_policy_id
production_policy_version
production_semantic_engine_contract_id
challenge_adapter_id
challenge_adapter_version
protocol_id
```

Artifact reopening and promote-packet generation must preserve and display these
identities. A legacy artifact lacking them may be opened as historical output
but is not eligible for a verified production-policy promotion packet.

## 14. Sequencing And Activation Gate

This task is ready to specify but blocked for implementation until `ai-saham`
has delivered the **v2 activation** (companion task
`activate_screen_hard_filter_tournament_cohort.md`):

- accepted ADR-059 amendment for `production_policy_snapshot.v2`;
- migration allowing v1|v2 contract_ids; v1 rows remain immutable history;
- exactly the **seven** required accumulation policy rows with the locked IDs,
  decision types, binding strings, ID formula, and hard-filter payload;
- lean compatibility.v2 framing with snapshot binding
  `production_policy_snapshot.v2` (no delimiter-free alias);
- a fresh accumulation compatibility cohort bound to those **seven** v2
  snapshots (not the historical 1,890-row pre-binding cohort);
- producer tests, migration tests, and digest/golden examples;
- operational activation preferred for live smoke: backfill + labels +
  extract `SUFFICIENT_FOR_REPLAY` (producer code may merge earlier).

Implementation sequence in this repository:

1. Amend/accept ADR-002 for **v2/seven** before consumer runtime code. ADR and
   implementation may share one PR/branch, but the amended contract lands first.
   **Do not commit a v1/six-only consumer.**
2. Add read-only snapshot types/reader and digest/identity validation for
   `production_policy_snapshot.v2`.
3. Split production snapshot from `ChallengePolicyAdapter`.
4. Bind snapshot resolution into shared challenge preparation; enforce closed
   seven-row v2 set.
5. Add `BLOCKED_POLICY` paths (including historical-v1-only and partial v2) and
   artifact identity fields.
6. Add golden-vector conformance tests per supported semantic contract. These
   vectors are in scope for this cutover, not a follow-up; a counterfactual
   remains blocked until its vector suite passes. Hard-filter tournament
   adapter conformance may land with the tournament task if not ready here,
   but then hard-filter counterfactuals stay `BLOCKED_POLICY`.
7. Convert/remove packaged production mirrors.
8. Update `BOUNDARY.md`, challenge docs, and operator output.
9. Run live read-only smoke against the fresh **v2** upstream cohort.

Do not remove the old production-mirror path before the fresh v2 upstream cohort
is available. Once cutover begins, do not retain packaged mirrors or v1 as a
compatibility fallback; perform one clean switch to v2.

## 15. Testing Expectations

Positive:

- matching cohort + valid snapshot + supported adapter permits challenge prep;
- digest is recomputed from canonical payload and matches the upstream example;
- exact snapshot ID recomputation, closed **seven-row v2** set, common material
  hash, and binding strings validate;
- observed baseline uses frozen observation output;
- supported counterfactual passes golden-vector conformance;
- result and artifact include all snapshot/cohort/adapter identities.

Negative:

- missing table/snapshot returns `BLOCKED_POLICY`;
- malformed JSON or bad digest returns `BLOCKED_POLICY`;
- wrong purpose, observation contract, cohort, or policy ID returns
  `BLOCKED_POLICY`;
- unsupported snapshot/semantic contract returns `BLOCKED_POLICY`;
- adapter for the right policy but wrong semantic contract is rejected;
- counterfactual without conformance proof is rejected;
- missing any one of the seven required v2 rows is rejected;
- historical v1 / six-row-only cohort is rejected for active production
  eligibility (no fallback);
- wrong decision type for any locked policy ID is rejected;
- sector-breadth challenge is rejected under the closed set;
- packaged JSON cannot rescue any failed case;
- valid policy with insufficient folds remains `BLOCKED_DATA`, proving status
  separation;
- all SQLite tests use read-only/temp fixtures and perform no upstream writes.

Run focused challenge/reader/artifact tests, the full relevant suite,
`git diff --check`, and whole-repository Ruff checks when Python is touched.

## 16. Acceptance Criteria

- [x] Implementation begins only after the upstream activation gate is met.
- [x] One observation cohort is selected before snapshot lookup.
- [x] Upstream canonical digest and all binding identities are validated.
- [x] The exact **seven-row** `production_policy_snapshot.v2` policy set and
      decision-type map are enforced (including
      `screener.accum.hard_filters`).
- [x] Snapshot ID and canonical JSON use the locked upstream algorithms with
      contract_id v2 for active rows.
- [x] All seven rows share the exact purpose, observation contracts, cohort,
      material-config hash, and v2 contract_id.
- [x] Historical v1 is non-eligible for `baseline=production` (no fallback).
- [x] `VerifiedProductionPolicySnapshot` is separate from
      `ChallengePolicyAdapter` and `Protocol`.
- [x] Missing/mismatched/unverifiable policy returns `BLOCKED_POLICY` before
      panel execution.
- [x] No packaged production fallback exists after cutover.
- [x] Observed outputs are preferred for ordinary production baselines.
- [x] Counterfactuals require semantic-contract support and golden conformance.
- [x] Sector breadth is removed/disabled as a closed-set production component
      and its counterfactual returns `BLOCKED_POLICY`.
- [x] Challenge/result/artifact/promote surfaces carry cohort, snapshot,
      adapter, and protocol identities.
- [x] `ml-saham` never writes or repairs the upstream database.
- [x] ADR-002 and `BOUNDARY.md` describe the verified split and no longer call
      feature/parameter names alone a sufficient production snapshot.
- [x] No production auto-promotion or diagnostic-authority change is introduced.
- [ ] Focused/full relevant tests and whole-repo Ruff gates pass.

## 17. Documentation Impact

- ADR-002 amendment: Yes.
- `BOUNDARY.md`: Yes — add snapshot read/ownership contract.
- Challenge product and artifact docs: Yes.
- README/operator help: update only if output gains new policy-blocked guidance.
- New config: No.
- Limitation: historical cohorts without snapshots cannot support verified
  `baseline=production` claims.

## 18. Required Reading

- `BOUNDARY.md`
- `docs/adr/ADR-001-challenge-first-product-axis.md`
- `docs/adr/ADR-002-ideal-challenge-system.md`
- `docs/challenge_product.md`
- `data_contract.md`
- `src/ml_saham/challenge/types.py`
- `src/ml_saham/challenge/policies/registry.py`
- `src/ml_saham/challenge/runner.py`
- `src/ml_saham/challenge/scorers.py`
- `src/ml_saham/challenge/artifacts.py`
- `src/ml_saham/challenge/promote.py`
- `src/ml_saham/challenge/panel.py`
- sibling producer task and accepted snapshot ADR/contract

## 19. Agent Execution Instructions

Before implementation, the agent must:

- verify the upstream activation gate using current `ai-saham` code and schema;
- inspect and protect both worktrees;
- enumerate every current consumer of `PolicySnapshot` and `policy_hash`;
- identify which challenges use observed output versus counterfactual
  reproduction;
- state supported policy IDs and semantic contract IDs;
- state the layer plan and exact clean-break boundary;
- stop if asked to import sibling Python, write upstream SQLite, infer missing
  snapshots, keep a fallback, or auto-promote a result.

## Do Not Interpret This As

- Do not rename the existing overloaded class and leave its responsibilities
  mixed.
- Do not accept a non-empty hash string as verification.
- Do not bind today's snapshot to an older cohort.
- Do not treat `source_ref` prose as machine-verifiable provenance.
- Do not let the ML adapter own production material parameters.
- Do not put fold/label/protocol rules in the production snapshot.
- Do not turn diagnostic bags into production policies.
- Do not downgrade policy-integrity failures to warnings or `BLOCKED_DATA`.
- Do not preserve static mirrors as a fallback after cutover.
- Do not write to `ai-saham` or auto-edit its configuration.
- Do not merge a v1/six-only consumer and immediately supersede it with v2.
- Do not treat historical v1 snapshots as active production eligibility.
- Do not claim hard-filter `baseline=production` without the verified seventh
  row under snapshot v2.

## Completion Record

- Completed date: 2026-07-31
- Upstream `ai-saham` v2 activation commit / compatibility ID:
  `46c35f86` / `sha256:8ba8fc1e53868bb267c3ef4efeb6ba8780479f4b83fb500573df7826b4040beb`
- Upstream ADR-059 amendment: `46c35f86`
- `ml-saham` implementation commit: `b674e8b`
- Supported snapshot contract: `production_policy_snapshot.v2` (seven rows)
- Supported semantic contracts: `accum_score_policy.v1`,
  `signal.semantic_engine.v1.5`, `risk.hard_gates.accum.v1`, and verified
  identity binding for `screen.accum.hard_filters.v1`.
- Hard-filter adapter status (`BOUND` / `BLOCKED_POLICY_until_tournament_task`):
  `BLOCKED_POLICY_until_tournament_task` — the seventh snapshot is required and
  verified, but the local adapter intentionally has no conformance ID yet.
- Commands run: focused/full challenge pytest; live `challenge run`, `factor
  --all`, `engine screener --scenario accum`, and `health --scenario accum`, all
  with the explicit v2 compatibility ID; `git diff --check`; targeted and
  whole-repository Ruff gates; full repository pytest.
- Test result: relevant challenge/snapshot suite `176 passed`; full repository
  `325 passed, 8 failed` on pre-existing incomplete chapter demos
  (`broker-flow`, `volatility-sizing`, `market-regime`, `research-pipeline`,
  `seasonality-drift`, `special-monitoring`, and `meta-ensemble`).
- Live read-only smoke result (v2 cohort): verified seven-row set accepted;
  304-row panel; score-weight challenge `INCONCLUSIVE`, production H10 IC
  `+0.3161` versus equal-sleeves `+0.3065`; factor/engine/health selectors all
  remained bound to the explicit cohort; no v1/package fallback.
- Lint result: all task-touched files pass Ruff and format checks; whole-repo
  baseline remains red with 69 unrelated errors and 71 pre-existing files that
  would be reformatted. `git diff --check` passed.
