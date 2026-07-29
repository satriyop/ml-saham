# ADR-001: Challenge-first product axis

**Status:** Accepted  
**Date:** 2026-07-29  
**Related:** [architecture.md](../../architecture.md) · [chapters.md](../../chapters.md) · `src/ml_saham/eval/challenge.py`

---

## Context

`ml-saham` grew two product axes:

| Axis | Surface | Purpose |
|------|---------|---------|
| **Learning** | `explore` / `demo` / curriculum chapters | Problem-centric ML course on real IDX data |
| **Challenge** | `challenge` / `compare` / engine factor map | Stress-test factors & parameters that feed **`ai-saham` engines** |

Early docs and tests optimized for the curriculum (`demo` green, chapter order, soft learning paths). The maintainer priority is the opposite: **challenge is more important than learning.** Artifacts and comparisons should inform tuning of `ai-saham` (never auto-promoted).

Without an explicit decision, agents and future work keep recentering “finish the course” instead of “audit the engines.”

---

## Decision

1. **Primary product** = **challenge lab for `ai-saham`**  
   - Spine: `ml-saham challenge`, `ml-saham compare <factor>`, engine groups in `ENGINE_FACTORS`.  
   - Quality bar: every factor in the engine map has a working **`run_compare`** (baseline ≈ ai-saham-style vs against/learned) and honest metrics/artifacts.

2. **`challenge` vs `compare` (both primary-axis; both related to `ai-saham`)**  

   | Command | Product definition | Relation to `ai-saham` |
   |---------|-------------------|------------------------|
   | **`challenge`** | **Engine audit report** — run a mapped factor set (engine / scenario / all), default baselines, rollup export (JSON/MD). | **For** `ai-saham` engines: “How is the screener / signal / risk / market stack doing?” |
   | **`compare`** | **Single-factor experiment** — one topic slug, explicit `--baseline` / `--against`, full head-to-head narrative + optional artifact pack. | **Against** ai-saham-style (or static/hand) baselines: “Should we change *this* factor/policy?” |

   One-liner:

   > **`compare`** is the single-factor lab used to challenge **ai-saham-style baselines**; **`challenge`** is the multi-factor engine audit that runs those compares in bulk.

   Shared implementation fact: both ultimately call chapter `run_compare`.  
   Product split is **scope + UX**, not a different ML core.

   Rules of thumb:
   - Daily / ship review of engines → `challenge`  
   - Dig into one loser or try alternate models → `compare`  
   - Prefer baselines that mean *current static / engine-like policy*; “against” = learned alternative  
   - Some compares are honest ML hygiene labs (e.g. coin-flip, LOF vs IF) — still on the same data plane and still support tuning habits; they are not “pure sklearn playground” outside `ai-saham`  
   - **Never auto-promote** winners into `ai-saham` configs

3. **Learning is secondary onboarding**  
   - `explore` / `demo` / chapter numbers teach *why* a factor exists so challenge/compare output is interpretable.  
   - Curriculum order and registry numbers remain useful, but **do not outrank engine maps** when priorities conflict.  
   - `demo` may refuse or redirect to challenge/compare for engine-critical factors; that is acceptable if messaging is clear.

4. **Two sources of truth, different jobs**  
   - **Curriculum SSOT:** `src/ml_saham/chapters/registry.py` (chapter number, slug, phase).  
   - **Challenge SSOT:** `ENGINE_FACTORS` in `src/ml_saham/eval/challenge.py` (screener / signal / risk / market_context / other).

5. **No silent weak challenge fallbacks**  
   - Prefer hard failure + install hint (`pip install -e ".[ml]"`) over a degraded model that would lie about beating a baseline.  
   - Learning-only paths may stay on core sklearn; challenge may require optional ML deps.

6. **Product language by axis**  
   | Axis | Learner-facing copy language |
   |------|------------------------------|
   | **Challenge** (primary) | **English** — `challenge` / `compare` titles, tables, metrics labels, export reports, engine audit banners |
   | **Learning** (secondary) | **Indonesian** — `explore` / curriculum narrative, teaching caveats, chapter “Masalah / Opsi / Caveat” prose |

   Shared rules:
   - CLI **command names, flags, topic slugs, code identifiers** stay English on both axes.  
   - Finance/ML technical terms may stay English inside ID learning copy (existing habit).  
   - Global disclaimers may remain bilingual or ID where legally clearer (“bukan saran…”); challenge **scoreboard/metrics body** stays English.  
   - New challenge work must not add Indonesian as the default UI language for audit output.

7. **Boundaries unchanged**  
   - Read-only SQLite from `ai-saham` data; no `ai-saham` Python imports; no scrapers; artifacts never auto-promote into production configs.

---

## Consequences

### Positive

- Roadmap, tests, and agent work optimize for engine audits first.  
- README and CLI mental model match maintainer intent.  
- Clear rule when curriculum docs disagree with challenge design.

### Trade-offs

- Plain `pip install -e .` may not run full challenge suite.  
- Some `demo` commands stay thin or challenge-only — curriculum “completionism” is not a goal.  
- Engine map and chapter list can drift; both must be updated when adding factors.  
- Bilingual product: challenge strings migrate to English over time; learning copy stays ID — mixed CLI output is expected until challenge modules are fully localized.

### Follow-ups

- [x] Challenge acceptance checklist / CI with `.[ml]` — see [challenge_acceptance.md](../../challenge_acceptance.md) and `.github/workflows/ci.yml`.  
- [x] Ideal challenge system design — **[ADR-002](./ADR-002-ideal-challenge-system.md)** (replaces chapter-loop runner as design target).  
- Migrate implementation to ADR-002 PolicySpec runner (open).  
- Whether `demo` should alias to challenge inspect (open; ADR-002 prefers not).

---

## Rejected alternatives

| Alternative | Why rejected |
|-------------|--------------|
| Learning-first (curriculum spine, challenge as extra) | Undervalues the real use case: tuning `ai-saham` |
| Soft sklearn fallbacks so every `demo`/`challenge` always “works” | Fake wins; unsafe for weight/policy decisions |
| Merge axes into one “demo = challenge” command | Blurs teaching vs audit; harder scoreboard honesty |
| Merge `challenge` and `compare` into one command | Batch audit vs single-factor experiment need different UX and knobs |
| Treat `compare` as pure ML, unrelated to `ai-saham` | Undervalues the real use case (challenging engine-like baselines) |
| Claim every compare is a 1:1 engine knob mirror | Some labs are hygiene/honesty (coin-flip, anomaly methods); still on ai-saham data plane |
| Auto-write `ai-saham` config from challenge winners | Out of scope; human review required |
| Single language for whole product (all-ID or all-EN) | Learning needs ID pedagogy; challenge needs EN audit/export clarity |

---

## Implementation notes

```text
challenge  →  ENGINE_FACTORS groups  →  each slug.run_compare(defaults)  →  rollup export
compare    →  one slug.run_compare(--baseline, --against)  →  full lines + optional artifact
explore    →  teach problem (no heavy train required)  [ID]
demo       →  optional illustration; may defer to challenge path
```

Engine groups (challenge SSOT): `screener`, `signal_engine`, `risk_engine`, `market_context`, `other_aspects`.
