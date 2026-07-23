# Phase-2 acceptance (Ch.9–17 + optional Ch.18)

Definition of **done** for Phase 6 curriculum ship.  
Data: [data_contract.md](./data_contract.md) · Roadmap: [roadmap.md](./roadmap.md)

**Sign-off:** 2026-07-23 — fixture suite + maintainer DB smoke (earnings/corp/IEV/labels present; headlines soft-missing → synthetic Ch.9).

---

## Global

- [x] `doctor` reports **Phase-2 data** (earnings, corp, IEV, labels hard; regime/candidates/headlines soft)  
- [x] `required_data=phase2` gated on `phase2_hard_ok`  
- [x] Chapters 9–17 implemented (`explore` + `demo` + deepdive stub); Ch.18 optional sandbox  
- [x] Ch.16 uses **open-session** scoreboard banners  
- [x] No `ai-saham` Python imports  

---

## Per cluster

| Cluster | Topics | Done |
|---|---|---|
| Text | `headline-tone` | [x] synthetic corpus when no headline table |
| Risk | `volatility-sizing`, `market-regime` | [x] |
| Honesty | `walk-forward` | [x] time split + leakage lesson |
| Portfolio | `portfolio-small` | [x] |
| Events | `corp-events`, `earnings-surprise` | [x] |
| Open session | `pre-open-rank` | [x] IEV |
| Pipeline | `research-pipeline` | [x] |
| Optional | `rl-sandbox` | [x] epsilon-greedy toy |

---

## Status

**Phase 6 accepted** at curriculum-demo quality (not production trading). Next optional: Phase 7 UX extras only if needed.
