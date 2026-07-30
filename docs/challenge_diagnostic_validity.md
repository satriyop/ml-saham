# Product: Diagnostic validity track

**Status:** Shipped (v1 — two bags)  
**Date:** 2026-07-30  
**Axis:** Challenge (third **purpose**, not a fourth top-level product)  
**SSOT:** `src/ml_saham/challenge/diagnostic_validity.py` · `src/ml_saham/challenge/diagnostics/`  
**Related:** [challenge_product.md](./challenge_product.md) · [challenge_factor_validity.md](./challenge_factor_validity.md) · [challenge_product_roadmap.md](./challenge_product_roadmap.md) · ai-saham ADR-057 · `evidence_diagnostic_factor_accum.md`

**Never auto-promotes into ai-saham. Never sets TradeSetup Action authority.**

---

## One-line product

> **Diagnostic validity** = versioned, protocol-fixed audit of **explain-only bags**: are they calibrated enough to **keep on the desk**, **demote/hide**, or **nominate for production wiring** — without treating them as score/Action SSOT.

---

## Final product (what you ship)

A **third purpose under Challenge**, next to **tune** and **champion**:

```text
ml-saham
└── Challenge (primary axis)
      ├── tune              production policy: weights / factors / gates
      ├── champion          better score rule than production
      └── diagnostic        explain-only bags: display + promote-candidate
            list · run · report · (optional) health slice
```

### User-facing promise

| You want to know… | Track |
|-------------------|--------|
| Should this **production sleeve/weight** stay? | **tune** (`challenge run` / `factor`) |
| Is there a **better scorer** than production? | **champion** |
| Is this **diagnostic panel** worth showing / worth promoting later? | **diagnostic** ← this product |

### Operator commands (v1 shipped)

```bash
# Catalog of registered diagnostic bags (not production PolicySpecs)
ml-saham challenge diagnostic list

# Features in a bag
ml-saham challenge diagnostic run mce.screen_display --list-features

# One feature or whole bag
ml-saham challenge diagnostic run mce.screen_display --feature regime_score
ml-saham challenge diagnostic run mce.screen_display --all
ml-saham challenge diagnostic run sector.peer_context --feature sector_context_score
ml-saham challenge diagnostic run sector.peer_context --all

# Batch pack for weekly review
ml-saham challenge diagnostic health --scenario accum
```

English artifact pack under e.g.:

```text
artifacts/challenge/diagnostic/<diagnostic_id>/<timestamp>/
  manifest.json      # bag id, version, protocol, data range, hash
  metrics.json       # IC / strata / residual / stability
  summary.md         # verdict + plain-language notes
```

Optional export: `--export-json` / `--export-md` (same pattern as tune).

---

## Product objects

### 1. `DiagnosticSpec` (baseline = “what the desk shows”)

Frozen snapshot of an **explain-only** producer/bag — **not** a production PolicySpec.

| Field | Meaning |
|-------|---------|
| `diagnostic_id` | Stable id, e.g. `mce.screen_display`, `sector.peer_context`, `cq.valuation_bag` |
| `version` / `hash` | Frozen extract contract |
| `engine` | Owning surface: `mce` · `sector` · `cq` · `institutional` · `setup_diag` · … |
| `scenario` | `accum` (v1); pre-open later if needed |
| `kind` | Always **diagnostic** (ADR-057) — code enforces no Action claim |
| `features[]` | Named fields extractable from observations / caches |
| `protocol_id` | Label law (reuse or diagnostic-specific) |
| `source_ref` | ai-saham producer / config path (docs only; no Python import) |

Registry: e.g. `src/ml_saham/challenge/diagnostics/*.v1.json` + loader (parallel to `policies/`, **separate namespace**).

### 2. Protocol (evaluation law)

Same honesty rules as ADR-002 (folds, min N, `BLOCKED_DATA`).  
**Default v1:** reuse path labels already used for accum/pre-open where comparable.

| Protocol | Primary use |
|----------|-------------|
| `accum_path_v1` | Conditional excess vs IHSG @ H=10 (report 3/10/20) |
| `pre_open_session_v1` | Same-session open→close (if bag is pre-open diagnostic) |
| Later: `diagnostic_event_v1` | Event-style bags (corp action window, etc.) if needed |

