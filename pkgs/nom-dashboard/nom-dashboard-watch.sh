#!/usr/bin/env bash
# Keep a nom task's measured progress fresh on every reporting host.
set -euo pipefail
status_file="${1:?Usage: nom-dashboard-watch.sh STATUS_FILE [REMOTE]}"
remote="${2:-}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sync_script="$script_dir/nom-dashboard-sync.sh"
[[ -f "$sync_script" ]] || sync_script="$script_dir/nom-dashboard-sync"
while [[ ! -f "$status_file" ]]; do
  bash "$sync_script" "$remote" || true
  sleep 30
done
bash "$sync_script" "$remote" || true
