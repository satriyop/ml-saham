# ADR-003: Local Streamlit Challenge Desk

**Status:** Accepted
**Date:** 2026-08-02
**Related:** [ADR-001](./ADR-001-challenge-first-product-axis.md) ·
[ADR-002](./ADR-002-ideal-challenge-system.md) ·
[BOUNDARY.md](../../BOUNDARY.md)

## Context

The shipped challenge product is command-driven. It already owns deterministic
PolicySpec tournaments, factor validity, engine and health rollups, diagnostics,
artifacts, and human review packets. Operators must nevertheless remember many
flags, carry exact compatibility identities between commands, and compare fold
and identity evidence across text output and artifact directories.

The MVP architecture intentionally said “CLI only; no web/TUI.” That constraint
described the smallest shippable product. It is no longer the preferred limit
for a visual challenge-management surface.

The choice was evaluated independently of the existing Typer/Rich stack.
Streamlit fits this product better than a terminal UI because cohort tables,
fold inspection, metric comparison, missingness, identity lineage, and artifact
history benefit from browser-width data tables and plots. The CLI remains
better for automation, CI, scripting, recovery, and headless use.

## Decision

Add a **local, single-user Streamlit Challenge Desk** as an optional thin
presentation adapter.

```text
Typer CLI --------\
                   -> ChallengeWorkbenchService -> challenge/data/artifact authority
Streamlit Desk ---/
```

### Framework and launch contract

- Python 3.11+ and optional dependency `streamlit>=1.43,<2` under the `ui`
  extra.
- Launch with `ml-saham challenge desk`.
- Bind to loopback only (`127.0.0.1` by default); Phase 0 does not support
  remote hosting, authentication, or multi-user use.
- Use the official `python -m streamlit run` command surface. Do not depend on
  private Streamlit bootstrap APIs.
- Core/headless installation and every existing CLI path remain usable without
  Streamlit.

### Authority boundary

The Desk may own layout, navigation, presentation state, explicit form input,
and local interaction feedback. It must consume typed application DTOs.

It must not:

- query SQLite or artifact JSON directly;
- call Typer commands or scrape CLI/Rich output;
- calculate features, metrics, folds, readiness, eligibility, or verdicts;
- invent policy aliases, challengers, Protocols, identities, or fallback;
- auto-select largest/latest/only cohorts for production-facing work;
- rewrite `BLOCKED_*` or `INCONCLUSIVE` as successful UI states;
- import ai-saham, fetch providers, write upstream SQLite/configuration, or
  auto-promote a result.

`ChallengeWorkbenchService` is the shared typed presentation boundary. Product
meaning remains in the existing `challenge/`, `data/`, `eval/`, and
`artifacts/` owners. Streamlit is never a second challenge authority.

### Delivery phases

| Phase | Scope |
|---|---|
| 0 | ADR, optional dependency, launcher, typed facade, boundary-only shell |
| 1A | Read-only Control Tower, factual cohort discovery, canonical Policy Catalog |
| 1B | C0-backed producer and Protocol readiness enrichment |
| 2 | Explicit challenge setup and synchronous Result Inspector |
| 3 | Validated artifact history/comparison and human-review handoff |
| 4 | Measured, durable local jobs plus operational/accessibility hardening |

Phase 0 exposes no challenge actions or placeholder metrics. Phase 1A may use
existing typed health/results, factual cohort inventory, and the canonical
policy registry without waiting for the separate C0 readiness projection.
Missing readiness is displayed as unavailable, never inferred. Only Phase 1B
depends on C0; the UI may not fill that gap with SQL, CLI scraping, or
presentation logic. Phase 2 may expose already registered and executable
challenge contracts after Phase 1A while capabilities dependent on unfinished
C0-C4 work remain unavailable.

## Superseded scope

This ADR supersedes only the MVP statements that prohibit any web/TUI surface
in `architecture.md`, `ux.md`, and the shipped product guide. It does not
supersede:

- challenge-first/curriculum-second product priority;
- CLI product commands or machine-readable outputs;
- ai-saham ownership and read-only SQLite rules;
- cohort, production-policy, adapter, Protocol, verdict, or artifact contracts;
- human-only production changes and the prohibition on auto-promotion.

## Consequences

### Positive

- Easier discovery and comparison without duplicating product authority.
- One application boundary can support CLI and browser presentation tests.
- Optional packaging preserves a small headless/core install.
- Browser layout is suitable for later fold, cohort, and artifact inspection.

### Trade-offs

- Streamlit reruns require explicit duplicate-execution guards before Phase 2.
- Long-running work needs measured job design; session state alone is not a
  durable queue.
- A local HTTP server exists while the Desk runs, although it performs no
  external network operation and binds only to loopback.
- UI testing and packaging add an optional dependency and CI surface.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Textual TUI | Better for SSH/keyboard workers, but weaker for the product's table/chart/comparison-heavy workflow and slower to build |
| Streamlit pages calling CLI commands | Duplicates transport concerns and makes rendered strings an unstable API |
| UI-owned direct SQLite queries | Creates a second data/cohort/readiness authority and risks upstream mutation or silent fallback |
| FastAPI plus React/HTMX now | Adds a service/deployment architecture without a remote or multi-user requirement |
| Notebook as primary UI | Weak operational navigation, state, packaging, and repeatable interaction testing |

## One-line summary

> The Challenge Desk is an optional localhost Streamlit adapter over typed
> ml-saham application services; it improves challenge management without
> becoming a scorer, data owner, or promotion authority.
