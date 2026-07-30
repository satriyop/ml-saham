# UX — Challenge lab CLI (`ml-saham`)

UI/UX for the personal IDX **challenge lab** (+ curriculum onboarding).  
Product axis: [ADR-001](./docs/adr/ADR-001-challenge-first-product-axis.md) · Curriculum: [chapters.md](./chapters.md) · Backlog: [problem_backlog.md](./problem_backlog.md)

---

## Verdict

**Primary surface: CLI only.**  
Not a trading cockpit, TUI workbench, or web app. Optional notebook export / TUI may come later; they are not the spine.

**Command priority:** `challenge` (product) ahead of `learn` (curriculum).

| Command | Use when |
|---------|----------|
| `challenge` | Policy / engine audit (ADR-002 authority) |
| `learn` | Curriculum: list / explore / demo / compare (not promotion) |

---

## Intent

**“Engine audit in the terminal”** — challenge policies against clean challengers; curriculum is the short path to understand a factor before you trust the audit.

| Principle | Meaning |
|---|---|
| Challenge first | `challenge` is the main job; green policy audits > complete demos |
| One namespace per axis | `learn explore` teaches · `learn demo` illustrates · `learn compare` = curriculum lab · `challenge` = product audit |
| Generic first | Curriculum never blocks product work; challenge still needs honest metrics |
| Quiet chrome | Short prose + tables + banners; no dashboard clutter |
| Language by axis | **Challenge output: English.** **Learning (`learn explore`) narrative: Indonesian.** Commands/flags/slugs always EN (ADR-001 §6) |
| Honest by default | Cost / leakage / “not investment advice” banners on scoreboards |

---

## Command map

```text
ml-saham
├── challenge …              # PRIMARY: ADR-002 policy / engine / factor / health
├── learn …                  # SECONDARY curriculum (not promotion)
│   ├── list | chapters      # catalog + progress (E✓ D✓)
│   ├── status               # DB path + MVP progress
│   ├── explore <topic>
│   ├── demo <topic>
│   ├── compare <topic>
│   ├── leaderboard
│   └── glossary [term]
├── doctor                   # shared: data-tier coverage
└── vet                      # shared: English data-integrity audit
```

**Topic slugs** = generic chapter ids. Numbers match `registry.py` (SSOT):

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
| `survival-analysis` | 8 |
| `volume-anomaly` | 9 |
| `headline-tone` | 10 |
| `volatility-sizing` | 11 |
| `market-regime` | 12 |
| `walk-forward` | 13 |
| `portfolio-small` | 14 |
| `corp-events` | 15 |
| `earnings-surprise` | 16 |
| `nowcasting` | 17 |
| `pre-open-rank` | 18 |
| `research-pipeline` | 19 |
| `rl-sandbox` | 20 (optional appendix) |
| `seasonality-drift` … `pre-open-macro` | 21–44 |

Full list: `ml-saham learn list --all` or [chapters.md](./chapters.md).

Do **not** name topics after engines (`signal-engine`, `mce`, `risk-engine`).

---

## Happy path (every chapter)

```text
ml-saham learn list
ml-saham learn explore <topic>
ml-saham learn demo <topic> [flags]
ml-saham learn compare <topic> --baseline … --against …   # curriculum lab
ml-saham challenge run|engine|factor|health …        # product authority
```

Progress stored lightly (e.g. `~/.ml-saham/progress.json`): explored / demoed per topic — no gamification noise.

---

## Screen frames

### `learn explore` — teach, don’t train

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

Lanjut:  ml-saham learn demo <topic> --help
```

- Use pager by default; `--no-pager` to disable.  
- Keep “must read” short; extra detail behind `--verbose`.

### `learn demo` — run on real data

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

Ch.18 (`pre-open-rank`) exception: opening-session scoreboard (not default IHSG long-only), still with biaya + disclaimer banners.

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
4. Curriculum `learn compare` is not promotion authority; use `challenge` for policy audits.

---

## Out of UX scope (for now)

- TUI workbench  
- Web UI  
- Chat-first “AI tutor” as the main interface  
- Retired: flat root `explore` / `demo` / `compare` / `chapters` (use `learn …`); `deepdive`  
- Notebook as primary path (optional later only)

---

## Relationship to `ai-saham`

| App | Job |
|---|---|
| `ai-saham` | Operate / screen / analyze / fetch |
| `ml-saham` | Learn / prove / export artifacts |

Share muscle memory (CLI, `--db`, universe flags) where it helps; do not copy trading-workbench UX into learning chapters.
