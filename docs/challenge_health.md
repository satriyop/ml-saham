# Operator note: Challenge **health** + **promote-packet**

English control tower for ai-saham (human-in-the-loop).  
Product map: [challenge_product.md](./challenge_product.md) · Boundary: [BOUNDARY.md](../BOUNDARY.md)

## Health report

**Question:** How is the screener challenge surface right now (tune ± champion ± factors)?

```bash
ml-saham challenge health
ml-saham challenge health --scenario accum
ml-saham challenge health --scenario pre-open
ml-saham challenge health --with-champion
ml-saham challenge health --with-factors
ml-saham challenge health --with-champion --with-factors
```

### Recipe

| Step | Default |
|------|---------|
| Engine portfolio | `screener` vs **equal_sleeves** (tune) |
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
ml-saham challenge health --with-champion --with-factors
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
- Factor DEMOTE / DROP_CANDIDATE  
- Skipped champion/factors notes  
