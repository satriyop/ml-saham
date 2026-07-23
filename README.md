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
ml-saham doctor            # cek path + tabel MVP data
ml-saham explore orientasi # stub sampai Phase 3
ml-saham demo orientasi
ml-saham deepdive orientasi
ml-saham glossary
```

Progress disimpan di `~/.ml-saham/progress.json` (E=explore, D=demo, DV=deepdive).

## Status implementasi

| Phase | Isi | Status |
|---|---|---|
| 0 | Scaffold CLI + registry + DB resolve | **done** |
| 1 | Doctor tabel MVP + loaders + universe | **done** |
| 2 | Metrics + artifacts | berikutnya |
| 3 | Chapter 0,1,2,3,4,6 | belum |

## Catatan

Bukan saran trading/investasi. Skorboard demo default long-only vs IHSG (gross + banner biaya) — lihat desain di repo.
