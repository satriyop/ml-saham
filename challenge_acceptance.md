# Challenge acceptance (ADR-001)

Definition of **done** for the challenge axis of `ml-saham`.  
Product decision: [docs/adr/ADR-001-challenge-first-product-axis.md](./docs/adr/ADR-001-challenge-first-product-axis.md)  
Engine map SSOT: `src/ml_saham/eval/challenge.py` → `ENGINE_FACTORS`

Curriculum acceptance (historical): [mvp_acceptance.md](./mvp_acceptance.md) · [v1_1_acceptance.md](./v1_1_acceptance.md) · [phase2_acceptance.md](./phase2_acceptance.md)

---

## Global

- [x] Challenge outranks curriculum polish when priorities conflict (ADR-001)  
- [x] Every slug in `ENGINE_FACTORS` is loadable and implements **`run_compare`**  
- [x] Fixture suite runs full `run_full_challenge` with **zero factor errors**  
- [x] CLI: `ml-saham challenge all` exports JSON + Markdown  
- [x] No silent weak models that invent wins: hard fail or documented fallback (e.g. ridge when XGBoost missing)  
- [x] CI installs `pip install -e ".[ml,dev]"` and runs challenge + core tests  
- [ ] **Language:** new challenge / compare learner-facing strings are **English** (learning `explore` stays Indonesian) — migrate legacy ID challenge copy over time (ADR-001 §5)  

---

## Engine groups

| Group | Factors | Gate |
|---|---|---|
| `screener` | pre-open + accum factors | `challenge screener` / scenarios |
| `signal_engine` | meta-ensemble, factor-score, … | `challenge engine --category signal` |
| `risk_engine` | vol sizing, portfolio, gates, distress | `challenge engine --category risk` |
| `market_context` | regime, breadth, nowcast, micro | `challenge engine --category market` |
| `other_aspects` | clusters, graph, WF, RL, … | `challenge other` |

---

## Local commands

```bash
pip install -e ".[ml,dev]"
pytest tests/test_challenge_acceptance.py -q
ml-saham --db "$ML_SAHAM_DB" challenge all --export-md /tmp/challenge.md
```

---

## Status

**Challenge acceptance suite shipped** (fixture-level).  
Maintainer DB smoke remains optional and environment-specific.
