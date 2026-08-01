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

### Cron install (recommended)

```bash
# from repo root (uses default Sun 07:15 local)
./scripts/install_challenge_health_cron.sh

# custom schedule / deeper weekly pack
CHALLENGE_HEALTH_CRON_SCHEDULE='0 8 * * 1' \
CHALLENGE_HEALTH_EXTRA_FLAGS='--with-factors --with-champion' \
  ./scripts/install_challenge_health_cron.sh

# dry-run once
./scripts/challenge_health_weekly.sh

# remove
./scripts/uninstall_challenge_health_cron.sh
```

Job script: `scripts/challenge_health_weekly.sh`  
Logs: `$ML_SAHAM_ARTIFACTS/logs/challenge_health_weekly_*.log` (+ `…_latest.log` symlink).

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

**Schema reopen contract:** challenge/champion JSON exports and artifact packs
stamp integer `schema_version: 3` (material population identity fields + honest
`baseline_id`). `promote-packet` requires that exact integer on every reopen
path (`--from-json` and `--from-artifact`). Historical v2 packs are display-only
and not promote-reopen eligible. Missing, string, float, or unsupported versions
fail closed. When `manifest.json` is present it is authoritative — a sibling
`export.json` cannot bypass manifest validation.

**v3 population identity (promote reopen):** verified production ACCUM exports
must carry non-empty `population_identity_kind` / `population_identity_id` /
`population_identity_detail`. For ACCUM promote eligibility:
`population_identity_kind == "accum_compat"` and
`population_identity_id == observation_compatibility_id`. Omitting these fields
fails closed even when production snapshot ids are present.

**Baselines:** `baseline=production` requires a verified production-policy
snapshot + adapter (ACCUM path today). Static pre-open / IEV fixtures must pass
`--baseline static_reference` explicitly; production is never silently remapped.
`static_reference` digs are not promote-eligible.

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
