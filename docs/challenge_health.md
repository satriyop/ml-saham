# Operator note: Challenge **health** + **promote-packet**

English control tower for ai-saham (human-in-the-loop).  
Product map + **operator ritual SSOT:** [challenge_product.md](./challenge_product.md) · Boundary: [BOUNDARY.md](../BOUNDARY.md)

## Weekly ritual (default)

**Question:** How is the **screener** challenge surface + **display diagnostics** right now?

```bash
# Weekly control tower (recommended)
ml-saham challenge health --with-diagnostics

# Optional deeper weekly pack
ml-saham challenge health --with-diagnostics --with-factors
ml-saham challenge health --with-diagnostics --with-champion --with-factors
```

| Do weekly | Do **not** every week |
|-----------|------------------------|
| `health --with-diagnostics` | `challenge engine signal` / `risk` (only when retuning those knobs) |
| Start from `challenge list` if you forgot the catalog | Treat diagnostic `PROMOTE_CANDIDATE` as ENTER/Action |

Signal / risk digs (on-demand):

```bash
ml-saham challenge engine signal --scenario accum
ml-saham challenge engine risk --scenario accum --against gate_off
```

Diagnostics section in the pack is **display / promote-candidate only** — **never** sleeve KEEP/DEMOTE and **never** TradeSetup Action (ADR-057).  
`PROMOTE_CANDIDATE` → design a PolicySpec → `challenge run` / `factor` → human ai-saham change.

## Health report

**Question:** How is the screener challenge surface right now (tune ± diagnostics ± champion ± factors)?

```bash
ml-saham challenge health
ml-saham challenge health --scenario accum
ml-saham challenge health --scenario pre-open
ml-saham challenge health --with-diagnostics
ml-saham challenge health --with-champion
ml-saham challenge health --with-factors
ml-saham challenge health --with-diagnostics --with-champion --with-factors
```

### Recipe

| Step | Default |
|------|---------|
| Engine portfolio | `screener` vs **equal_sleeves** (tune) |
| `--with-diagnostics` | display bags (KEEP_DISPLAY / PROMOTE_CANDIDATE) — **not Action** |
| `--with-champion` | accum only: `lgbm_reweight` (skipped if scenario excludes accum) |
| `--with-factors` | always `screener.accum.score_weights --all` (note in pack) |

### Pack layout

```text
artifacts/challenge/health/<ts>/
  manifest.json
  summary.md      # read this first
  engine.json
  index.json
  champion.json   # if --with-champion and not skipped
  factors.json    # if --with-factors
  diagnostics.json  # if --with-diagnostics (display bags; not Action)
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Recipe finished (BLOCKED rows allowed) |
| 2 | Bad scenario / missing DB / resolve error |

### Cron example

```bash
#!/usr/bin/env bash
set -euo pipefail
export ML_SAHAM_DB="${ML_SAHAM_DB:-$HOME/dev/ai-saham/data/db/data.db}"
export ML_SAHAM_ARTIFACTS="${ML_SAHAM_ARTIFACTS:-$HOME/dev/ml-saham/artifacts}"
cd "$HOME/dev/ml-saham"
source .venv/bin/activate
ml-saham challenge health --with-diagnostics --with-champion --with-factors
# inspect latest:
ls -t "$ML_SAHAM_ARTIFACTS/challenge/health" | head -1
```

---

## Promote packet

**Question:** Given this result, what must a human review before touching ai-saham?

```bash
ml-saham challenge champion screener.accum.score_weights \
  --export-json /tmp/champ.json --no-artifact

ml-saham challenge promote-packet --from-json /tmp/champ.json
# → artifacts/challenge/promote/<policy>/<ts>/PROMOTE.md
```

Also: `--from-artifact <challenge_artifact_dir>` (manifest + metrics).

**Never auto-applies.** LOSE/INCONCLUSIVE packets are allowed (document reject / need data).

---

## Attention heuristics (summary.md)

- Engine BLOCKED rows  
- Tune LOSE vs equal_sleeves  
- Champion WIN (human review scorer replacement)  
- Factor DEMOTE / DROP_CANDIDATE (sleeves — **not** diagnostic verdicts)  
- Diagnostic PROMOTE_CANDIDATE → design PolicySpec (never Action)  
- Diagnostic DEMOTE/DROP_DISPLAY (desk noise)  
- Skipped champion/factors notes  
