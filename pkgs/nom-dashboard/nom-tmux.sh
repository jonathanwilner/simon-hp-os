#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/nom-tmux.sh SESSION -- COMMAND [ARG...]

Run a build or test command in a detached tmux session, tracked in the Nix
build dashboard. Nix and nixos-rebuild commands render through nom; any other
command (tests, scripts, any build) is tracked with the same log, exit status,
and published metadata.

Examples:
  scripts/nom-tmux.sh nixos-rebuild-slazenger -- sudo nixos-rebuild switch --flake .#slazenger --accept-flake-config
  scripts/nom-tmux.sh build-slazenger -- nix build .#nixosConfigurations.slazenger.config.system.build.toplevel --no-link
  scripts/nom-tmux.sh test-voice-tools -- python3 -m pytest tests/voice

Attach:
  tmux attach -t SESSION
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 3 ]]; then
  usage
  exit 0
fi

session="$1"
shift

if [[ "${1:-}" != "--" ]]; then
  usage >&2
  exit 2
fi
shift

if tmux has-session -t "=$session" 2>/dev/null; then
  echo "nom-tmux: tmux session already exists: $session" >&2
  echo "Attach with: tmux attach -t $session" >&2
  exit 1
fi

if ! command -v nom >/dev/null 2>&1; then
  echo "nom-tmux: missing nom; install nix-output-monitor first" >&2
  exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "nom-tmux: missing tmux" >&2
  exit 1
fi

quote_args() {
  local arg
  for arg in "$@"; do
    printf '%q ' "$arg"
  done
}

safe_file_name() {
  local value="$1"
  value="$(printf '%s' "$value" | LC_ALL=C tr -c 'A-Za-z0-9_.@+-' '_' | cut -c1-160)"
  if [[ -z "$value" ]]; then
    value="session"
  fi
  printf '%s' "$value"
}

has_arg() {
  local needle="$1"
  shift
  local arg
  for arg in "$@"; do
    [[ "$arg" == "$needle" ]] && return 0
  done
  return 1
}

build_command=("$@")
prefix=()
if [[ "${build_command[0]}" == "sudo" ]]; then
  prefix=(sudo)
  build_command=("${build_command[@]:1}")
fi

if [[ "${build_command[0]}" == "nixos-rebuild" ]]; then
  monitored=("${prefix[@]}" "${build_command[@]}")
  if ! has_arg "--log-format" "${monitored[@]}"; then
    monitored+=(--log-format internal-json -v)
  fi
  run_line="$(quote_args "${monitored[@]}")2>&1 | nom --json"
elif [[ "${build_command[0]}" == "nix" && "${build_command[1]:-}" =~ ^(build|shell|develop)$ ]]; then
  monitored=("${prefix[@]}" nom "${build_command[1]}" "${build_command[@]:2}")
  run_line="$(quote_args "${monitored[@]}")"
elif [[ "${build_command[0]}" == "nix" || "${build_command[0]}" == "nix-build" || "${build_command[0]}" == "home-manager" ]]; then
  monitored=("${prefix[@]}" "${build_command[@]}")
  if ! has_arg "--log-format" "${monitored[@]}"; then
    monitored+=(--log-format internal-json -v)
  fi
  run_line="$(quote_args "${monitored[@]}")2>&1 | nom --json"
else
  # Tests, scripts, and any other command: tracked and published without nom.
  monitored=("${prefix[@]}" "${build_command[@]}")
  run_line="$(quote_args "${monitored[@]}")"
fi

state_dir="${NOM_DASHBOARD_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/nixos-intc/nom-tmux}"
mkdir -p "$state_dir"
safe_session="$(safe_file_name "$session")"
status_file="$state_dir/${safe_session}.status"
log_file="$state_dir/${safe_session}.log"
metadata_file="$state_dir/${safe_session}.json"
events_file="$state_dir/${safe_session}.events.jsonl"
progress_file="$state_dir/${safe_session}.progress.json"
rm -f "$status_file" "$progress_file"

reporting_config="${XDG_CONFIG_HOME:-$HOME/.config}/nom-dashboard/reporting.env"
if [[ -f "$reporting_config" && ! ${NOM_DASHBOARD_REMOTE+x} ]]; then
  source "$reporting_config"
