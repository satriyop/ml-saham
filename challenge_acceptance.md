# Challenge acceptance (ADR-002)

Definition of **done** for the challenge product axis of `ml-saham`.  
Product decision: [docs/adr/ADR-002-ideal-challenge-system.md](./docs/adr/ADR-002-ideal-challenge-system.md) · map: [docs/challenge_product.md](./docs/challenge_product.md)

**Product SSOT:** `src/ml_saham/challenge/` — PolicySpecs, protocols, runner, engines, health.  
Curriculum phase checklists (historical, local only): `archive/mvp_acceptance.md` · `archive/v1_1_acceptance.md` · `archive/phase2_acceptance.md` (gitignored `archive/`)

---

## Global

- [x] Challenge outranks curriculum polish when priorities conflict (ADR-001)  
- [x] Policy registry loads every registered `policy_id` with a known protocol  
- [x] Engine portfolio `screener` covers registered PolicySpecs only  
- [x] CLI: `challenge list` / `run` / `engine` / `factor` / `health` / `champion` / `promote-packet`  
- [x] CLI: `challenge diagnostic list` / `run` / `health` (display / promote-candidate; never Action)  
- [x] Chapter-loop product surface **retired** (`challenge legacy` removed; no `ENGINE_FACTORS` batch)  
- [x] Honest statuses: WIN / LOSE / INCONCLUSIVE / BLOCKED_* (no silent fake wins)  
- [x] CI installs `pip install -e ".[ml,dev]"` and runs challenge + core tests  
- [ ] **Language:** new challenge learner-facing strings are **English** (learning `explore` stays Indonesian)

---

## Product surface

| Surface | Role | Gate |
|---------|------|------|
| Policy registry | Frozen PolicySnapshots | `list_policy_ids` / `load_policy` |
| Protocols | Horizons, folds, win margin | `accum_path_v1`, `pre_open_session_v1` |
| `challenge run` | Production vs challenger (tune) | fixture + maintainer DB |
| `challenge engine` | PolicySpec portfolio rollup | `screener` ± scenario |
| `challenge factor` | KEEP / DEMOTE / DROP_CANDIDATE | accum sleeves |
| `challenge diagnostic` | KEEP_DISPLAY / DEMOTE_DISPLAY / PROMOTE_CANDIDATE | explain-only bags (v1: MCE, sector) |
| `challenge health` | Control tower pack | engine ± champion ± factors |
| `vet` / `doctor --deep` | Data-plane gate | fixture + maintainer DB |

Curriculum `learn compare <slug>` remains for learning labs — **not** promotion authority.

---

## Local commands

```bash
pip install -e ".[ml,dev]"
pytest tests/test_challenge_acceptance.py -q
ml-saham challenge list
ml-saham --db "$ML_SAHAM_DB" challenge run screener.accum.score_weights --against equal_sleeves
ml-saham --db "$ML_SAHAM_DB" challenge engine screener --scenario accum
ml-saham --db "$ML_SAHAM_DB" challenge health
```

---

## Status

**ADR-002 acceptance suite** (fixture-level).  
Maintainer DB smoke remains optional and environment-specific.  
Pre-ADR-002 chapter-loop batch (`eval/challenge.py` / `challenge legacy`) is **retired**.
