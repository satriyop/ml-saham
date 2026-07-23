# UX — ML Learning CLI (`ml-saham`)

Final UI/UX for the personal IDX ML learning app.  
Curriculum: [chapters.md](./chapters.md) · Backlog: [problem_backlog.md](./problem_backlog.md)

---

## Verdict

**Primary surface: CLI only** (MVP and phase 2).  
Not a trading cockpit, TUI workbench, or web app. Optional notebook export / TUI may come later; they are not the spine.

---

## Intent

**“Kursus di terminal”** — each chapter is a short, finishable path with honest scoreboard banners.

| Principle | Meaning |
|---|---|
| One job per command | `explore` teaches · `demo` runs · `deepdive` links to `ai-saham` |
| Generic first | Deep-dive never blocks completing the lesson |
| Quiet chrome | Short prose + tables + banners; no dashboard clutter |
| ID-first copy | Explanations ID; commands/flags/terms EN |
| Honest by default | Biaya / leakage / “bukan saran” visible on scoreboards |

---

## Command map

```text
ml-saham
├── chapters              # path, phase, progress
├── status                # alias-ish: what’s done / unlocked
├── explore <topic>       # generic problem → options → caveats (no heavy train)
├── demo <topic>          # real-data run + scoreboard
├── compare …             # baseline vs model (when chapter needs it)
├── deepdive <topic>      # optional: kaitkan ke ai-saham + artifact
├── glossary [term]       # kamus bertahap
└── doctor                # DB path, data-tier coverage, missing tables / how to fetch
```

**Topic slugs** = generic chapter ids (examples):

| Topic slug | Chapter |
|---|---|
| `orientasi` | 0 |
| `clean-prices` | 1 |
| `screen-rules` | 2 |
| `pattern-fail` | 3 |
| `factor-score` | 4 |
| `cluster-peers` | 5 |
| `broker-flow` | 6 |
| `insider` | 7 |
| `volume-anomaly` | 8 |
| `headline-tone` | 9 |
| `volatility-sizing` | 10 |
| `market-regime` | 11 |
| `walk-forward` | 12 |
| `portfolio-small` | 13 |
| `corp-events` | 14 |
| `earnings-surprise` | 15 |
| `pre-open-rank` | 16 |
| `research-pipeline` | 17 |
| `rl-sandbox` | 18 (optional appendix) |

Do **not** name topics after engines (`signal-engine`, `mce`, `risk-engine`).

---

## Happy path (every chapter)

```text
ml-saham chapters
ml-saham explore <topic>
ml-saham demo <topic> [flags]
ml-saham compare <topic> --baseline … --against …   # when useful
ml-saham deepdive <topic>                           # optional
```

Progress stored lightly (e.g. `~/.ml-saham/progress.json`): explored / demoed per topic — no gamification noise.

---

## Screen frames

### `explore` — teach, don’t train

```text
═══════════════════════════════════════
Ch.N  <Judul masalah umum>
═══════════════════════════════════════
Masalah
  …

Opsi pendekatan
  1) …
  2) …
  3) …

Caveat (baca sebelum demo)
  • …
  • Skorboard: … · belum termasuk biaya

Lanjut:  ml-saham demo <topic> --help
```

- Use pager by default; `--no-pager` to disable.  
- Keep “must read” short; extra detail behind `--verbose`.

### `demo` — run on real data

```text
Data     db=…  universe=…  as_of=…
Model    …
─────────────────────────────────────
[hasil: tabel / IC / ASCII singkat]
─────────────────────────────────────
⚠ Skorboard: long-only vs IHSG · belum termasuk biaya
⚠ Bukan saran trading / investasi
Artifact (opsional):  artifacts/<topic>/…
```

Ch.16 exception: opening-session scoreboard (not default IHSG long-only), still with biaya + disclaimer banners.

### `deepdive` — clearly secondary

```text
Deep-dive · kaitkan ke ai-saham
  Terkait: …
  Yang bisa dibawa balik: …
  Artifact: …
```

Must be skippable; chapter remains complete without it.

### `doctor` — data readiness

Report DB path, MVP / v1.1 / phase-2 table coverage, and exact remediation (e.g. which `saham fetch …` to run). Fail demos with a pointer to `doctor`, not a stack trace dump.

---

## Global flags & defaults

| Item | Default |
|---|---|
| `--db` | Env `ML_SAHAM_DB`, else configured path to personal `ai-saham` / learning DB |
| `--universe` | Liquid subset (LQ45-like ∩ cached) where relevant |
| `--json` | Machine-readable demo/compare output for artifacts |
| `--plot PATH` | Optional image; terminal ASCII/sparkline by default |
| `--with-costs` | Optional simple haircut; off by default (banner still on) |
| Color | Sparse; respect `NO_COLOR` |

---

## Copy rules

1. Section headers and teaching prose: **Indonesian**.  
2. Flags, topic slugs, library names, metric names (`rank IC`, `walk-forward`): **English**.  
3. Every scoreboard block includes: honesty banners (biaya and/or leakage as relevant) + **bukan saran trading/investasi**.  
4. Deep-dive blocks labeled explicitly so they never look like the main lesson.

---

## Out of UX scope (for now)

- TUI workbench  
- Web UI  
- Chat-first “AI tutor” as the main interface  
- Forcing `deepdive` before `demo`  
- Notebook as primary path (optional `demo --export-notebook` later only)

---

## Relationship to `ai-saham`

| App | Job |
|---|---|
| `ai-saham` | Operate / screen / analyze / fetch |
| `ml-saham` | Learn / prove / export artifacts |

Share muscle memory (CLI, `--db`, universe flags) where it helps; do not copy trading-workbench UX into learning chapters.
