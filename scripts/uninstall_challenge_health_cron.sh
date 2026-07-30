#!/usr/bin/env bash
# Remove the weekly challenge health crontab line installed by install_challenge_health_cron.sh.
set -euo pipefail

MARKER="# ml-saham-challenge-health-weekly"
EXISTING="$(crontab -l 2>/dev/null || true)"
if ! printf '%s\n' "$EXISTING" | grep -qF "$MARKER"; then
  echo "No ${MARKER} line found in crontab."
  exit 0
fi
FILTERED="$(printf '%s\n' "$EXISTING" | grep -vF "$MARKER" || true)"
printf '%s\n' "$FILTERED" | crontab -
echo "Removed weekly challenge health cron (${MARKER})."
