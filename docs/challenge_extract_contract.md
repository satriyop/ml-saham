# Challenge extract contract (ship gate)

**Rule:** a product panel is **not shipped** until it passes a **live-shaped contract**, not only `build_mvp_fixture`.

This doc is the systematic prevention layer after ADR-056 / open_30m / NCP / multi-fold failures.  
Related: [data_contract.md](../data_contract.md) (paths/units table) · [challenge_product.md](./challenge_product.md) · goldens `tests/fixtures/golden/`.

---

## Principle

| Allowed | Not allowed |
|---------|-------------|
| Fixture for *wiring* smoke | Fixture as the *only* payload contract |
| Legacy root-level fallback | Root-only extract that is empty on 100% of live rows |
| Curriculum toy math in `chapters/` | Same math as product PolicySpec features without re-derivation |
| `INCONCLUSIVE` / provisional notes | `WIN` on a single OOS fold |

---

## Contract template (every new / changed panel)

Copy into the PR description or operator note before merge:

```text
Policy / diagnostic id:
Payload path (primary):
Payload path (legacy fallback, if any):
Label y (definition + horizon):
Benchmark (same horizon as y?):
Units (e.g. *_return_pct = percent points → /100):
Capture / PIT (NCP window, shared.market_context, …):
Missing blob behavior (None/skip vs invent zeros — prefer None):
Golden fixture file under tests/fixtures/golden/:
Contract test (calls shipped extract_* / _pick_* / _verdict):
```

---

## PR / agent checklist

For any change under `src/ml_saham/challenge/panel*.py`, policies, or diagnostics:

- [ ] Golden JSON added/updated under `tests/fixtures/golden/` from **real** structure (redacted OK)
- [ ] Test calls **shipped** extract helpers (not a re-implemented parser)
- [ ] Empty / root-only path is **not** all-clear and **not** silent zero-rate success
- [ ] Label **y** and benchmark share one horizon
- [ ] Units unconditional (no `|x|≤1 ⇒ fraction` heuristics)
- [ ] Capture rule: NCP / decision clock / bound context preferred over “largest / latest table row”
- [ ] WIN still requires `min_folds_for_win ≥ 2` (provisional single-fold = INCONCLUSIVE)
- [ ] No curriculum-only math as product features without field-meaning re-derivation
- [ ] Row added/updated in `data_contract.md` extract-contracts table when path is new
- [ ] `./scripts/check_challenge_contracts.sh` passes locally

---

## Local + CI gate

```bash
# Always (no maintainer DB required)
./scripts/check_challenge_contracts.sh

# Optional when ML_SAHAM_DB or default ai-saham DB exists
pytest tests/test_challenge_live_smoke.py -q -m live_db
```

`check_challenge_contracts.sh` runs:

1. **Pattern bans** (known regressions: IEV/IEP ratio assignment, old pct heuristic)
2. **Protocol gate** (`min_folds_for_win ≥ 2`)
3. **Golden presence** under `tests/fixtures/golden/`
4. **pytest** `test_challenge_payload_contracts.py` + `test_challenge_verdict_folds.py`

CI (`.github/workflows/ci.yml`) runs the same script early in the challenge job.

---

## Definition of shipped

| Item | Gate |
|------|------|
| Extract path | Golden contract test green |
| Units / horizon / PIT | Asserted in contracts or notes + code |
| Tournament status | Multi-fold WIN rules enforced |
| Curriculum | May lag; never defines product feature meaning |

---

## Anti-patterns (do not reintroduce)

| Anti-pattern | Symptom |
|--------------|---------|
| Top-level `payload["signal"]` only | 0 rows / false empty |
| Top-level `trade_setup` only | `block_rate_raw=0%` false-clear |
| Largest IEV batch of the day | Post-open / early non-NCP |
| open→09:30 stock − full-day IHSG | Mixed horizons |
| `|x|≤1` → treat as fraction | −0.6173% becomes −61.73% |
| Table MCE by date last-wins | Wrong snapshot vs capture |
| Single-fold WIN | Fake promotion readiness |
| `iev/iep - 1` as imbalance | Volume÷price nonsense |

---

## Curriculum wall

| Layer | Role |
|-------|------|
| `src/ml_saham/chapters/` | Pedagogy; may use simplified demos |
| `src/ml_saham/challenge/` | Product authority; live-shaped contracts only |

---

## One-line summary

> **No new product panel without a golden + shipped-extractor test; CI runs the contract script every time.**
