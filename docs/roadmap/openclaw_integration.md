# OpenClaw Integration Roadmap

Status: `PROPOSED`

Last verified against upstream documentation: 2026-08-02

## 1. Outcome

Provide a dedicated, locked-down OpenClaw reviewer that can discover, explain,
run, and review existing ml-saham challenges through a small structured tool
surface without becoming a challenge or production authority.

```text
Dedicated OpenClaw reviewer agent
  -> per-agent tool and skill policy
  -> local stdio ml-saham MCP adapter
  -> ChallengeWorkbenchService
  -> existing challenge/data/artifact owners
  -> structured result with exact identities and status
```

OpenClaw conversation, memory, skills, schedules, and model output are
non-authoritative. Only the structured result produced by ml-saham may carry a
challenge status.

## 2. Why MCP, Not A Plugin

OpenClaw currently supports managed MCP servers over stdio or remote HTTP,
tool filtering, diagnostics/probing, per-agent tool policy, sandbox controls,
and workspace skills.

Use the same local stdio ml-saham MCP adapter planned for Hermes. Do not build
an OpenClaw plugin: plugins run in the Gateway trust boundary and add an
unnecessary Node/in-process integration surface. Do not let a skill shell out
to `ml-saham`; a skill is instructions, not a typed transport or authority
boundary.

Remote Streamable HTTP, OAuth, public exposure, and multi-user operation are
outside the initial roadmap.

## 3. Authority And Security Locks

- ml-saham is an offline challenge lab first and curriculum second.
- ai-saham owns production behavior, ingest, observations, labels, snapshots,
  and shared SQLite; ml-saham accesses it read-only.
- The OpenClaw agent receives only structured MCP capabilities. It receives no
  arbitrary SQL, shell, Python, filesystem, browser, provider, or ai-saham tool.
- Use a dedicated OpenClaw agent ID and workspace. Do not add the integration to
  a general personal assistant with broad host or messaging capabilities.
- Set workspace access to none unless a later accepted requirement proves a
  need. The MCP server itself resolves configured paths through ml-saham.
- Deny exec, filesystem mutation, browser, messaging, cron, gateway mutation,
  node control, and sub-agent spawning in the reviewer profile through the
  effective tool policy.
- Set an explicit skill allowlist containing only the reviewed ml-saham skill;
  do not rely on default unrestricted discovery.
- Set an MCP include filter containing only approved `ml_*` tools. Effective
  per-agent tool visibility must be tested after discovery.
- No implicit cohort selection, identity inference, verdict rewriting,
  upstream writes, trading, fetching, or auto-promotion.
- OpenClaw memory may remember display preferences, never authoritative market
  or challenge state. Every answer re-resolves current identities and status.
- If multiple people or channels can steer the agent, use a separate Gateway
  and OS user/container. Session scoping is not a multi-user authorization
  boundary.

## 4. Shared MCP Contract

OpenClaw must reuse the common ml-saham MCP adapter rather than creating a
platform-specific API.

Proposed module boundary:

```text
src/ml_saham/mcp/
  server.py       # stdio transport and tool declarations
  schemas.py      # structured response contracts
  mapping.py      # application DTO -> MCP response mapping
```

The adapter is thin and calls `ChallengeWorkbenchService` or another accepted
typed application service. It never calls Typer, parses Rich output, reads raw
SQLite from the MCP layer, or treats arbitrary artifact JSON as valid.

### Tool capability tiers

| Tier | Tools | Effect |
|---|---|---|
| Discovery | `ml_product_describe`, `ml_policy_catalog`, `ml_cohort_catalog` | Read-only facts; cohort discovery grants no eligibility |
| Review | `ml_challenge_health`, `ml_artifact_inspect` | Read-only exact status and validated artifacts |
| Execution | `ml_challenge_run` | Optional later capability; normal ml-saham artifact write only |

Execution is not exposed until its phase passes. No v1 tool creates a promote
packet, modifies ai-saham, installs dependencies, changes OpenClaw config, or
sends a message.

### Response envelope

Each tool returns a versioned structured envelope with:

- schema ID/version, tool name, and request ID;
- exact status and closed machine-readable reasons;
- applicable cohort/population, production snapshot, policy, adapter,
  Protocol, baseline, challenger, source, and artifact identities;
- data range, denominators, exclusions, missingness, and folds when applicable;
- `authoritative_source="ml-saham"` and
  `agent_summary_authority="none"`;
- bounded/paginated data and sanitized errors.

OpenClaw must ignore unknown response fields for forward-compatible display but
must reject unsupported schema versions for any authoritative interpretation.

## 5. Phases

### O0 - architecture, version, and threat-model lock

Deliver:

- ADR accepting the shared MCP adapter and rejecting plugin/CLI-wrapper paths;
- exact tested OpenClaw release, MCP SDK range, and MCP protocol version;
- authority matrix for upstream data, snapshots, results, artifacts, MCP
  transport, OpenClaw memory/skills, and agent prose;
- threat model covering prompt injection, skill poisoning, tool confusion,
  global/per-agent policy drift, path traversal, secret leakage, replay,
  duplicate calls, stale memory, and untrusted channel senders;
- final tool schemas, limits, timeouts, and failure taxonomy.

Exit gate: the effective per-agent capability boundary can be inspected and
tested. If the selected OpenClaw version cannot isolate the reviewer tool set,
use a separate Gateway/OS identity or stop.

### O1 - local read-only MCP foundation

If another roadmap already delivered the shared adapter, verify and reuse it.
Otherwise deliver:

- optional stable MCP Python SDK dependency;
- local stdio entry point with stdout reserved for MCP protocol traffic;
- Discovery-tier tools mapped from typed application DTOs;
- deterministic ordering, bounded responses, safe stderr diagnostics, and no
  persistent write;