fi

script_path="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "${BASH_SOURCE[0]}")"
script_dir="$(dirname "$script_path")"
record_script="$script_dir/nom-dashboard-record.py"
publish_script="$script_dir/nom-dashboard-publish.py"
asset_dir="${NOM_DASHBOARD_ASSET_DIR:-$script_dir/../share/nom-dashboard}"
[[ -d "$asset_dir" ]] || asset_dir="$script_dir/web"
watch_script="$script_dir/nom-dashboard-watch.sh"
host_name="${NOM_DASHBOARD_HOST:-$(hostname -s 2>/dev/null || hostname)}"
publish_dir="${NOM_DASHBOARD_PUBLIC_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/nixos-intc/nom-dashboard/public}"
command_display="$(quote_args "$@")"
record_base=(
  python3 "$record_script"
  --metadata-file "$metadata_file"
  --events-file "$events_file"
  --session "$session"
  --safe-session "$safe_session"
  --host "$host_name"
  --cwd "$PWD"
  --command "$command_display"
  --log-file "$log_file"
  --status-file "$status_file"
)
record_running="$(quote_args "${record_base[@]}" --phase running)"
record_finished="$(quote_args "${record_base[@]}" --phase finished)"
publish_command="$(quote_args python3 "$publish_script" --state-dir "$state_dir" --output-dir "$publish_dir" --host "$host_name" --asset-dir "$asset_dir")"

if command -v python3 >/dev/null 2>&1 && [[ -f "$record_script" ]]; then
  "${record_base[@]}" --phase queued || true
fi

tmux_command=$(
  printf 'set -o pipefail; '
  printf 'export NOM_DASHBOARD_PROGRESS_FILE=%q NOM_DASHBOARD_STATE_DIR=%q NOM_DASHBOARD_PUBLIC_DIR=%q NOM_DASHBOARD_HOST=%q NOM_DASHBOARD_REMOTE=%q; ' "$progress_file" "$state_dir" "$publish_dir" "$host_name" "${NOM_DASHBOARD_REMOTE:-}"
  printf 'if command -v python3 >/dev/null 2>&1 && [ -f %q ]; then %s || true; fi; ' "$record_script" "$record_running"
  printf 'if command -v python3 >/dev/null 2>&1 && [ -f %q ]; then %s >/dev/null 2>&1 || true; fi; ' "$publish_script" "$publish_command"
  printf 'if [ -f %q ]; then NOM_DASHBOARD_ASSET_DIR=%q bash %q %q %q >/dev/null 2>&1 & fi; ' "$watch_script" "$asset_dir" "$watch_script" "$status_file" "${NOM_DASHBOARD_REMOTE:-}"
  printf 'echo "[nom-tmux] session=%q"; ' "$session"
  printf 'echo "[nom-tmux] cwd=%q"; ' "$PWD"
  printf 'echo "[nom-tmux] command=%s"; ' "$(printf '%q ' "$@")"
  printf '%s; ' "$run_line"
  printf 'rc=$?; '
  printf 'printf "%%s\\n" "$rc" > %q; ' "$status_file"
  printf 'if command -v python3 >/dev/null 2>&1 && [ -f %q ]; then %s --exit-code "$rc" || true; fi; ' "$record_script" "$record_finished"
  printf 'if command -v python3 >/dev/null 2>&1 && [ -f %q ]; then %s >/dev/null 2>&1 || true; fi; ' "$publish_script" "$publish_command"
  printf 'echo "[nom-tmux] exit=$rc"; '
  printf 'echo "[nom-tmux] status file: %q"; ' "$status_file"
  printf 'echo "[nom-tmux] leaving shell open for attach"; '
  printf 'exec "${SHELL:-bash}"'
)

tmux_shell_command="$(printf '%q ' bash -lc "$tmux_command")"
tmux new-session -d -s "$session" -c "$PWD" "$tmux_shell_command" \; pipe-pane -o -t "$session" "cat >> $(printf '%q' "$log_file")"

echo "Started tmux session: $session"
echo "Attach with: tmux attach -t $session"
echo "Status file: $status_file"
echo "Log file: $log_file"
