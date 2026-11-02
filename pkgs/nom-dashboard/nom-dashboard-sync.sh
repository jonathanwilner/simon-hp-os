#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/nom-dashboard-sync.sh [remote]

Publish this machine's nom-tmux dashboard files and optionally rsync them to
the central dashboard host. The remote should name the dashboard public root,
for example:

  user@dashboard.example:/srv/nom-dashboard/public

Environment:
  NOM_DASHBOARD_STATE_DIR   defaults to ~/.local/state/nixos-intc/nom-tmux
  NOM_DASHBOARD_PUBLIC_DIR  defaults to ~/.local/state/nixos-intc/nom-dashboard/public
  NOM_DASHBOARD_HOST        defaults to hostname -s
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ssh_opts=( -o BatchMode=yes -o ConnectTimeout=8 )
export RSYNC_RSH="${RSYNC_RSH:-ssh -o BatchMode=yes -o ConnectTimeout=8}"
script_path="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "${BASH_SOURCE[0]}")"
script_dir="$(dirname "$script_path")"
host_name="${NOM_DASHBOARD_HOST:-$(hostname -s 2>/dev/null || hostname)}"
state_dir="${NOM_DASHBOARD_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/nixos-intc/nom-tmux}"
public_dir="${NOM_DASHBOARD_PUBLIC_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/nixos-intc/nom-dashboard/public}"

# Timers and per-task watchers share one nonblocking machine lock.
if [[ "${NOM_DASHBOARD_SYNC_LOCKED:-}" != 1 ]]; then
  python3 - "$state_dir" "$script_path" "$@" <<'LOCK'
import fcntl, os, pathlib, subprocess, sys
state = pathlib.Path(sys.argv[1])
state.mkdir(parents=True, exist_ok=True)
with (state / '.sync.lock').open('w') as handle:
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(0)
    environment = dict(os.environ, NOM_DASHBOARD_SYNC_LOCKED='1')
    sys.exit(subprocess.call(['bash', sys.argv[2], *sys.argv[3:]], env=environment))
LOCK
  exit "$?"
fi

asset_dir="${NOM_DASHBOARD_ASSET_DIR:-$script_dir/../share/nom-dashboard}"
[[ -d "$asset_dir" ]] || asset_dir="$script_dir/web"

python3 "$script_dir/nom-dashboard-publish.py" \
  --state-dir "$state_dir" \
  --output-dir "$public_dir" \
  --host "$host_name" \
  --asset-dir "$asset_dir"

if [[ -n "${1:-}" ]]; then
  remote="${1%/}"
  remote_host="${remote%%:*}"
  remote_root="${remote#*:}"
  remote_machine_dir="$remote_root/machines/$host_name"
  use_sudo=0

  if ! rsync -az --delete "$public_dir/machines/$host_name/" "$remote_host:$remote_machine_dir/"; then
    stage_dir=".cache/nom-dashboard-sync-$host_name"
    ssh "${ssh_opts[@]}" "$remote_host" bash -s -- "$stage_dir" <<'SH'
set -euo pipefail
stage_dir="$1"
rm -rf "$stage_dir"
mkdir -p "$stage_dir"
SH
    rsync -az --delete "$public_dir/machines/$host_name/" "$remote_host:$stage_dir/"
    ssh "${ssh_opts[@]}" "$remote_host" bash -s -- "$stage_dir" "$remote_machine_dir" <<'SH'
set -euo pipefail
stage_dir="$1"
remote_machine_dir="$2"
sudo -n mkdir -p "$remote_machine_dir"
sudo -n rsync -a --delete "$stage_dir/" "$remote_machine_dir/"
SH
    use_sudo=1
  fi

  if [[ "$use_sudo" == 0 ]]; then
    if ! ssh "${ssh_opts[@]}" "$remote_host" bash -s -- "$remote_root" <<'SH'
set -euo pipefail
remote_root="$1"
[[ -w "$remote_root" && ( ! -e "$remote_root/manifest.json" || -w "$remote_root/manifest.json" ) ]]
SH
    then
      use_sudo=1
    fi
  fi

  # Publish a shared UI that survives an older central publisher's root assets.
  dashboard_stage=".cache/nom-dashboard-ui-$host_name"
  ssh "${ssh_opts[@]}" "$remote_host" mkdir -p "$dashboard_stage"
  rsync -az --delete "$public_dir/dashboard/" "$remote_host:$dashboard_stage/"
  rsync -az "$public_dir/dashboard.html" "$remote_host:$dashboard_stage/dashboard.html"
  rsync -az "$script_dir/nom_dashboard_feed.py" "$remote_host:$dashboard_stage/nom_dashboard_feed.py"
  ssh "${ssh_opts[@]}" "$remote_host" bash -s -- "$dashboard_stage" "$remote_root/dashboard" "$use_sudo" <<'SH'
set -euo pipefail
stage="$1"
destination="$2"
if [[ "$3" == 1 ]]; then
  sudo -n mkdir -p "$destination"
  sudo -n rsync -a --delete --exclude nom_dashboard_feed.py --exclude manifest.json --exclude dashboard.html "$stage/" "$destination/"
  sudo -n install -m644 "$stage/dashboard.html" "$(dirname "$destination")/dashboard.html"
else
  mkdir -p "$destination"
  rsync -a --delete --exclude nom_dashboard_feed.py --exclude manifest.json --exclude dashboard.html "$stage/" "$destination/"
  install -m644 "$stage/dashboard.html" "$(dirname "$destination")/dashboard.html"
fi
SH

  ssh "${ssh_opts[@]}" "$remote_host" bash -s -- "$remote_root" "$use_sudo" "$dashboard_stage/nom_dashboard_feed.py" <<'SH'
set -euo pipefail
python_cmd=(python3)
[[ "$2" != 1 ]] || python_cmd=(sudo -n python3)
"${python_cmd[@]}" "$3" "$1"
SH
fi
