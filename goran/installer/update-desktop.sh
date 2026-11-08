#!/usr/bin/env bash
# Update the locked Simon desktop without changing Ubuntu or another user profile.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: simon-desktop-update [--checkout PATH] [--build-only] [--no-pull] [--development] [--attach]
       simon-desktop-update --status | --status-window

Merge the tested fleet-stable release with preserved local changes, build in nom-tmux,
and activate it as simon. --build-only never activates; --no-pull is allowed
only with --build-only for validating a committed integration branch.
--development explicitly selects unpromoted main instead of the tested release.
USAGE
}
fail() { echo "simon-desktop-update: $*" >&2; exit 1; }
status() {
  printf 'Application source: %s\n' "$checkout"
  local record="${XDG_STATE_HOME:-$HOME/.local/state}/simon-desktop-update/current"
  if [[ -r "$record/source-revision" ]]; then
    if [[ -r "$record/published-revision" ]]; then
      printf 'Installed published release: '; cat "$record/published-revision"
      printf 'Release channel: '; cat "$record/release-channel"
    fi
    printf 'Last successful desktop revision: '; cat "$record/source-revision"
    printf 'Desktop generation: %s\n' "$(readlink -f "$record/candidate")"
  fi
  local reporter="${HP_OS_FLEET_STATUS:-$checkout/fleet/release/status.py}"
  if [[ -r "$reporter" ]]; then
    python3 "$reporter" --checkout "$checkout" --installed-record "$record" \
      --active-generation "${XDG_STATE_HOME:-$HOME/.local/state}/nix/profiles/home-manager" || true
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
channel=fleet-stable
status_mode=
while (($#)); do
  case "$1" in
    --checkout) (($# >= 2)) || fail '--checkout requires a path'; checkout="$2"; shift 2 ;;
    --development) channel=main; shift ;;
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
  args=(--worker --checkout "$checkout")
  [[ "$build_only" == false ]] || args+=(--build-only)
  [[ "$pull" == true ]] || args+=(--no-pull)
  [[ "$channel" == fleet-stable ]] || args+=(--development)
  if command -v nom-tmux >/dev/null; then
    tracker=$(command -v nom-tmux)
  else
    tracker="$checkout/pkgs/nom-dashboard/nom-tmux.sh"
  fi
  export NOM_DASHBOARD_ASSET_DIR="$checkout/pkgs/nom-dashboard/web"
  bash "$tracker" update-simon-desktop -- bash "${BASH_SOURCE[0]}" "${args[@]}"
  if [[ "$attach" == true ]]; then exec tmux attach -t update-simon-desktop; fi
  exit 0
fi
[[ -n "${NOM_DASHBOARD_PROGRESS_FILE:-}" ]] || fail 'Internal worker must run through nom-tmux'
state="${XDG_STATE_HOME:-$HOME/.local/state}/simon-desktop-update"
mkdir -p "$state"
exec 9>"$state/update.lock"
flock -n 9 || fail 'Another Simon desktop update is running'
# Git flakes include tracked files only. Evaluation checks the full import tree.
git ls-files --error-unmatch flake.nix flake.lock goran/installer/simon-home.nix \
  goran/installer/update-desktop.sh >/dev/null || fail 'Required desktop sources are not tracked in Git'
stamp=$(date -u +%Y%m%dT%H%M%SZ)-$$
run_dir="$state/$stamp"
mkdir -p "$run_dir"
if [[ "$pull" == true ]]; then
  # Load the channel's merge tool before running checkout code. The checkout
  # may predate tested releases, while this installed updater already supports them.
  git fetch origin "refs/heads/$channel" || fail "Release channel $channel is unavailable; no fallback to main is permitted"
  git show FETCH_HEAD:goran/installer/merge-desktop-update.sh > "$run_dir/merge-desktop-update.sh"
  bash "$run_dir/merge-desktop-update.sh" "$checkout" "$run_dir/recovery" "$channel"
  cp "$run_dir/recovery/published-revision" "$run_dir/published-revision"
  cp "$run_dir/recovery/release-channel" "$run_dir/release-channel"
fi
[[ -z $(git status --porcelain) ]] || fail 'Build-only source must be committed; normal updates preserve and commit local edits automatically'
revision=$(git rev-parse HEAD)
# shellcheck source=desktop-update-guards.sh
source "$checkout/goran/installer/desktop-update-guards.sh"
printf '%s\n' "$revision" > "$run_dir/source-revision"
nix build .#homeConfigurations.simon-daytona.activationPackage \
  --no-update-lock-file --out-link "$run_dir/candidate"
candidate=$(readlink -f "$run_dir/candidate")
[[ -x "$candidate/activate" ]] || fail 'Built output has no Home Manager activation script'
require_stable_checkout "$revision" || exit 1
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
python3 "$checkout/goran/installer/snapshot-managed-files.py" "$HOME" "$candidate/home-files" "$run_dir/live-config"
require_stable_checkout "$revision" || exit 1
export HOME_MANAGER_BACKUP_EXT="simon-update-$stamp"
activate_with_rollback "$candidate" "$profile" "$previous" || exit $?
# Refresh an installed Owly service from this generation without interrupting
# an active radio session. Initial setup remains an explicit desktop action.
if [[ -e /etc/systemd/system/owlyd.service ]]; then
  if /usr/bin/sudo -n true 2>/dev/null; then
    /usr/bin/sudo "$HOME/.nix-profile/bin/hp-os-owly-install-system"
  else
    printf 'Open Set Up AirDrop to refresh the Owly system service.\n'
  fi
fi
# Refresh the explicitly configured printing adapter without restarting its radio.
# Refresh requires the same saved adapter and preserves its active session.
if [[ -f /etc/hp-os-aware-print-interface ]]; then
  if /usr/bin/sudo -n true 2>/dev/null; then
    /usr/bin/sudo "$HOME/.nix-profile/bin/hp-os-aware-install-system" --refresh "$(cat /etc/hp-os-aware-print-interface)"
  else
    printf 'Refresh Wi-Fi Aware setup: sudo hp-os-aware-install-system --refresh %s\n' "$(cat /etc/hp-os-aware-print-interface)"
  fi
fi
ln -sfn "$run_dir" "$state/current"
printf 'Simon desktop updated to %s\nGeneration: %s\n' "$revision" "$candidate"
printf 'Remote services: open Set Up Remote Access once to enable Sunshine and SSH. Tailscale stays unenrolled.\n'
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
