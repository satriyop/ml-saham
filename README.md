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
ml-saham explore orientasi --no-pager   # pager default; --verbose untuk detail
ml-saham demo orientasi                 # tulis artifacts/<topic>/… (kecuali --no-artifact)
ml-saham demo orientasi --with-costs
ml-saham compare factor-score --baseline hand --against elastic-net
ml-saham deepdive broker-flow
ml-saham glossary
```

Progress disimpan di `~/.ml-saham/progress.json` (E=explore, D=demo, DV=deepdive).  
Artifact root: `./artifacts` atau `ML_SAHAM_ARTIFACTS` / `--artifacts-dir` (folder di-gitignore).

## Status implementasi

| Phase | Isi | Status |
|---|---|---|
| 0 | Scaffold CLI + registry + DB resolve | **done** |
| 1 | Doctor tabel MVP + loaders + universe | **done** |
| 2 | Metrics + artifacts + explore pager | **done** |
| 3 | Chapter 0,1,2,3,4,6 | berikutnya |

## Catatan

Bukan saran trading/investasi. Skorboard demo default long-only vs IHSG (gross + banner biaya) — lihat desain di repo.