Label is about **calibration of the bag**, not “production score beats challenger.”

### 3. Methods (minimum viable product)

| Method | Question |
|--------|----------|
| **Univariate / stratum** | When bag is high/on, is forward outcome different? |
| **Residual / incremental** | After **production score** (e.g. Accum sleeves or signal raw) is controlled, does the bag still explain residual label? |
| **Redundancy** | Collinear with production evidence already on the desk? |
| **Stability** | Holds across folds / regimes? |
| **Coverage** | Enough non-null rate to trust the panel? |

v1 does **not** require learned models. Champion-style fit is out of scope for diagnostic track.

### 4. Verdicts (final product language)

**Different vocabulary from production factor KEEP/DEMOTE** so agents cannot confuse them.

| Verdict | Meaning | Human next step |
|---------|---------|-----------------|
| **`KEEP_DISPLAY`** | Calibrated enough + non-redundant enough to keep on desk | Leave as diagnostic |
| **`DEMOTE_DISPLAY`** | Weak / unstable / noisy | Hide, collapse, or redesign bag |
| **`DROP_DISPLAY`** | No calibration + low coverage or pure noise | Remove from default UI path (human in ai-saham) |
| **`PROMOTE_CANDIDATE`** | Incremental signal **and** residual value after production score | **Eligible** to design a real PolicySpec / wiring proposal — **not** auto-wired |
| **`INCONCLUSIVE`** | Conflicting folds / thin N | Collect more captures |
| **`BLOCKED_DATA`** / **`BLOCKED_SPEC`** | Missing fields or unknown id | Fix corpus / spec |

Hard rule in product copy and promote-packet:

> **`PROMOTE_CANDIDATE` ≠ change production.**  
> Next step = write a **tune** PolicySpec H0 (or DecisionPolicy wiring), then `challenge run` / `factor`.  
> Diagnostic track **never** emits WIN/LOSE against production weights.

### 5. Explicit non-outputs

| Must not claim | Why |
|----------------|-----|
| WIN/LOSE vs production Accum/signal policy | Wrong decision type |
| Action ENTER accuracy | Desk composer is separate product (roadmap P4) |
| Auto-edit of ai-saham YAML | BOUNDARY |
| “This diagnostic is now production evidence” | Only human + production config change |
| Curriculum `learn compare` authority | Still pedagogy only |

---

## How it sits next to tune & champion

| | **Tune** | **Champion** | **Diagnostic** |
|--|----------|--------------|----------------|
| Object | `PolicySpec` (production decision) | Same | `DiagnosticSpec` (explain-only bag) |
| Baseline | production policy | production score | “panel as shown” / bag fields |
| Question | Factor/weights/gates OK? | Better scorer? | Keep display / demote / promote-candidate? |
| Typical metric | Rank IC, ΔIC ablation | Rank IC of learned score | Stratum + residual IC + coverage |
| If strong | Maybe retune production | Maybe adopt scorer | Maybe **start** a production policy design |
| Promote-packet | Weight/factor checklist | Scorer checklist | Display keep/hide **or** “open PolicySpec design” |
| Action authority | Indirect (policy knobs) | Indirect | **Never** |

```text
Diagnostic PROMOTE_CANDIDATE
        │
        ▼
  Human designs PolicySpec / DecisionPolicy wiring
        │
        ▼
  challenge run / factor  (tune)  ← real production H0
        │
        ▼
  Human may change ai-saham config
```

---

## Catalog scope

### Shipped (v1)

| `diagnostic_id` | Engine | Features (enabled) | Extract |
|-----------------|--------|--------------------|---------|
| `mce.screen_display` | mce | regime_score, vix, eido, usd_idr, idx_trend, idx_breadth, foreign_flow | `market_context_snapshots` join by date |
| `sector.peer_context` | sector | sector_context_score, peer_breadth | observation group_contributions / peer fields |
| `institutional.accumulation_bag` | institutional | institutional_flow_score, ia_foreign_participation, ia_domestic_buy_vwap_distance | group + fingerprint |
| `company_quality.bag` | company_quality | company_quality_score, cq_valuation_score, tp_liquidity_score | group + fingerprint |

