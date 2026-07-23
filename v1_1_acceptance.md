# v1.1 acceptance

Definition of **done** for the v1.1 ship of `ml-saham` (after MVP).  
Chapters: [chapters.md](./chapters.md) · Data: [data_contract.md](./data_contract.md) · Roadmap: [roadmap.md](./roadmap.md)

**v1.1 chapters:** 5 (`cluster-peers`), 7 (`insider`), 8 (`volume-anomaly`)  
**Sign-off:** 2026-07-23 — fixture suite + maintainer DB doctor/demo smoke.

---

## Global

- [x] `ml-saham doctor` reports **v1.1 data** (sector_coverage + insider_cache, absurd-date note)  
- [x] Demo/compare for `required_data=v1_1` gated on `v1_1_hard_ok` (implies MVP hard OK)  
- [x] `ml-saham chapters` lists MVP + v1.1 by default  
- [x] Scoreboard banners + bukan-saran on demos; artifacts unless `--no-artifact`  
- [x] No `ai-saham` Python imports  

---

## Per chapter

### Ch.5 — `cluster-peers`

- [x] `explore` frames peer/similarity problem + k-means / hierarchical / PCA options  
- [x] `demo` clusters real return windows; prints members + sector context  
- [x] Deepdive stub OK  

### Ch.7 — `insider`

- [x] `explore` covers sparse events + scrub absurd dates  
- [x] `demo` uses scrubbed `insider_cache`; net BUY/SELL rule + logistic; rank IC  
- [x] Doctor surfaces usable vs absurd counts  

### Ch.8 — `volume-anomaly`

- [x] `explore` separates *how much* (volume–price) from Ch.6 *who*  
- [x] `demo` Isolation Forest + One-Class SVM on price/volume features only  
- [x] Outputs flagged count / overlap  

---

## Status

**v1.1 accepted.** Next: Phase 6 curriculum (Ch.9–17) when needed.
