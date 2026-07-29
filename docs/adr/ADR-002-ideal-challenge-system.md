# ADR-002: Ideal Challenge System (greenfield)

**Status:** Accepted (design target — replaces current chapter-loop runner)  
**Date:** 2026-07-29  
**Supersedes (implementation intent):** ad-hoc `ENGINE_FACTORS` → `run_compare` slug dump in `eval/challenge.py`  
**Related:** [ADR-001](./ADR-001-challenge-first-product-axis.md) · [engine_factor_map.md](../engine_factor_map.md) · ai-saham label contracts (e.g. ADR-056 accum path; signal horizon tags)

---

## Context

ADR-001 locked **challenge > learning** and **compare vs challenge** as product roles.  
The **current implementation** (curriculum slugs + generic baselines like equal-weight/elastic-net + silent JSON errors) is not fit for purpose:

- Challenges **policies**, not “ML chapter demos.”
- Baselines must mean **production / exported ai-saham policy**, not a random sklearn name.
- Metrics and horizons must match **ai-saham decision contracts**.
- We also need a first-class way to ask: **does this factor/parameter predict the label enough to keep using it?** (keep / drop / demote).

This ADR defines the **ideal challenge system** as the implementation north star. Shipping may be incremental; behavior must converge here, not to the old loop.

---

## Decision

### 1. What a challenge is

A **challenge** is a **gated, protocol-fixed, production-baseline tournament** over an **ai-saham policy** (or policy component), producing a **versioned verdict + artifact**.

```text
H0: Production policy P is not worse than challenger C
    under protocol R (universe, horizon, costs, PIT, sample).
```

If H0 cannot be stated, it is not a challenge.

**Never auto-promote** winners into `ai-saham` configs. Output = human decision support only.

### 2. Split from learning

| Product | Registry | Language | Gate for “shipped”? |
|---------|----------|----------|---------------------|
| **Challenge** | Policy / ChallengeSpec registry | **English** | Spec + runner + protocol + artifact |
| **Learning** | Curriculum chapters (`registry.py`) | **Indonesian** explore | Optional; never blocks challenge ship |

Curriculum modules may reuse metrics libraries; they **do not** define the challenge catalog.

### 3. Core objects

#### 3.1 `PolicySnapshot` (baseline)

Frozen “what production does / would do”:

- `policy_id` + version / config hash  
- decision type: `rank` | `score` | `gate` | `size` | `label`  
- feature/parameter contract (names only)  
- PIT / availability rules  

**Default baseline id:** `production` (or `exported-policy@<hash>`).  
Not `elastic-net` unless that *is* production.

Sources (preferred order): observation payloads that embed configured weights; exported JSON/YAML snapshots from ai-saham; documented constant maps. Still **no import of ai-saham Python packages** (ADR-001 boundary).

#### 3.2 `Challenger`

Named alternative with the **same decision type** as baseline, e.g.:

- `ridge_reweight`, `equal_sleeves`, `drop_factor:<name>`, `gate_off:<gate>`, `threshold_shift:±10%`, `macro_off`

Prefer **ablations and reweights** over exotic models when the question is “keep this sleeve?”

#### 3.3 `Protocol` (evaluation law)

Versioned. Changing protocol ⇒ new run identity.

| Knob | Rule |
|------|------|
| Universe | Explicit list / LQ45∩cache contract |
| **Horizons** | Must match ai-saham contracts for that path (see §4) |
| Primary horizon | Exactly one primary metric horizon per protocol |
| Costs | Gross + mandatory disclaimer banner; optional haircut scenario |
| Split | Purged / walk-forward time splits — **no random row shuffle** for path labels |
| Labels | Typed by decision (forward return, open path, gate correctness, …) |
| PIT | `fetched_date ≤ as_of`; observation readiness rules |
| Min N | Hard `BLOCKED_DATA` if insufficient — no fake IC |

#### 3.4 `ChallengeSpec`

```text
challenge_id: screener.accum.score_weights.v1
engine: screener
policy: production.accum_score@…
challengers: [ridge_reweight, equal_sleeves, drop_factor:flow]
protocol: accum_path_v1          # primary H=10 sessions, also report 3 & 20
tracks: [policy_tournament, factor_validity]
success: beat production on primary without worse tail / turnover bound
```

#### 3.5 `ChallengeResult`

```text
status: WIN | LOSE | INCONCLUSIVE | BLOCKED_DATA | BLOCKED_POLICY
primary_metric + CI / fold table
secondary: turnover, tail, gate FP cost, …
factor_validity: (optional track — see §5)
verdict_notes: promote? no — checklist
artifact_id: immutable pack (spec hash, data range, metrics, diffs)
```

