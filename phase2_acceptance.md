# Phase-2 acceptance (Ch.8, 10–20 + optional Ch.20 sandbox)

Definition of **done** for Phase 6 curriculum ship.  
Data: [data_contract.md](./data_contract.md) · Roadmap: [roadmap.md](./roadmap.md)

**Sign-off:** 2026-07-23 — fixture suite + maintainer DB smoke (earnings/corp/IEV/labels present; headlines soft-missing → synthetic Ch.10).  
**Numbering note (2026-07-29):** registry is SSOT. Phase-2 core topics include Ch.8 `survival-analysis`, Ch.10–19 curriculum chapters, and optional Ch.20 `rl-sandbox`. Ch.9 is v1.1 (`volume-anomaly`).

---

## Global

- [x] `doctor` reports **Phase-2 data** (earnings, corp, IEV, labels hard; regime/candidates/headlines soft)  
- [x] `required_data=phase2` gated on `phase2_hard_ok`  
- [x] Phase-2 chapters implemented (`explore` + `demo`) including `survival-analysis`, `nowcasting`, `broker-network` loadable via CLI  
- [x] Ch.18 (`pre-open-rank`) uses **open-session** scoreboard banners  
- [x] No `ai-saham` Python imports  

---

## Per cluster

| Cluster | Topics | Done |
|---|---|---|
| Survival | `survival-analysis` | [x] time-to-event lab |
| Text | `headline-tone` | [x] synthetic corpus when no headline table |
| Risk | `volatility-sizing`, `market-regime` | [x] |
| Honesty | `walk-forward` | [x] time split + leakage lesson |
| Portfolio | `portfolio-small` | [x] |
| Events | `corp-events`, `earnings-surprise` | [x] |
| Nowcast | `nowcasting` | [x] mixed-frequency panel |
| Open session | `pre-open-rank` | [x] IEV |
| Pipeline | `research-pipeline` | [x] |
| Graph | `broker-network` | [x] centrality / PageRank |
| Optional | `rl-sandbox` | [x] epsilon-greedy toy |

---

## Status

**Phase 6 accepted** at curriculum-demo quality (not production trading). Extended chapters 21–44 follow the same contract.
