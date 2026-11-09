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
notification_env="$XDG_RUNTIME_DIR/hp-os-fleet-notify-${WAYLAND_DISPLAY//\//_}.json"
python3 - "$notification_env" <<'PYENV'
import json, os, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({key: os.environ.get(key, '') for key in
    ('WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'NIRI_SOCKET')}))
PYENV
cleanup() {
  rm -f "$notification_env"
  if command -v relay-control >/dev/null; then
    relay-control session-stop >/dev/null 2>&1 || true
  fi
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

# Match only processes attached to this display or bus. Another login's
# clipboard or input method must not suppress this session's services.
session_has_process() {
  python3 - "$1" <<'PYCODE'
import os, pathlib, re, sys
pattern = re.compile(sys.argv[1])
for proc in pathlib.Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        if proc.stat().st_uid != os.getuid():
            continue
        cmd = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        if not pattern.search(cmd):
            continue
        env = dict(item.split(b'=', 1) for item in (proc / 'environ').read_bytes().split(b'\0') if b'=' in item)
        for key in ('WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS'):
            value = os.environ.get(key)
            if value and env.get(key.encode()) == value.encode():
                sys.exit(0)
    except (OSError, ValueError):
        continue
sys.exit(1)
PYCODE
}

if ! session_has_process '/wl-clip-persist( |$)'; then
  wl-clip-persist --clipboard both --write-timeout 5000 --reconnect-tries INF &
  children+=("$!")
fi
if ! session_has_process '/wl-paste .*--watch .*cliphist'; then
  wl-paste --watch cliphist store &
  children+=("$!")
fi
if [[ "${HP_OS_FLEET_INPUT_METHOD:-0}" == 1 && "${HP_OS_OWNED_SESSION:-}" != 1 ]] && ! session_has_process '/fcitx5( |$)'; then
  # Run in the foreground so the compositor supervisor owns its lifetime.
  fcitx5 &
  children+=("$!")
fi
if ! session_has_process '/(polkit[^ ]*agent[^ ]*|polkit-kde-authentication-agent-1|lxqt-policykit-agent|mate-polkit)( |$)'; then
  "$HP_OS_FLEET_POLKIT_AGENT" &
  children+=("$!")
fi
# Relay bridges to the real user manager and records this display without
# exporting HP-OS's private D-Bus. This is a no-op until explicitly enrolled.
if command -v relay-control >/dev/null; then
  relay-control session-start || echo "Relay session startup unavailable" >&2
fi
# Niri removes its IPC socket at session exit. This keeps services tied to the
# correct compositor without requiring a systemd manager on the private bus.
while [[ -S "$NIRI_SOCKET" ]]; do
  sleep 2
done