`INCONCLUSIVE` and `BLOCKED_*` are first-class — not buried as `"error": "..."`.

---

## 4. Horizons (aligned with ai-saham)

Challenge protocols **must not invent** horizons ad hoc.

### 4.1 Signal / alpha path tags (ai-saham semantic contract)

ai-saham defines execution-style horizons including:

| Tag | Meaning (ai-saham) | Sessions (nominal) |
|-----|--------------------|--------------------|
| `TACTICAL_3D` | Tactical path | **3** |
| `SWING_10D` | Swing path | **10** |
| `ACCUM_20D` | Longer accum path | **20** |

### 4.2 Accum research / corpus (ai-saham ADR-056 family)

- Accum path observations stamp **primary** grade horizon **`accum_10d`** (10 sessions).  
- Operators: lookbacks (e.g. 7/30/90) are **features**, not label horizons.  
- **Primary label for accum challenges: 10 sessions** unless a spec explicitly targets tactical/accum_20d.

### 4.3 Accumulation audit measurement config

`config/accumulation_audit.yaml` currently emits forward close-to-close horizons **`[5, 10, 20]`** for audit records (measurement block).  
Protocols that read **audit tables** must declare whether they use that set or the **3 / 10 / 20** signal tags — do not mix silently.

### 4.4 Protocol requirement

Every accum-related `Protocol` documents:

```text
horizons_report: [3, 10, 20]   # or [5, 10, 20] if audit-table protocol
primary_horizon: 10            # DEFAULT for accum path
label_contract: accum_10d | tactical_3d | accum_20d | audit_close_N
```

**Default primary for screener accum policy challenges: `H = 10`.**  
Always **report** secondary horizons (3 and 20, or 5 and 20) for stability; **win/lose uses primary only**.

Pre-open protocols use **session / open-path** contracts (not 10d close) — separate protocol family.

---

## 5. Factor & parameter validity (keep / drop)

This is a **first-class challenge track**, not an afterthought.

### 5.1 Question (correct terms)

| Term | Meaning |
|------|---------|
| **Predictive validity** | Does the factor (or parameter setting) carry information about the **label** under protocol R? |
| **Univariate association** | Rank IC / correlation / mutual info of factor vs forward label (with PIT) |
| **Marginal contribution** | Does removing or shuffling the factor **hurt** the production policy (ablation / permutation)? |
| **Redundancy** | Is it collinear with an existing sleeve (drop candidate even if univariate OK)? |
| **Stability** | Does validity hold across folds / regimes? |

User-facing language: **“Is this factor still earning its place in the policy?”**

### 5.2 Two related but different tracks

| Track | Question | Typical baseline | Typical against |
|-------|----------|------------------|-----------------|
| **A. Policy tournament** | Is full policy P better than alternative policy C? | `production` | `ridge_reweight`, new weight map |
| **B. Factor validity** | Should we **keep, demote, or drop** factor *f* (or param *θ*)? | `production` (with *f*) | `drop_factor:f`, `permute_factor:f`, `threshold_shift` |

Both use the same Protocol and labels.  
**Do not** drop a factor from production solely on univariate IC; require **ablation and stability**.

### 5.3 Factor-validity outcomes

| Verdict | Meaning |
|---------|---------|
| **KEEP** | Ablation hurts primary metric (or risk) materially; stable across folds |
| **DEMOTE** | Weak / unstable; keep as diagnostic only (not score authority) |
| **DROP_CANDIDATE** | Ablation neutral/helps; low univariate validity; or pure redundancy — **human** may remove |
| **INCONCLUSIVE** | N too small, regime-dependent, or collinearity unresolved |

Still **no auto-edit** of ai-saham config.

### 5.4 Minimum methods (ideal library)

1. **Univariate:** rank IC of factor vs label at primary horizon (+ report secondaries).  
2. **Permutation / ablation:** zero or shuffle factor inside production score; Δ metric.  
3. **Partial / residual:** optional — IC after residualizing on other sleeves.  
4. **Parameter sweep:** for thresholds/weights, one-at-a-time ± grid under same protocol.

### 5.5 CLI (target)

```bash
# Policy tournament
ml-saham challenge run screener.accum.score_weights \
  --against ridge_reweight

# Factor keep/drop
ml-saham challenge factor screener.accum --factor institutional_flow
ml-saham challenge factor screener.accum --factor smc_oil --track diagnostic

# Parameter
ml-saham challenge param risk.bandar_gate --param threshold --grid ...
```

Reports English; include horizons table (3 / 10 / 20) with **primary = 10** for accum.

---

## 6. CLI surface (target product)

