#!/usr/bin/env bash
# Small online installer/updater. Run from the installed Ubuntu user's terminal.
set -euo pipefail
fail() { echo "hp-os-setup: $*" >&2; exit 1; }
revision=
channel=
build_only=false
while (($#)); do
  case "$1" in
    --source-revision|--channel)
      (($# >= 2)) || fail "$1 needs a value"
      if [[ $1 == --source-revision ]]; then revision=$2; else channel=$2; fi
      shift 2;;
    --build-only) build_only=true; shift;;
    -h|--help)
      echo 'Usage: bootstrap.sh --source-revision COMMIT [--build-only]'
      echo '       bootstrap.sh --channel fleet-stable [--build-only]'
      echo 'Install or update HP-OS in the current Ubuntu ARM64 account. Keep GNOME.'
      echo 'Requires Internet and sudo. Desktop packages download after Ubuntu install.'
      exit 0;;
    *) fail "Unknown option: $1";;
  esac
done
[[ $EUID != 0 ]] || fail 'Run as the installed desktop user, without sudo.'
[[ $(uname -m) == aarch64 ]] || fail 'This desktop requires Ubuntu ARM64.'
. /etc/os-release
[[ $ID == ubuntu ]] || fail 'This bootstrap requires Ubuntu.'
[[ ! -d /run/casper && ! -d /rofs ]] || fail 'Boot the installed Ubuntu system before setting up HP-OS.'
user=$(id -un)
[[ $user =~ ^[a-z_][a-z0-9_-]*$ && $HOME == "$(getent passwd "$user" | cut -d: -f6)" ]] || fail 'Use the actual desktop login and home directory.'
[[ -z $revision || -z $channel ]] || fail 'Select a revision or channel, not both.'
[[ -z $revision || $revision =~ ^[a-f0-9]{40}$ ]] || fail 'Source revision must be a full Git commit.'
[[ -z $channel || $channel == fleet-stable ]] || fail 'The supported release channel is fleet-stable.'
state=${XDG_STATE_HOME:-$HOME/.local/state}/hp-os-snapdragon
mkdir -p "$state"
exec 9>"$state/setup.lock"
flock -n 9 || fail 'Another HP-OS setup or update is already running.'
if [[ -z $revision && -z $channel ]]; then
  [[ -r $state/current/source-revision ]] || fail 'First setup requires --source-revision COMMIT or --channel fleet-stable.'
  revision=$(cat "$state/current/source-revision")
fi
sudo -v
sudo apt-get update
sudo apt-get install -y curl git tmux rsync ca-certificates python3 dbus-daemon brightnessctl xdg-desktop-portal-gnome xdg-desktop-portal-gtk apparmor-utils plymouth plymouth-themes
if ! command -v nix >/dev/null && [[ ! -x /nix/var/nix/profiles/default/bin/nix ]]; then
  installer=$(mktemp)
  curl --fail --location --proto '=https' --tlsv1.2 https://nixos.org/nix/install -o "$installer"
  # The official multi-user installer asks sudo for the system-owned daemon.
  sh "$installer" --daemon --yes
  rm -f "$installer"
fi
export PATH="/nix/var/nix/profiles/default/bin:$HOME/.nix-profile/bin:$PATH"
export NIX_CONFIG="${NIX_CONFIG:-}
experimental-features = nix-command flakes
max-jobs = 2
cores = 2
min-free = 0"
command -v nix >/dev/null || fail 'Nix installation did not provide nix.'
stamp=$(date -u +%Y%m%dT%H%M%SZ)-$$
run=$state/$stamp
mkdir -p "$run"
repo=https://github.com/jonathanwilner/simon-hp-os.git
git init -q "$run/source"
git -C "$run/source" remote add origin "$repo"
git -C "$run/source" fetch --depth=1 origin "${revision:-refs/heads/$channel}"
git -C "$run/source" checkout --detach -q FETCH_HEAD
revision=$(git -C "$run/source" rev-parse HEAD)
[[ -f $run/source/fleet/ubuntu-snapdragon/home.nix ]] || fail 'This release does not include Snapdragon. Keep the installed revision until a compatible fleet-stable release is published.'
printf '%s\n' "$revision" > "$run/source-revision"
# A generated, private consumer contains identity only. Shared features stay public.
python3 "$run/source/fleet/ubuntu-snapdragon/prepare-profile.py" "$run" "$user" "$HOME" "$revision"
tracker=$run/source/pkgs/nom-dashboard/nom-tmux.sh
export NOM_DASHBOARD_ASSET_DIR=$run/source/pkgs/nom-dashboard/web
export NOM_DASHBOARD_STATE_DIR=$state/tracking
session=install-hp-os-snapdragon
bash "$tracker" "$session" -- bash "$run/source/fleet/ubuntu-snapdragon/build-profile.sh" "$run" "$build_only"
echo "HP-OS is downloading and building. View progress: tmux attach -t $session"
status=$NOM_DASHBOARD_STATE_DIR/$session.status
while [[ ! -f $status ]]; do sleep 3; done
[[ $(cat "$status") == 0 ]] || fail "Build or activation failed. See $NOM_DASHBOARD_STATE_DIR/$session.log; rerun setup to retry."
[[ $build_only == false ]] || { echo "Built without activation: $run/candidate"; exit 0; }
# Privileged boot integration can rebuild initramfs. Track and await it too.
root_tracking=$state/system-tracking
sudo env NOM_DASHBOARD_STATE_DIR="$root_tracking" NOM_DASHBOARD_ASSET_DIR="$NOM_DASHBOARD_ASSET_DIR" bash "$tracker" install-hp-os-system -- bash "$run/source/fleet/ubuntu-snapdragon/install-system.sh" "$user"
while ! sudo test -f "$root_tracking/install-hp-os-system.status"; do sleep 3; done
[[ $(sudo cat "$root_tracking/install-hp-os-system.status") == 0 ]] || fail "Native integration failed. See $root_tracking/install-hp-os-system.log; rerun setup to retry."
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
# Repeatable updates default to this working pinned release. A tested channel is opt-in.
python3 "$run/source/fleet/ubuntu-snapdragon/prepare-profile.py" --launcher "$run" "$HOME"
ln -sfn "$run" "$state/current"
echo 'HP-OS installed. Save your work, log out, and select HP-OS (Snapdragon) or Niri + DMS.'
echo 'Ubuntu GNOME remains available. Run hp-os-snapdragon-update to retry/update this release.'
