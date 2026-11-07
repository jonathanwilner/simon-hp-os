#!@shell@
export QT_QUICK_CONTROLS_STYLE=Basic
# Quickshell may return zero for a missing IPC target or function. A successful
# void call is silent; diagnostic output must continue to the fallback panel.
ipc_ok() {
  local reply
  reply=$("$@" 2>&1) && [[ -z "$reply" ]]
}
if command -v hp-os >/dev/null 2>&1 && ipc_ok hp-os ipc hpos sharing; then
  exit 0
fi
if ipc_ok @quickshell@ ipc -p "@panel@" call omdrop open; then
  exit 0
fi
exec @quickshell@ -p "@panel@" --no-duplicate
