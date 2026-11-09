# Niri starts this supervisor after exposing its session environment. Running
# under the compositor also supports HP-OS's private dbus-run-session bus.
: "${XDG_RUNTIME_DIR:?A graphical session is required}"
: "${WAYLAND_DISPLAY:?A Wayland session is required}"
: "${NIRI_SOCKET:?A Niri session is required}"
[[ -S "$NIRI_SOCKET" ]] || exit 1
umask 077
exec 9>"$XDG_RUNTIME_DIR/hp-os-fleet-session-${WAYLAND_DISPLAY//\//_}.lock"
flock -n 9 || exit 0
children=()
cleanup() {
  if (( ${#children[@]} )); then
    kill "${children[@]}" 2>/dev/null || true
    wait "${children[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 0' INT TERM HUP

# Do not export HP-OS's private bus to the global user manager: that would
# redirect services belonging to another desktop/login session.
if [[ "${HP_OS_OWNED_SESSION:-}" != 1 ]]; then
  systemctl --user import-environment WAYLAND_DISPLAY NIRI_SOCKET XDG_CURRENT_DESKTOP XDG_SESSION_TYPE DBUS_SESSION_BUS_ADDRESS || true
  dbus-update-activation-environment --systemd WAYLAND_DISPLAY NIRI_SOCKET XDG_CURRENT_DESKTOP XDG_SESSION_TYPE DBUS_SESSION_BUS_ADDRESS || true
  systemctl --user start graphical-session.target || true
fi

# Existing Goran services and desktop-owned watchers remain authoritative.
# The shared helper starts only missing processes and owns only its children.
if ! pgrep -u "$(id -u)" -x wl-clip-persist >/dev/null; then
  wl-clip-persist --clipboard both --write-timeout 5000 --reconnect-tries INF &
  children+=("$!")
fi
if ! pgrep -u "$(id -u)" -f 'wl-paste .*--watch .*cliphist' >/dev/null; then
  wl-paste --watch cliphist store &
  children+=("$!")
fi
if [[ "${HP_OS_FLEET_INPUT_METHOD:-0}" == 1 && "${HP_OS_OWNED_SESSION:-}" != 1 ]] && ! pgrep -u "$(id -u)" -x fcitx5 >/dev/null; then
  # Run in the foreground so the compositor supervisor owns its lifetime.
  fcitx5 &
  children+=("$!")
fi
# Niri removes its IPC socket at session exit. This keeps services tied to the
# correct compositor without requiring a systemd manager on the private bus.
while [[ -S "$NIRI_SOCKET" ]]; do
  sleep 2
done
