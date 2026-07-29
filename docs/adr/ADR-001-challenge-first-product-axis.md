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

2. **Learning is secondary onboarding**  
   - `explore` / `demo` / chapter numbers teach *why* a factor exists so challenge output is interpretable.  
   - Curriculum order and registry numbers remain useful, but **do not outrank engine maps** when priorities conflict.  
   - `demo` may refuse or redirect to challenge/compare for engine-critical factors; that is acceptable if messaging is clear.

3. **Two sources of truth, different jobs**  
   - **Curriculum SSOT:** `src/ml_saham/chapters/registry.py` (chapter number, slug, phase).  
   - **Challenge SSOT:** `ENGINE_FACTORS` in `src/ml_saham/eval/challenge.py` (screener / signal / risk / market_context / other).

4. **No silent weak challenge fallbacks**  
   - Prefer hard failure + install hint (`pip install -e ".[ml]"`) over a degraded model that would lie about beating a baseline.  
   - Learning-only paths may stay on core sklearn; challenge may require optional ML deps.

5. **Product language by axis**  
   | Axis | Learner-facing copy language |
   |------|------------------------------|
   | **Challenge** (primary) | **English** — `challenge` / `compare` titles, tables, metrics labels, export reports, engine audit banners |
   | **Learning** (secondary) | **Indonesian** — `explore` / curriculum narrative, teaching caveats, chapter “Masalah / Opsi / Caveat” prose |

   Shared rules:
   - CLI **command names, flags, topic slugs, code identifiers** stay English on both axes.  
   - Finance/ML technical terms may stay English inside ID learning copy (existing habit).  
   - Global disclaimers may remain bilingual or ID where legally clearer (“bukan saran…”); challenge **scoreboard/metrics body** stays English.  
   - New challenge work must not add Indonesian as the default UI language for audit output.

6. **Boundaries unchanged**  
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
- Per-engine scoreboard contracts (open).  
- Whether `demo` should alias to single-factor challenge for mapped slugs (open).

---

## Rejected alternatives

| Alternative | Why rejected |
|-------------|--------------|
| Learning-first (curriculum spine, challenge as extra) | Undervalues the real use case: tuning `ai-saham` |
| Soft sklearn fallbacks so every `demo`/`challenge` always “works” | Fake wins; unsafe for weight/policy decisions |
| Merge axes into one “demo = challenge” command | Blurs teaching vs audit; harder scoreboard honesty |
| Auto-write `ai-saham` config from challenge winners | Out of scope; human review required |
| Single language for whole product (all-ID or all-EN) | Learning needs ID pedagogy; challenge needs EN audit/export clarity |

---

## Implementation notes

```text
challenge  →  load_chapter(slug).run_compare(...)  →  metrics / artifacts
compare    →  one-factor deep audit
explore    →  teach problem (no heavy train required)
demo       →  optional illustration; may defer to challenge path
```

Engine groups (challenge SSOT): `screener`, `signal_engine`, `risk_engine`, `market_context`, `other_aspects`.