- server capability/version response.

Verification:

- SDK client and MCP Inspector smoke;
- schema/mutation and malformed-input tests;
- architecture guard proving no CLI/data/artifact implementation leakage into
  the MCP layer;
- core install/import without MCP or OpenClaw;
- upstream SQLite no-mutation tripwire;
- missing DB/table/schema failures return typed failure, never empty success.

### O2 - dedicated OpenClaw reviewer

Deliver:

- one dedicated agent ID and workspace with no host-workspace access;
- MCP server registration through `openclaw mcp add`/`set` using stdio;
- explicit MCP include filter for Discovery and approved Review tools;
- `openclaw mcp doctor --probe` capability evidence;
- exact per-agent tool allowlist and denials for exec, filesystem mutation,
  browser, messaging, cron, node/gateway control, and sub-agents;
- exact skill allowlist containing one reviewed `ml-saham-reviewer` skill;
- skill instructions that require exact identity/status citation and label all
  natural-language interpretation non-authoritative.

Do not use a shared/global skill when a per-agent workspace skill suffices. Do
not enable automatic skill generation or install a third-party plugin for this
integration.

Exit gate: effective tool inventory proves that the reviewer can call only the
intended ml-saham tools, and adversarial prompts cannot reach host tools or
replace explicit identities.

### O3 - read-only health and artifact review

Deliver:

- `ml_challenge_health` with exact required population and policy identity;
- validated artifact inventory/inspection through the canonical reader;
- compatible comparison only when ml-saham proves all material identity axes;
- bounded table rendering suitable for chat channels;
- prompt-injection fixtures embedded in corpus/artifact text;
- evaluation set for status fidelity, identity citation, refusal, and
  hallucination.

Historical artifacts are display-only. OpenClaw may explain why a result is
blocked or inconclusive, but cannot relabel it or turn diagnostics into Action.

### O4 - controlled existing-challenge execution

Start only after ml-saham has one canonical immutable run request and
duplicate-execution guard shared with CLI/Streamlit.

Deliver:

- `ml_challenge_run` limited to canonical registered challenge contracts;
- explicit exact population, policy, baseline, challenger, and write choice;
- application-owned request ID and retry/idempotency behavior;
- synchronous execution first with honest timeout semantics;
- normal canonical artifact writer only;
- a proven per-call OpenClaw human approval path plus server-side validation
  and allowlists.

Do not grant exec/filesystem tools merely to run a challenge. MCP is the only
execution path. Client approval is not sufficient authorization; the server
must reject unsupported or incomplete requests independently. If the pinned
OpenClaw release cannot enforce per-call human approval for the MCP tool, keep
`ml_challenge_run` disabled and direct the human to the CLI or Challenge Desk.

Exit gate: retries cannot duplicate an artifact, C0-C4 product gaps remain
unavailable, and no result can trigger promote/apply/send actions.

### O5 - optional scheduled read-only digest

This phase is optional and requires a separate deployment decision.

- read-only tools only; exclude `ml_challenge_run` from scheduled/channel agent;
- fixed explicit policy/population watchlist outside model-generated prompts;
- paired owner-only channel, rate limits, bounded output, and delivery audit;
- no broad shared-channel access;
- every digest includes source timestamp, exact identity, unchanged ml-saham
  status, and a non-authoritative summary label;
- no alerts interpreted as trading advice or production Action.

If strict per-agent/channel isolation cannot be demonstrated, deploy the digest
agent in a separate OpenClaw Gateway and OS user/container or do not ship it.

## 6. Test Matrix

| Area | Required proof |
|---|---|
| Effective policy | Reviewer sees only explicitly approved MCP tools and one skill |
| Sandbox | No host workspace, exec, filesystem, browser, messaging, node, or sub-agent reachability |
| Determinism | Same request/source identities produce the same structured response |
| Read-only upstream | SQLite file metadata, schema/page/count state, and rows unchanged |
| Identity | Every material identity mutation changes or blocks output correctly |
| Failure | Missing, malformed, stale, unsupported, and conflicting state fails closed |
| Injection | Data/artifact/skill text cannot issue tools or override system policy |
| Retry | Duplicate calls cannot duplicate challenge execution or artifact commits |
| Memory | Stale remembered IDs/status never replace a current tool resolution |
| Packaging | Core ml-saham runs without MCP/OpenClaw installed |

## 7. Definition Of Done

- O0-O3 complete for the useful read-only reviewer integration.
- O4 and O5 remain independently optional.
- No OpenClaw dependency or configuration parser exists in core challenge code.
- No plugin, CLI scraping, direct SQLite/artifact parsing, implicit selection,
  auto-promotion, or upstream write exists.
- Exact pinned-release configuration and effective tool inventory are recorded
  during implementation; examples copied from `main` are not treated as a
  version lock.
- Focused tests, architecture guard, relevant challenge contract gates, full
  applicable CI, and `git diff --check` pass.

## 8. Upstream References

- [OpenClaw MCP CLI](https://github.com/openclaw/openclaw/blob/main/docs/cli/mcp.md)
- [OpenClaw gateway MCP configuration](https://github.com/openclaw/openclaw/blob/main/docs/gateway/configuration-reference.md)
- [OpenClaw tools, skills, and plugins](https://github.com/openclaw/openclaw/blob/main/docs/tools/index.md)
- [OpenClaw skill scopes and allowlists](https://github.com/openclaw/openclaw/blob/main/docs/tools/skills.md)
- [OpenClaw sandbox and tool policy](https://github.com/openclaw/openclaw/blob/main/docs/gateway/sandbox-vs-tool-policy-vs-elevated.md)
- [OpenClaw security boundary](https://github.com/openclaw/openclaw/blob/main/SECURITY.md)
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
