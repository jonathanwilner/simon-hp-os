#!/usr/bin/env bash
set -euo pipefail
system=${1:?Pass x86_64-linux or aarch64-linux}
case "$system" in x86_64-linux|aarch64-linux) ;; *) exit 2 ;; esac
session=omdrop-fleet-regression
export NOM_DASHBOARD_STATE_DIR="${RUNNER_TEMP:-/tmp}/omdrop-fleet-nom"
export NOM_DASHBOARD_ASSET_DIR="$PWD/pkgs/nom-dashboard/web"
bash pkgs/nom-dashboard/nom-tmux.sh "$session" -- nix build \
  ".#checks.$system.omdrop-fleet-contract" \
  ".#checks.$system.omdrop-package-contract" --no-link
status="$NOM_DASHBOARD_STATE_DIR/$session.status"
deadline=$((SECONDS + 1500))
while [[ ! -f "$status" ]]; do
  if (( SECONDS >= deadline )) || ! tmux has-session -t "=$session" 2>/dev/null; then
    cat "$NOM_DASHBOARD_STATE_DIR/$session.log" >&2 || true
    echo "Regression runner stopped without a result or exceeded 25 minutes." >&2
    exit 1
  fi
  sleep 10
done
cat "$NOM_DASHBOARD_STATE_DIR/$session.log"
exit "$(cat "$status")"
