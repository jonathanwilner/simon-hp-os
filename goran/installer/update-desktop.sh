#!/usr/bin/env bash
# Update the locked Simon desktop without changing Ubuntu or another user profile.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: simon-desktop-update [--checkout PATH] [--build-only] [--no-pull] [--attach]
       simon-desktop-update --status | --status-window

Pull main, build the locked Simon flake in nom-tmux,
and activate it as simon. --build-only never activates; --no-pull is allowed
only with --build-only for validating a committed integration branch.
USAGE
}
fail() { echo "simon-desktop-update: $*" >&2; exit 1; }
status() {
  printf 'Application source: %s\n' "$checkout"
  local record="${XDG_STATE_HOME:-$HOME/.local/state}/simon-desktop-update/current"
  if [[ -r "$record/source-revision" ]]; then
    printf 'Last successful desktop revision: '; cat "$record/source-revision"
    printf 'Desktop generation: %s\n' "$(readlink -f "$record/candidate")"
  fi
  printf '\nNix applications follow the published flake.lock.\n'
  printf '\nFlatpak applications in this account:\n'
  if [[ -x /usr/bin/flatpak ]]; then
    /usr/bin/env PATH=/usr/bin:/bin /usr/bin/flatpak list --user --app --columns=application,version || true
  else
    echo 'Flatpak is not installed.'
  fi
  printf '\nUbuntu automatic security maintenance:\n'
  /usr/bin/systemctl is-enabled apt-daily.timer apt-daily-upgrade.timer || true
  printf '\nPending Ubuntu updates (cached package index):\n'
  /usr/bin/apt list --upgradable 2>/dev/null | cat || true
  printf '\nReboot status: '
  if [[ -r /var/run/reboot-required ]]; then cat /var/run/reboot-required; else echo 'No reboot requested by Ubuntu.'; fi
}
checkout="${SIMON_DESKTOP_CHECKOUT:-$HOME/src/simon-hp-os}"
build_only=false
pull=true
worker=false
attach=false
status_mode=
while (($#)); do
  case "$1" in
    --checkout) (($# >= 2)) || fail '--checkout requires a path'; checkout="$2"; shift 2 ;;
    --build-only) build_only=true; shift ;;
    --no-pull) pull=false; shift ;;
    --worker) worker=true; shift ;;
    --attach) attach=true; shift ;;
    --status) status_mode=plain; shift ;;
    --status-window) status_mode=window; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; fail "unknown argument: $1" ;;
  esac
done
if [[ -n "$status_mode" ]]; then
  status
  if [[ "$status_mode" == window && -t 0 ]]; then read -r -p 'Press Enter to close' || true; fi
  exit 0
fi
[[ "$pull" == true || "$build_only" == true ]] || fail '--no-pull requires --build-only'
[[ $(uname -m) == aarch64 ]] || fail 'Use an ARM64 host to build this desktop'
checkout=$(realpath "$checkout")
cd "$checkout"
[[ -f flake.nix && -f flake.lock && -f goran/installer/simon-home.nix ]] || fail 'Not a Simon desktop checkout'
[[ -z $(git status --porcelain) ]] || fail 'Checkout has local changes; commit or preserve them before updating'
if [[ "$build_only" == false ]]; then
  [[ $(id -un) == simon && "$HOME" == /home/simon ]] || fail 'Activate only from Simon’s own login session, without sudo'
  [[ "${XDG_RUNTIME_DIR:-}" == "/run/user/$(id -u)" ]] || fail 'Use a real Simon login session'
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "$ID" == ubuntu && "$VERSION_ID" == 26.04 ]] || fail 'This profile requires Ubuntu 26.04'
  [[ $(cat /sys/module/nvidia/version) == 615.78.08 ]] || fail 'Running NVIDIA driver must be 615.78.08'
  [[ -r /usr/lib/aarch64-linux-gnu/libpam.so.0 ]] || fail 'Ubuntu native PAM is unavailable'
