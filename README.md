# ml-saham

CLI kursus **machine learning problem-centric** untuk pasar saham Indonesia (IDX).  
Personal learning — data real dari SQLite `ai-saham` milikmu.

Desain: [chapters.md](./chapters.md) · [ux.md](./ux.md) · [roadmap.md](./roadmap.md)

## Setup

```bash
cd ~/dev/ml-saham
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Database

Default: `~/dev/ai-saham/data/db/data.db`

```bash
export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db
# atau
ml-saham --db ~/dev/ai-saham/data/db/data.db doctor
```

Isi data lewat `ai-saham` (`saham fetch market`, dll). `ml-saham` tidak scrape provider.

## Perintah utama

```bash
ml-saham chapters          # jalur MVP + progress
ml-saham chapters --all
ml-saham status
ml-saham doctor
ml-saham explore orientasi --no-pager
ml-saham demo orientasi
ml-saham demo clean-prices
ml-saham demo screen-rules
ml-saham compare screen-rules --baseline hand --against tree
ml-saham demo pattern-fail
ml-saham demo factor-score
ml-saham compare factor-score --baseline equal-weight --against elastic-net
ml-saham demo broker-flow
ml-saham demo cluster-peers
ml-saham demo insider
ml-saham demo volume-anomaly
ml-saham deepdive broker-flow
```

Acceptance: [mvp_acceptance.md](./mvp_acceptance.md) · [v1_1_acceptance.md](./v1_1_acceptance.md)

Butuh: `pip install -e .` (pandas + scikit-learn). LightGBM opsional: `pip install -e ".[ml]"`.

Progress: `~/.ml-saham/progress.json` (override `ML_SAHAM_HOME`).  
Artifact root: `./artifacts` atau `ML_SAHAM_ARTIFACTS` / `--artifacts-dir`.

## Status implementasi

| Phase | Isi | Status |
|---|---|---|
| 0 | Scaffold CLI + registry + DB resolve | **done** |
| 1 | Doctor tabel MVP + loaders + universe | **done** |
| 2 | Metrics + artifacts + explore pager | **done** |
| 3 | Chapter 0,1,2,3,4,6 | **done** |
| 4 | MVP harden / sign-off | **done** |
| 5 | v1.1 chapters 5,7,8 | **done** |
| 6 | Phase-2 curriculum 9–17 (+18) | **done** |
| 7 | UX extras | opsional |

## Catatan

Bukan saran trading/investasi. Skorboard demo default long-only vs IHSG (gross + banner biaya) — lihat desain di repo.
