#!/usr/bin/env bash
set -euo pipefail
system=${1:?Pass a Nix system}
session="fleet-validation-$system"
export NOM_DASHBOARD_STATE_DIR="${RUNNER_TEMP:-/tmp}/fleet-release-nom"
export NOM_DASHBOARD_ASSET_DIR="$PWD/pkgs/nom-dashboard/web"
bash pkgs/nom-dashboard/nom-tmux.sh "$session" -- bash tests/release/validate.sh "$system"
status="$NOM_DASHBOARD_STATE_DIR/$session.status"
deadline=$((SECONDS + 10800))
while [[ ! -f "$status" ]]; do
  if (( SECONDS >= deadline )) || ! tmux has-session -t "=$session" 2>/dev/null; then
    cat "$NOM_DASHBOARD_STATE_DIR/$session.log" >&2 || true
    echo 'Fleet validation stopped without a result or exceeded three hours.' >&2
    exit 1
  fi
  sleep 10
done
cat "$NOM_DASHBOARD_STATE_DIR/$session.log"
exit "$(cat "$status")"
