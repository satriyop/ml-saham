#!/usr/bin/env bash
# Install (or update) a weekly crontab entry for challenge_health_weekly.sh.
# Default: Sundays 07:15 local time.
set -euo pipefail

ML_SAHAM_ROOT="${ML_SAHAM_ROOT:-$HOME/dev/ml-saham}"
JOB_SCRIPT="${ML_SAHAM_ROOT}/scripts/challenge_health_weekly.sh"
CRON_SCHEDULE="${CHALLENGE_HEALTH_CRON_SCHEDULE:-15 7 * * 0}"
MARKER="# ml-saham-challenge-health-weekly"

if [[ ! -x "$JOB_SCRIPT" ]]; then
  if [[ -f "$JOB_SCRIPT" ]]; then
    chmod +x "$JOB_SCRIPT"
  else
    echo "missing job script: $JOB_SCRIPT" >&2
    exit 2
  fi
fi

# Ensure job is executable
chmod +x "$JOB_SCRIPT"

LINE="${CRON_SCHEDULE} ML_SAHAM_ROOT=${ML_SAHAM_ROOT} ${JOB_SCRIPT} ${MARKER}"

# Merge into user crontab without duplicating our marker
EXISTING="$(crontab -l 2>/dev/null || true)"
FILTERED="$(printf '%s\n' "$EXISTING" | grep -vF "$MARKER" || true)"
NEW="${FILTERED}"
if [[ -n "${NEW// }" ]]; then
  NEW="${NEW}"$'\n'
fi
NEW="${NEW}${LINE}"$'\n'

printf '%s' "$NEW" | crontab -

echo "Installed weekly challenge health cron:"
echo "  schedule: ${CRON_SCHEDULE}  (default Sun 07:15 local)"
echo "  job:      ${JOB_SCRIPT}"
echo "  marker:   ${MARKER}"
echo
echo "Env (optional overrides in crontab or shell before install):"
echo "  ML_SAHAM_ROOT  ML_SAHAM_DB  ML_SAHAM_ARTIFACTS"
echo "  CHALLENGE_HEALTH_CRON_SCHEDULE   e.g. '0 8 * * 1' for Mondays 08:00"
echo "  CHALLENGE_HEALTH_EXTRA_FLAGS     e.g. '--with-factors --with-champion'"
echo
echo "Current crontab lines for this job:"
crontab -l 2>/dev/null | grep -F "$MARKER" || true
echo
echo "Dry-run now:"
echo "  ${JOB_SCRIPT}"
echo "Uninstall:"
echo "  ${ML_SAHAM_ROOT}/scripts/uninstall_challenge_health_cron.sh"