```text
ml-saham vet                         # data-plane gate → PASS/FAIL
ml-saham challenge list              # PolicySpecs, not curriculum slugs
ml-saham challenge run <policy_id>   # tournament vs production
ml-saham challenge inspect <policy_id>  # deep lab (replaces muddy compare)
ml-saham challenge factor …          # keep/drop validity track
ml-saham challenge param …           # parameter sensitivity
ml-saham challenge engine <name>     # portfolio of PolicySpecs + rollup
ml-saham challenge report <run_id>   # reopen artifact
```

`compare` may remain a **deprecated alias** of `challenge inspect` during migration.

### Engine portfolio (ideal)

`challenge engine market` = fixed set of **PolicySpecs** for Market Context — not “run these chapter modules.”

Rollup rules:

- Core policy `BLOCKED_DATA` ⇒ engine cannot be overall green  
- `WIN` requires stability (e.g. majority of folds), not one-shot IC  
- **Diagnostic** policies (e.g. sector-macro v1) on a separate track from **scoring** policies  
- Point to `challenge inspect` / `challenge factor` for the weakest row

---

## 7. Metrics by decision type

| Decision type | Primary metrics (examples) | Secondary |
|---------------|----------------------------|-----------|
| Rank / score | Rank IC @ primary H; top-quantile excess | Turnover, breadth, secondaries H |
| Gate | Precision/recall of blocks; cost of false blocks | Rate of blocks, stability |
| Size | Realized vol vs target; haircut Sharpe | Max adverse excursion |
| Regime label | Balanced accuracy / Brier vs forward stress | Transition noise |

**No single global “IC for everything.”**

---

## 8. Artifacts

Each run writes an immutable pack:

- ChallengeSpec + Protocol + policy hash  
- Data range, universe, vet summary  
- Metrics tables (all horizons; primary marked)  
- Factor-validity table when applicable  
- Weight / threshold diffs vs production  
- Fold-wise results  
- Human checklist (promote / demote / drop candidate / need more data)

English only.

---

## 9. Migration stance

| Phase | Action |
|-------|--------|
| Now | ADR-002 is **source of truth** for design; stop extending the slug-dump runner except bugfixes |
| Next | Implement `vet` + PolicySpec registry + one end-to-end accum policy challenge @ H=10 |
| Then | `challenge factor` validity track; engine portfolios |
| Last | Delete or quarantine chapter-loop `ENGINE_FACTORS` batch as non-product |

Learning chapters may keep `run_compare` for pedagogy; **product challenge** must not depend on them.

---

## Consequences

### Positive

- Challenges answer real policy questions (weights, gates, keep/drop factors).  
- Horizons match ai-saham (3 / 10 / 20; **primary 10 for accum**).  
- Honest outcomes: WIN/LOSE/INCONCLUSIVE/BLOCKED.  
- Clear path to drop useless factors without cargo-cult ML.

### Trade-offs

- Requires policy export/snapshot discipline from ai-saham.  
- Larger upfront design than “loop chapters.”  
- Some curriculum compares become non-authoritative for promotion decisions.

### Follow-ups

- [ ] ADR or schema for PolicySnapshot export from ai-saham  
- [x] Implement Protocol registry (`accum_path_v1`) + first production challenge: **accum score weights @ H=10** (`src/ml_saham/challenge/`, `ml-saham challenge run`)  
- [x] Factor-validity CLI (`challenge factor`) — univariate + drop ablation, enabled sleeves only
- [x] Second policy: **pre-open IEV rank** (`screener.pre_open.iev_rank`, protocol `pre_open_session_v1`, same-session open→close)
- [x] Pre-open **observation** policy (`screener.pre_open.directional_score`, raw_score + features; data-tolerant BLOCKED when thin)
- [ ] Engine portfolios on PolicySpecs only  
- [ ] Retire chapter-loop challenge CLI (`challenge legacy`)  

---

## Rejected alternatives

| Alternative | Why rejected |
|-------------|--------------|
| Keep curriculum slug dump as challenge product | Wrong object; wrong baselines; unmaintainable |
| Univariate correlation alone to drop factors | Ignores ablation, redundancy, stability |
| Single horizon (e.g. only 5d) for all engines | Fights ai-saham 3/10/20 and accum_10d primary |
| Auto-write ai-saham YAML on WIN | Out of scope; human promotion only |
| Require full ID curriculum before shipping a policy challenge | Violates challenge-first (ADR-001) |

---

## One-line summary

> **Challenge = versioned tournament of ai-saham policies (and factor keep/drop) under fixed protocols — primary accum horizon 10 sessions, report 3 and 20 — with English artifacts and no auto-promotion; learning stays optional and separate.**
