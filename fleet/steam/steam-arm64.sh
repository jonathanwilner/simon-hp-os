#!/usr/bin/env bash
set -euo pipefail
# Shell launchers may predate Xwayland startup. Recover the session's published
# X11 endpoint when absent, preserving an explicit caller display. Never pick
# an arbitrary /tmp/.X11-unix socket (the login greeter has a different one).
if [[ -z ${DISPLAY:-} ]]; then
  while IFS= read -r assignment; do
    case "$assignment" in
      DISPLAY=*) export DISPLAY="${assignment#DISPLAY=}" ;;
      XAUTHORITY=*) [[ -n ${XAUTHORITY:-} ]] || export XAUTHORITY="${assignment#XAUTHORITY=}" ;;
    esac
  done < <(@systemctl@ --user show-environment 2>/dev/null || true)
fi
# Niri starts Xwayland on demand, after the original shell environment was
# captured. A fresh login may not have imported DISPLAY into systemd either.
# Accept only one live Xwayland owned by this user, with its actual X socket.
if [[ -z ${DISPLAY:-} ]]; then
  displays=()
  for process in /proc/[0-9]*; do
    [[ -O $process && -r $process/comm && -r $process/cmdline ]] || continue
    IFS= read -r name < "$process/comm" || continue
    [[ $name == Xwayland ]] || continue
    while IFS= read -r -d '' arg; do
      if [[ $arg =~ ^:([0-9]+)$ && -S /tmp/.X11-unix/X${BASH_REMATCH[1]} ]]; then
        displays+=("$arg")
        break
      fi
    done < "$process/cmdline"
  done
  if [[ ${#displays[@]} == 1 ]]; then
    export DISPLAY="${displays[0]}"
  fi
fi

if [[ -z ${DISPLAY:-} ]]; then
  echo "Steam requires the desktop Xwayland display; the session has not published DISPLAY." >&2
  exit 1
fi

steam_root="$HOME/.local/share/Steam"
if [[ ! -x "$steam_root/steamrtarm64/steam" ]]; then
  echo "Steam ARM64 is missing. Run hp-os-steam-bootstrap first." >&2
  exit 1
fi
mkdir -p "$HOME/.steam" "$steam_root/logs"
if [[ ! -e "$HOME/.steam/steam" ]]; then
  ln -s "$steam_root" "$HOME/.steam/steam"
fi
if [[ ! -e "$HOME/.steam/root" ]]; then
  ln -s "$steam_root" "$HOME/.steam/root"
fi
export PATH="$steam_root/steamapps/common/SteamLinuxRuntime_4-arm64/pressure-vessel/bin:$HOME/.local/opt/fex-current/bin:$PATH"
export LD_LIBRARY_PATH="$steam_root/steamrtarm64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export STEAM_RUNTIME=0
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$steam_root"
cd "$steam_root"
while true; do
  status=0
  "@python@" "@gpu@" --exec "$steam_root/steamrtarm64/steam" -beta publicbeta "$@" || status=$?
  [[ $status == 42 ]] || exit "$status"
done
