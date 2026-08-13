# C0 ACCUM readiness authority matrix (2026-08-13)

Status: `LOCKED_FOR_IMPLEMENTATION`

C0 is a read-only readiness report. It is not a challenge verdict and cannot
authorize a production change.

| Fact | Owner / source of truth | ml-saham validation | Output axis |
|---|---|---|---|
| ACCUM observations | ai-saham SQLite `learning_observations` | Explicit `compatibility_id`; validate the consumed envelope and schema-15 payload contract; reject malformed or mixed rows | C0A |
| Population identity | ai-saham observation envelope and payload binding | Require the explicit cohort identity and a non-empty population binding on every counted current observation | C0A |
| Production policy set | ai-saham SQLite `production_policy_snapshots` | Existing independent v4 snapshot verifier and supported adapter registry; exact closed set is **9/9** | C0A and C0B |
| Producer path labels | ai-saham SQLite `learning_outcome_labels` | Join only validated cohort observations; enforce supported H3/H10/H20 contracts and terminal availability/outcome consistency | C0A only |
| Action/readiness | ai-saham schema-15 observation payload | Read locked window-7 paths from validated observations; missing readiness is a reported fact, not corruption | C0A only |
| Evaluation targets | ml-saham Protocol and candles/IHSG | Existing panel builder computes point-in-time excess returns; producer labels do not gate `accum_path_v1` | C0B |
| Fold estimate | ml-saham Protocol and fold builder | Use the exact `time_purged_folds` implementation used by challenge runs | C0B |

Status laws:

- C0A is `BLOCKED_POLICY` for consumed-contract corruption or an incomplete
  claimed active snapshot set; `LEGACY_RAW_ONLY` when the active set/current
  population authority is absent; `COLLECTING` when the current set verifies
  but there are fewer than two valid sessions or no available H10 producer
  labels; otherwise `CHALLENGE_INPUT_READY`.
- C0B is `BLOCKED_POLICY` when explicit cohort, snapshot, adapter, PolicySpec,
  or Protocol authority cannot be established; `BLOCKED_DATA` when a valid
  panel cannot be formed; `INCONCLUSIVE_DEPTH` when the panel exists but has
  fewer post-embargo folds than the Protocol requires for a directional
  verdict; otherwise `READY_FOR_PROTOCOL`.
- `CHALLENGE_INPUT_READY` never implies `READY_FOR_PROTOCOL`. Neither status is
  `WIN`, `LOSE`, promotion evidence, or trading authority.

The older C0 backlog prose naming a seven-policy active set is stale. Executable
snapshot verification currently requires `production_policy_snapshot.v4` and
nine policies. This decision follows the current code and database contract.
