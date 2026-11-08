#!/usr/bin/env bash
set -euo pipefail
system=${1:?Pass a Nix system}
session="fleet-validation-$system"
export NOM_DASHBOARD_STATE_DIR="${RUNNER_TEMP:-/tmp}/fleet-release-nom"
export NOM_DASHBOARD_ASSET_DIR="$PWD/pkgs/nom-dashboard/web"
# These figures distinguish disk exhaustion from an actual build regression.
df -h "$PWD" /nix/store
trap 'df -h "$PWD" /nix/store >&2 || true' EXIT
bash pkgs/nom-dashboard/nom-tmux.sh "$session" -- bash tests/release/validate.sh "$system"
status="$NOM_DASHBOARD_STATE_DIR/$session.status"
log="$NOM_DASHBOARD_STATE_DIR/$session.log"
offset=0
stream_log() {
  [[ -f "$log" ]] || return 0
  local size
  size=$(stat -c %s "$log")
  if (( size > offset )); then
    dd if="$log" iflag=skip_bytes,count_bytes skip="$offset" count="$((size-offset))" status=none
    offset=$size
  fi
}
deadline=$((SECONDS + 10800))
while [[ ! -f "$status" ]]; do
  stream_log
  if (( SECONDS >= deadline )) || ! tmux has-session -t "=$session" 2>/dev/null; then
    [[ ! -f "$status" ]] || break
    stream_log >&2 || true
    echo 'Fleet validation stopped without a result or exceeded three hours.' >&2
    exit 1
  fi
  sleep 10
done
stream_log
exit "$(cat "$status")"