fi
if [[ "$worker" == false ]]; then
  if [[ "$pull" == true ]]; then
    [[ $(git branch --show-current) == main ]] || fail 'Switch to branch main first'
    git pull --ff-only origin main
    [[ $(git rev-parse HEAD) == $(git rev-parse refs/remotes/origin/main) ]] || fail 'Local commits differ from the published update branch'
  fi
  args=(--worker --checkout "$checkout")
  [[ "$build_only" == false ]] || args+=(--build-only)
  [[ "$pull" == true ]] || args+=(--no-pull)
  if command -v nom-tmux >/dev/null; then
    tracker=$(command -v nom-tmux)
  else
    tracker="$checkout/pkgs/nom-dashboard/nom-tmux.sh"
  fi
  export NOM_DASHBOARD_ASSET_DIR="$checkout/pkgs/nom-dashboard/web"
  bash "$tracker" update-simon-desktop -- bash "$checkout/goran/installer/update-desktop.sh" "${args[@]}"
  if [[ "$attach" == true ]]; then exec tmux attach -t update-simon-desktop; fi
  exit 0
fi
[[ -n "${NOM_DASHBOARD_PROGRESS_FILE:-}" ]] || fail 'Internal worker must run through nom-tmux'
state="${XDG_STATE_HOME:-$HOME/.local/state}/simon-desktop-update"
mkdir -p "$state"
exec 9>"$state/update.lock"
flock -n 9 || fail 'Another Simon desktop update is running'
revision=$(git rev-parse HEAD)
# Git flakes include tracked files only. Evaluation checks the full import tree.
git ls-files --error-unmatch flake.nix flake.lock goran/installer/simon-home.nix \
  goran/installer/update-desktop.sh >/dev/null || fail 'Required desktop sources are not tracked in Git'
stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$state/$stamp"
mkdir -p "$run_dir"
printf '%s\n' "$revision" > "$run_dir/source-revision"
nix build .#homeConfigurations.simon-daytona.activationPackage \
  --no-update-lock-file --out-link "$run_dir/candidate"
candidate=$(readlink -f "$run_dir/candidate")
[[ -x "$candidate/activate" ]] || fail 'Built output has no Home Manager activation script'
[[ "$revision" == $(git rev-parse HEAD) && -z $(git status --porcelain) ]] || fail 'Source changed during the build; rebuild before activation'
if [[ "$build_only" == true ]]; then
  printf 'Built Simon desktop %s\nGeneration: %s\nNo profile activated.\n' "$revision" "$candidate"
  exit 0
fi
profile="${XDG_STATE_HOME:-$HOME/.local/state}/nix/profiles/home-manager"
previous=$(readlink -f "$profile" || true)
if [[ -n "$previous" && -x "$previous/activate" ]]; then
  nix-store --add-root "$run_dir/previous" --indirect --realise "$previous" >/dev/null
  printf '%s\n' "$previous" > "$run_dir/previous-generation"
fi
export HOME_MANAGER_BACKUP_EXT="simon-update-$stamp"
if "$candidate/activate" && [[ $(readlink -f "$profile") == "$candidate" ]]; then
  echo 'Activation completed and the Home Manager profile matches the candidate.'
else
  result=$?
  echo "Activation failed with exit $result; logs and candidate retained at $run_dir" >&2
  if [[ -n "$previous" && -x "$previous/activate" ]]; then
    echo 'Reactivating the previous Home Manager generation.' >&2
    "$previous/activate" || echo "Automatic rollback failed. Run $previous/activate from Simon’s console." >&2
  fi
  exit "$result"
fi
ln -sfn "$run_dir" "$state/current"
printf 'Simon desktop updated to %s\nGeneration: %s\n' "$revision" "$candidate"
printf 'Save work, then log out and select HP-OS (Simon N1X) to load the new compositor.\n'
printf 'Previous generation and update record: %s\n' "$run_dir"

# Flatpak uses this account's existing remotes and sign-ins. Never update the
# system installation or request privilege escalation from the desktop launcher.
if [[ -x /usr/bin/flatpak ]]; then
  echo 'Updating this account’s Flatpak applications and runtimes.'
  if ! /usr/bin/env PATH=/usr/bin:/bin /usr/bin/flatpak update --user --noninteractive; then
    echo 'Desktop activation succeeded; the user Flatpak update failed. Re-run Update Applications to retry.' >&2
    exit 1
  fi
else
  echo 'Flatpak is unavailable; the Home Manager desktop update is complete.'
fi
status
