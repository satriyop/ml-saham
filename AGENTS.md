# Agent Contract

You are an AI development agent working on `ml-saham`.

Before every task:

1. Read and follow `AGENT_QUICKSTART.md` completely.
2. Read this `AGENTS.md` completely.
3. Use the reading matrix in `AGENT_QUICKSTART.md` to select the minimum
   task-specific documentation required.

Do not load every design document for a small task. Do not skip the required
boundary, protocol, data, or artifact contracts for challenge work.

Root CLI map: `challenge` (product) · `learn` (curriculum) · `doctor` / `vet`
(shared). Panel/extractor work must follow `docs/challenge_extract_contract.md`
and pass `./scripts/check_challenge_contracts.sh` before claiming done. For
shipped extract paths, CLI map, and multi-fold WIN semantics, prefer
`docs/challenge_product.md`, `docs/challenge_extract_contract.md`, and
`data_contract.md` over ADR migration/follow-up prose when they conflict.

Always confirm explicitly that:

- you understand that `ml-saham` is an offline challenge lab first and a
  curriculum second;
- `ai-saham` owns production behavior, ingest, observations, corpus labels, and
  the shared SQLite database;
- this repository reads the upstream database read-only and never repairs,
  migrates, or writes it;
- challenge results are deterministic human decision support and never
  auto-promote production configuration;
- you will preserve point-in-time, cohort, policy, protocol, adapter, and
  artifact identities and fail closed when they are absent or inconsistent;
- you will not confuse curriculum demonstrations with challenge authority;
- you will protect shared worktree changes and use no destructive git cleanup
  without explicit approval and file scope;
- you will obey the verification matrix in `AGENT_QUICKSTART.md`.

Before coding, state:

- risks, ambiguities, stale-contract findings, and unavoidable assumptions;
- the semantic-change classification from `AGENT_QUICKSTART.md`;
- the implementation boundary:

  ```md
  Boundary plan:
  - Data/read boundary:
  - Challenge contracts and orchestration:
  - Evaluation/statistics:
  - Artifacts:
  - CLI:
  - Curriculum:
  ```

For documentation-only tasks, mark all runtime boundaries `not touched` and add
`Documentation/governance`.

Proceed only when the preflight is clear and the user requested implementation
or supplied an explicitly actionable task. If a request would write ai-saham
state, conceal leakage, weaken a verdict gate, infer production identity, or
auto-promote a result, stop and ask for an architecture/task-contract change.
