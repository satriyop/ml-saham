# Hermes Integration Roadmap

Status: `PROPOSED`

Last verified against upstream documentation: 2026-08-02

## 1. Outcome

Let a local Hermes Agent help an operator discover, explain, run, and review
existing ml-saham challenges without making Hermes a data, scoring, verdict, or
promotion authority.

The integration direction is deliberately one-way:

```text
Hermes conversation
  -> Hermes MCP client and tool allowlist
  -> local ml-saham MCP adapter
  -> ChallengeWorkbenchService
  -> existing challenge/data/artifact owners
  -> structured result with exact identities and status
```

Hermes may summarize the returned evidence. The structured ml-saham result is
authoritative; Hermes prose is not.

## 2. Why MCP

Hermes currently supports local stdio and remote HTTP MCP servers, automatic
tool discovery, and per-server tool filtering. A local stdio MCP adapter is the
smallest mature integration because it avoids a new daemon, network listener,
authentication service, CLI-output parser, or Hermes-specific Python import.

Do not drive Hermes through its ACP, JSON-RPC gateway, or OpenAI-compatible API
from ml-saham. Those interfaces are appropriate when ml-saham needs to control
an agent session; this product only needs Hermes to call bounded ml-saham tools.

## 3. Authority And Safety Locks

- ml-saham remains an offline challenge lab first and curriculum second.
- ai-saham owns ingest, production behavior, observations, corpus labels,
  policy snapshots, and shared SQLite.
- The MCP adapter uses existing ml-saham read-only data/application boundaries.
- No tool accepts SQL, a filesystem path outside configured roots, Python,
  shell commands, arbitrary CLI arguments, or an ai-saham write target.
- No implicit largest/latest/only cohort selection for production-facing work.
- `WIN`, `LOSE`, `INCONCLUSIVE`, `BLOCKED_DATA`, and `BLOCKED_POLICY` pass
  through unchanged.
- No tool edits ai-saham code, YAML, SQLite, or production configuration.
- No tool auto-promotes, applies, trades, fetches provider data, or interprets
  curriculum demonstrations as challenge evidence.
- Hermes memory, learned skills, and conversation summaries never establish a
  current cohort, snapshot, policy, adapter, Protocol, or artifact identity.
  Every authoritative answer re-resolves those identities through ml-saham.
- Local stdio is the only supported transport through Phase 3. Remote HTTP is a
  separate architecture/security decision.
- Hermes `--yolo` and approval mode `off` are forbidden for this integration.

## 4. Shared MCP Contract

The first implemented external-agent roadmap creates one reusable ml-saham MCP
adapter. The second platform reuses it; it must not create a parallel tool API.

Proposed module boundary:

```text
src/ml_saham/mcp/
  server.py       # MCP transport and tool declarations only
  schemas.py      # structured transport DTOs/version metadata
  mapping.py      # application DTO -> MCP response mapping
```

The adapter calls `ChallengeWorkbenchService` or another accepted typed
application service. It does not call Typer commands or reach directly into
SQLite, panels, metrics, or artifact JSON.

### Initial tool set

| Tool | Phase | Effect | Required inputs |
|---|---:|---|---|
| `ml_product_describe` | 1 | Read-only | none |
| `ml_policy_catalog` | 1 | Read-only | optional exact decision-type filter |
| `ml_cohort_catalog` | 1 | Read-only | exact purpose family; discovery only |
| `ml_challenge_health` | 2 | Read-only | exact policy and compatibility/population identity |
| `ml_artifact_inspect` | 2 | Read-only | canonical artifact ID, never arbitrary path |
| `ml_challenge_run` | 3 | Writes only normal ml-saham artifacts when explicitly requested | exact policy, population, baseline, challenger, Protocol-owned options, write flag |

Phase 1 exposes no challenge execution or packet creation tool. Challenge-run
support enters only after its immutable request, duplicate-call behavior,
timeout behavior, artifact write target, and approval contract are locked.

`ml_artifact_inspect` must use the canonical artifact reader and current
identity verification. Successful JSON parsing is not sufficient. Historical
artifacts remain historical and cannot acquire promotion eligibility.

### Response envelope

Every tool returns a versioned structured envelope containing at least:

- `schema_id` and `schema_version`;
- tool name and request ID;
- status and closed reason codes;
- exact cohort/population, snapshot, policy, adapter, Protocol, baseline,
  challenger, and artifact identities applicable to that result;
- denominators, exclusions, missingness, folds, and data range when applicable;
- `authoritative_source="ml-saham"`;
- `agent_summary_authority="none"`;
- safe error category without secrets or unrestricted local paths.

Large tables use bounded pagination or summaries plus a canonical follow-up
tool. Tool responses may not silently truncate identity fields or blocker
reasons.

## 5. Phases

### H0 - decision and threat-model lock

Deliver:

- ADR accepting MCP as the shared external-agent adapter;
- exact Python MCP SDK version range and protocol version tested at
  implementation time;
- task-specific authority matrix covering upstream rows, production snapshots,
  challenge results, artifacts, transport, and agent prose;
- threat model for prompt injection, tool confusion, path traversal, secret
  leakage, denial of service, replay, duplicate calls, and stale memory;
- final tool names, schemas, size limits, timeouts, and error taxonomy.

