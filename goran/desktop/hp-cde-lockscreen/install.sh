#!/usr/bin/env bash
# Scoped installation; Home Manager owns the same paths afterward.
set -euo pipefail
[[ $(id -un) == jonathan ]] || { echo 'Run as jonathan' >&2; exit 2; }
case $(hostname -s) in
  goran|krickstein|slazenger|armstrong|tweener|sampras|longlen) ;;
  *) echo 'Target is not a managed DMS desktop' >&2; exit 2 ;;
esac
stage_only=0
if [[ ${1:-} == --stage-only ]]; then stage_only=1; shift; fi
[[ $# == 3 ]] || { echo 'Usage: install.sh [--stage-only] BASE_QML_DIR DMS_BIN PYTHON3' >&2; exit 2; }
source_dir=$1; dms_bin=$2; python_bin=$3
[[ -f "$source_dir/Modules/Lock/LockScreenContent.qml" && -x "$dms_bin" && -x "$python_bin" ]]
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
# A failed session query is also a reason to defer activation.
can_restart() {
  local sessions sid hint
  sessions=$(loginctl list-sessions --no-legend) || return 1
  while read -r sid _; do
    [[ -n "$sid" ]] || continue
    hint=$(loginctl show-session "$sid" -p LockedHint --value) || return 1
    [[ $hint == no ]] || return 1
  done <<< "$sessions"
}
if ! can_restart; then
  echo 'A session is locked or its state is unavailable; staging without restarting DMS.'
  stage_only=1
fi
origin=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
assets="${XDG_DATA_HOME:-$HOME/.local/share}/hp-cde-lockscreen"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/dms.service.d"
backup="${XDG_STATE_HOME:-$HOME/.local/state}/hp-cde-lockscreen/$(date -u +%Y%m%dT%H%M%S.%NZ)"
# Validate all new assets against the host source before replacing any file.
candidate=$(mktemp -d)
trap 'rm -rf "$candidate"' EXIT
cp -rL "$source_dir"/. "$candidate"/
chmod -R u+w "$candidate"
"$python_bin" "$origin/dms-wifi-scan.py" "$candidate"
"$python_bin" "$origin/dms-hp-cde-lock.py" "$candidate" "$origin/hp-vue-banner.png" "$origin/CdeFrame.qml"
mkdir -p "$unit_dir" "$backup"
if [[ -d "$assets" ]]; then cp -rL "$assets" "$backup/assets"; fi
for name in 50-hp-cde-lockscreen.conf 90-hp-cde-lockscreen.conf; do
  if [[ -e "$unit_dir/$name" ]]; then cp -L "$unit_dir/$name" "$backup/$name"; fi
done
mkdir -p "$assets"
# Remove individual managed symlinks first; do not write through into the Nix store.
for name in dms-hp-cde-lock.py dms-wifi-scan.py CdeFrame.qml hp-vue-banner.png; do
  rm -f "$assets/$name"
  install -m 0644 "$origin/$name" "$assets/$name"
done
rm -f "$assets/run"
{ printf '#!%s\n' "$(command -v bash)"; tail -n +2 "$origin/run.sh"; } > "$assets/run"
chmod 0755 "$assets/run"
rm -f "$unit_dir/90-hp-cde-lockscreen.conf"
cat > "$unit_dir/90-hp-cde-lockscreen.conf" <<CONF
[Service]
Environment="DMS_CDE_SOURCE=$source_dir"
Environment="DMS_CDE_BIN=$dms_bin"
Environment="DMS_CDE_PYTHON=$python_bin"
ExecStart=
ExecStart=%h/.local/share/hp-cde-lockscreen/run
CONF
rm -f "$unit_dir/50-hp-cde-lockscreen.conf"
# Leave the running process and loaded unit untouched while locked.
if (( stage_only )) || ! can_restart; then
  printf 'HP CDE assets staged on %s; DMS was not restarted.\n' "$(hostname -s)"
  printf 'After unlocking, rerun this installer without --stage-only to activate. Backup: %s\n' "$backup"
  exit 0
fi
systemctl --user daemon-reload
if ! systemctl --user restart dms.service || ! systemctl --user is-active --quiet dms.service; then
  for name in 50-hp-cde-lockscreen.conf 90-hp-cde-lockscreen.conf; do
    rm -f "$unit_dir/$name"
    if [[ -f "$backup/$name" ]]; then cp "$backup/$name" "$unit_dir/$name"; fi
  done
  rm -rf "$assets"
  if [[ -d "$backup/assets" ]]; then cp -r "$backup/assets" "$assets"; fi
  systemctl --user daemon-reload
  if can_restart; then systemctl --user restart dms.service; fi
  echo 'Theme activation failed; restored prior assets and DMS start command.' >&2
  exit 1
fi
printf 'HP CDE lock visuals installed on %s; backup: %s\n' "$(hostname -s)" "$backup"
