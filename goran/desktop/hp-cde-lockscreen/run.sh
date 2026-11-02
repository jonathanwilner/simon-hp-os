#!/usr/bin/env bash
# Launch the existing DMS backend with a private, visually patched QML copy.
set -euo pipefail
: "${DMS_CDE_SOURCE:?Missing base DMS QML directory}"
: "${DMS_CDE_BIN:?Missing original DMS executable}"
: "${DMS_CDE_PYTHON:?Missing Python interpreter}"
assets="${XDG_DATA_HOME:-$HOME/.local/share}/hp-cde-lockscreen"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/hp-cde-lockscreen"
mkdir -p "$cache"
stage=$(mktemp -d "$cache/staging.XXXXXX")
trap 'rm -rf "$stage"' EXIT
cp -rL "$DMS_CDE_SOURCE"/. "$stage"/
chmod -R u+w "$stage"
"$DMS_CDE_PYTHON" "$assets/dms-wifi-scan.py" "$stage"
if ! "$DMS_CDE_PYTHON" "$assets/dms-hp-cde-lock.py" "$stage" "$assets/hp-vue-banner.png" "$assets/CdeFrame.qml"; then
  echo 'HP CDE visuals do not support this DMS revision; keeping original lock screen with Wi-Fi scan fix.' >&2
fi
# The service's previous process is stopped before ExecStart; keep one prior copy.
rm -rf "$cache/previous"
if [[ -d "$cache/shell" ]]; then mv "$cache/shell" "$cache/previous"; fi
mv "$stage" "$cache/shell"
trap - EXIT
exec "$DMS_CDE_BIN" -c "$cache/shell" run --session