Exit gate: no implementation begins while any tool can infer authority, accept
arbitrary code/path input, or return ambiguous success.

### H1 - local read-only MCP foundation

Deliver:

- optional dependency group for the supported stable MCP Python SDK;
- `stdio` server entry point with stdout reserved for protocol traffic and
  diagnostics sent safely to stderr;
- the three Phase-1 discovery tools;
- typed mapping from application DTOs to structured MCP results;
- startup/version capability response;
- bounded requests, deterministic ordering, and no filesystem writes.

Verification:

- protocol schema and mutation tests;
- architecture/import guard proving the MCP package is a thin adapter;
- core install/import without the MCP extra;
- MCP Inspector or SDK client smoke over stdio;
- upstream SQLite before/after no-mutation tripwire;
- missing DB/table/contract errors fail closed rather than returning empty
  success.

### H2 - Hermes reviewer profile

Deliver:

- documented `hermes mcp add` configuration using the local stdio entry point;
- explicit include filter containing only the approved `ml_*` tools;
- `hermes mcp test` and tool-discovery smoke;
- a small `ml-saham-reviewer` skill that teaches workflow and vocabulary but
  grants no capabilities;
- a dedicated working directory/profile with manual approval mode;
- prompt templates for “what is blocked?”, “compare these validated results”,
  and “explain this verdict” that always cite the returned identities.

The Hermes profile must not expose terminal, filesystem mutation, browser,
provider, or unrelated MCP tools during acceptance. If Hermes cannot prove the
effective tool set for the selected version, run it in an isolated OS
user/container or stop the rollout.

Exit gate: an adversarial prompt cannot cause SQL, shell, upstream writes,
cohort substitution, result-state rewriting, or invented identities.

### H3 - controlled existing-challenge execution

Deliver only after the Streamlit/application workbench has a canonical
immutable run request and duplicate-execution guard:

- `ml_challenge_run` for already registered, executable challenge contracts;
- exact explicit population, policy, baseline, challenger, and write choice;
- server-side allowlist resolved from the canonical registry;
- one request ID per immutable input and idempotent handling of client retries;
- synchronous execution first, with honest timeout/completion behavior;
- existing artifact writer only—no Hermes-owned result schema.

The pinned Hermes release must prove a per-call human approval path for this
MCP tool. Server-side validation remains mandatory because client approval is a
UX guard, not an authorization boundary. If enforceable per-call approval is
not available, keep `ml_challenge_run` disabled and direct the human to the CLI
or Challenge Desk.

Exit gate: repeated transport calls cannot duplicate a persisted artifact or
change challenge identity, and unsupported C0-C4 capabilities remain
unavailable rather than approximated.

### H4 - validated artifact review

Deliver:

- validated artifact inventory and inspection through canonical readers;
- compatible-result comparison only when ml-saham proves every identity axis;
- agent explanations that visibly distinguish raw authoritative fields from
  interpretation;
- injection tests where artifact notes contain malicious instructions;
- evaluation set measuring status fidelity, identity citation, unsupported
  request refusal, and hallucination rate.

No promote-packet creation tool is included in v1. Humans use the existing CLI
or Challenge Desk after reviewing the authoritative artifact.

### H5 - optional messaging and scheduled summaries

This is optional and requires a separate accepted deployment decision.

- dedicated Hermes gateway identity and owner allowlist;
- read-only tools only; `ml_challenge_run` excluded from messaging sessions;
- fixed explicit policy/population watchlist maintained outside prompts;
- rate limits, bounded output, redaction, and delivery audit;
- scheduled messages labeled as summaries, never new challenge verdicts;
- separate OS user/container if any channel has more than one trusted operator.

## 6. Test Matrix

| Area | Required proof |
|---|---|
| Determinism | Same request and source identities produce the same structured response |
| Read-only boundary | Upstream file metadata, SQLite schema/page/count state, and rows unchanged |
| Identity | Mutation of every material identity changes or blocks the result as defined |
| Failure | Missing, malformed, unsupported, stale, and conflicting inputs fail closed |
| Prompt injection | Corpus/artifact strings cannot invoke tools or rewrite instructions |
| Tool scope | Hermes sees only the approved ml-saham MCP tools during acceptance |
| Retry | Duplicate MCP calls cannot duplicate execution/artifact commits |
| Presentation | Hermes quotes exact status/reasons and labels its prose non-authoritative |
| Packaging | Core ml-saham works without MCP/Hermes installed |

## 7. Definition Of Done

- H0-H2 complete for a useful read-only integration.
- H3-H5 remain independently optional and may not delay H0-H2 closure.
- No Hermes dependency is imported by core challenge modules.
- No CLI scraping, direct SQLite/artifact parsing, identity inference, or
  automatic promotion exists.
- All new application/MCP schemas are documented and versioned when persisted
  or externally contracted.
- Focused tests, architecture guard, challenge contract gate when applicable,
  full relevant CI, and `git diff --check` pass.
- Official upstream commands are reverified against the pinned Hermes release
  before implementation; `main` branch documentation is not a version pin.

## 8. Upstream References

- [Hermes Agent repository](https://github.com/NousResearch/hermes-agent)
- [Hermes MCP integration](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/mcp.md)
- [Hermes security model](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/security.md)
- [Hermes CLI commands](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/reference/cli-commands.md)
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
