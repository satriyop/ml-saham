#!/usr/bin/env bash
# Weekly challenge control tower (operator ritual step 2).
# Safe for cron: logs to ARTIFACTS/logs, never auto-promotes ai-saham.
set -euo pipefail

ML_SAHAM_ROOT="${ML_SAHAM_ROOT:-$HOME/dev/ml-saham}"
export ML_SAHAM_DB="${ML_SAHAM_DB:-$HOME/dev/ai-saham/data/db/data.db}"
export ML_SAHAM_ARTIFACTS="${ML_SAHAM_ARTIFACTS:-$ML_SAHAM_ROOT/artifacts}"

LOG_DIR="${ML_SAHAM_ARTIFACTS}/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/challenge_health_weekly_${STAMP}.log"

cd "$ML_SAHAM_ROOT"

if [[ -f "$ML_SAHAM_ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ML_SAHAM_ROOT/.venv/bin/activate"
fi

if ! command -v ml-saham >/dev/null 2>&1; then
  echo "ml-saham not on PATH; install with: pip install -e \".[ml]\"" | tee -a "$LOG"
  exit 2
fi

if [[ ! -f "$ML_SAHAM_DB" ]]; then
  echo "DB missing: $ML_SAHAM_DB" | tee -a "$LOG"
  exit 2
fi

{
  echo "=== challenge health weekly ==="
  echo "date: $(date -Iseconds 2>/dev/null || date)"
  echo "db: $ML_SAHAM_DB"
  echo "artifacts: $ML_SAHAM_ARTIFACTS"
  echo "cwd: $ML_SAHAM_ROOT"
  echo
  # Weekly default: screener rollup + display diagnostics (not Action).
  # Optional deeper pack via CHALLENGE_HEALTH_EXTRA_FLAGS.
  # shellcheck disable=SC2086
  ml-saham challenge health --with-diagnostics ${CHALLENGE_HEALTH_EXTRA_FLAGS:-}
  echo
  echo "=== done ==="
} 2>&1 | tee -a "$LOG"

# Keep a stable "latest" pointer for operators
ln -sfn "$LOG" "$LOG_DIR/challenge_health_weekly_latest.log"
echo "log: $LOG"
exit 0
