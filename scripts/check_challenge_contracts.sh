#!/usr/bin/env bash
# Systematic gate: live-shaped payload contracts + known anti-pattern bans.
# No maintainer DB required. Exit non-zero on any failure.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

echo "== challenge extract contracts =="

# --- 1) Pattern bans (product challenge panels) ---
echo "-- pattern bans --"

# Forbidden: IEV/IEP ratio assignment in panel code (docstrings may mention the ban).
if command -v rg >/dev/null 2>&1; then
  if rg -n --glob 'panel*.py' \
    -e '\(iev\s*/\s*iep' \
    -e 'iev\s*/\s*iep\s*-\s*1' \
    src/ml_saham/challenge/ 2>/dev/null \
    | grep -v 'Do \*\*not\*\*' \
    | grep -v '``iev/iep' \
    | grep -v 'not form' \
    | grep -v 'meaningless' \
    | grep -v 'volume-scale' \
    | grep .; then
    die "forbidden IEV/IEP ratio assignment in challenge panel code"
  fi

  # Forbidden: old unit heuristic on pre-open product paths
  if rg -n -e 'abs\(x\)\s*[><=!]+\s*1(\.0)?' \
    src/ml_saham/challenge/panel_pre_open_obs.py \
    src/ml_saham/challenge/panel_pre_open*.py 2>/dev/null \
    | grep .; then
    die "forbidden |x| vs 1 unit heuristic in pre-open product extract"
  fi
else
  echo "(rg not installed — skipping pattern bans; install ripgrep for full gate)"
fi

# --- 2) Protocol: multi-fold WIN ---
echo "-- min_folds_for_win --"
PYTHONPATH=src python - <<'PY'
from ml_saham.challenge.protocols import ACCUM_PATH_V1, PRE_OPEN_SESSION_V1

for p in (ACCUM_PATH_V1, PRE_OPEN_SESSION_V1):
    n = int(getattr(p, "min_folds_for_win", 0) or 0)
    assert n >= 2, f"{p.protocol_id} min_folds_for_win={n} (need >= 2)"
print("ok: min_folds_for_win >= 2 on product protocols")
PY

# --- 3) Golden fixtures present ---
echo "-- golden fixtures --"
GOLDEN_DIR=tests/fixtures/golden
required=(
  accum_adr056_window.json
  signal_adr056_window.json
  open_30m_metrics.json
  iev_multi_capture_day.json
  risk_adr056_trade_setup.json
  diagnostic_adr056_window.json
  mce_bound_market_context.json
  accum_screen_hard_filters.json
  README.md
)
for f in "${required[@]}"; do
  [[ -f "$GOLDEN_DIR/$f" ]] || die "missing golden fixture: $GOLDEN_DIR/$f"
done
echo "ok: ${#required[@]} golden files present"

# --- 4) Contract + verdict tests (no sklearn required) ---
echo "-- pytest payload contracts + verdict folds --"
PYTHONPATH=src:. python -m pytest \
  tests/test_challenge_payload_contracts.py \
  tests/test_challenge_verdict_folds.py \
  tests/test_challenge_screen_filter_replay.py \
  -q --tb=short

echo "== challenge extract contracts: PASS =="
