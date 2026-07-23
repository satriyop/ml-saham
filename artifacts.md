# Artifacts — export contract

How `ml-saham` lessons optionally write files you can use to tune `ai-saham`.  
Human-applied only — **never** auto-edit `ai-saham` YAML/config from this tool.

UX: [ux.md](./ux.md) · Architecture: [architecture.md](./architecture.md)

---

## Purpose

Support product goal #2: learning produces **reusable evidence** (metrics, feature lists, suggested weight notes), not a second trading engine.

---

## Location

```text
<project or cwd>/artifacts/
  <topic>/
    <timestamp>_<slug>/
      manifest.json
      summary.md
      … payload files …
```

Override root with `--artifacts-dir` or env `ML_SAHAM_ARTIFACTS`.

---

## `manifest.json` (required for every artifact pack)

```json
{
  "schema_version": 1,
  "topic": "broker-flow",
  "chapter": 6,
  "created_at": "2026-07-23T14:00:00+07:00",
  "db_path": "/Users/…/ai-saham/data/db/data.db",
  "universe": "LQ45",
  "as_of": "2026-07-22",
  "mode": "demo|compare|deepdive",
  "model": "elastic-net",
  "scoreboard": {
    "type": "long_only_vs_ihsg",
    "costs": "gross_banner",
    "disclaimer": "bukan_saran"
  },
  "ai_saham_deepdive": false,
  "files": ["summary.md", "metrics.json", "top_names.csv"]
}
```

For opening-session chapters, `"scoreboard.type": "open_session"`.

---

## Common payloads

| File | When | Content |
|---|---|---|
| `summary.md` | Always | ID prose: what ran, caveats, how to read metrics |
| `metrics.json` | demo/compare | rank IC, bucket returns vs IHSG, n tickers, date range |
| `top_names.csv` | rank demos | ticker, score, optional forward return |
| `feature_list.json` | factor/flow/walk-forward | names + short definitions |
| `compare.json` | compare | baseline vs against metrics side by side |
| `suggestions.md` | deepdive only | Human notes for `ai-saham` (YAML keys as **text suggestions**, not applied patches) |

---

## Deep-dive suggestions format (`suggestions.md`)

```markdown
# Suggestions for ai-saham (manual review)

Related: foreign-flow / accum score components

## Evidence
- ML blend rank IC: …
- Rule composite rank IC: …
- Caveats: …

## Possible knobs (do not apply blindly)
- Consider raising weight on `…` relative to `…`
- Validate on walk-forward before changing YAML

## Not claimed
- Live edge, auto-promote, or smart-money proof
```

No machine-applied patch files in MVP. If later you want structured diffs, add `suggestions.json` under a new schema_version — still human-gated.

---

## When artifacts are written

| Command | Default |
|---|---|
| `explore` | No |
| `demo` | Yes (minimal: manifest + summary + metrics) unless `--no-artifact` |
| `compare` | Yes |
| `deepdive` | Yes (includes `suggestions.md` when applicable) |

---

## Non-goals

- Writing into `ai-saham` repo paths automatically  
- Binary model pickle as the primary artifact (optional later; metrics + feature defs matter more for learning)  
- Claiming suggestions are production-ready