### Next bags (not shipped)

| Priority | `diagnostic_id` (illustrative) | Why next |
|----------|--------------------------------|----------|
| P2 | `setup.diagnostic_fit` | Not entry authority when setup evidence not attached |
| P2 | `corp_events.near_window` | Event calibration, not score sleeve |
| Later | `alpha_trigger`, multi-window labels, resistance flag | Only if extracts stable |

Production sleeves (cons/streak/…) stay on **`challenge factor`** — not this track.  
If a field is **both** diagnostic bag and production flag, the DiagnosticSpec notes the dual role; promote path still goes through tune for the **flag weight/penalty**.

---

## CLI surface (final)

```text
ml-saham challenge diagnostic list
ml-saham challenge diagnostic run <diagnostic_id> [--bag KEY | --all]
ml-saham challenge diagnostic health [--scenario accum]
```

Optional later:

```text
ml-saham challenge diagnostic promote-packet --from-json …
# checklist only: KEEP_DISPLAY | DEMOTE_DISPLAY | open_tune_design
```

Control tower (shipped):

```text
ml-saham challenge health --with-diagnostics
# separate section: “Diagnostics (display bags)” — never sleeve KEEP/DEMOTE
```

---

## Acceptance (v1)

- [x] `DiagnosticSpec` registry loads with hash; unknown id → `BLOCKED_SPEC`  
- [x] Four bags: MCE, sector, institutional, company_quality (fixture tests)  
- [x] Verdicts use **display/promote-candidate** language only (no WIN/LOSE)  
- [x] Reports state **ADR-057: not Action authority** on every summary  
- [x] Residual IC after accum production score control when components extract  
- [x] Artifacts: `artifacts/challenge/diagnostic/...`  
- [x] CLI: `challenge diagnostic list|run|health`  
- [x] Docs: this file + links from product/roadmap  
- [x] `--with-diagnostics` on `challenge health` (separate display section)  
- [ ] More bags (setup, corp events)  
- [ ] No ai-saham Python import; read-only SQLite (**held**)

---

## What success looks like in six months

| Outcome | Signal |
|---------|--------|
| Desk noise down | Bags with repeated `DEMOTE_DISPLAY` / `DROP_DISPLAY` get hidden or redesigned in ai-saham by human |
| No false promotion | No agent/PR treats diagnostic WIN as Accum weight change (there is no WIN) |
| Real promotions | A few `PROMOTE_CANDIDATE` → new **tune** PolicySpecs (e.g. sector breadth sleeve, flag penalty) with honest tournaments |
| Inventory stays SSOT for live Action | ai-saham `evidence_diagnostic_factor_accum.md` still owns enter composition |
| ml-saham owns offline validity | Diagnostic calibration + production policy challenges both live here, different tracks |

---

## Non-goals

- Replacing production factor validity (`challenge factor`)  
- Full Action / ENTER protocol (roadmap P4 — different product)  
- Challenging every YAML display string on day one  
- Auto-wiring diagnostics into DecisionPolicy  
- Indonesian audit copy (challenge English only)

---

## Build order (when implementing)

1. Spec schema + one bag (`mce.screen_display` or `sector.peer_context`) + `list` / `run`  
2. Verdict engine (stratum + residual + coverage) + artifacts  
3. Second bag + `diagnostic health`  
4. Wire optional `--with-diagnostics` on control tower  
5. Document promote ladder into tune (this file § how it sits next to tune)

Fits expansion roadmap as **parallel track** to P0–P2 (does not block Accum sleeve honesty; feeds **PROMOTE_CANDIDATE** into P0/P2 designs).

---

## One-line summary

> **Final product = `challenge diagnostic`: DiagnosticSpec catalog + protocol-calibrated KEEP_DISPLAY / DEMOTE_DISPLAY / DROP_DISPLAY / PROMOTE_CANDIDATE, English artifacts, never Action authority, promote only by starting a real tune PolicySpec.**
