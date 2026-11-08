#!/usr/bin/env bash
# Steam local compatibility tool for Linux x86/x86-64 applications.
set -euo pipefail
export PATH=/usr/bin:/bin
rev=14c92681f4d62cf84d901460e0358de09c8847a7
depot=$HOME/.local/opt/fex-steam-$rev
verb=${1:-}
case "$verb" in
  run|waitforexitandrun) shift ;;
  *) printf 'Unsupported Steam compatibility verb: %s\n' "$verb" >&2; exit 2 ;;
esac
[[ ${1:-} == -- ]] && shift
(( $# > 0 )) || { echo 'Missing Linux game executable' >&2; exit 2; }
# FEX creates configuration within Steam's per-game compatibility data directory.
# This fallback also keeps manual tests separate from the standalone FEX config.
export STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-$HOME/.local/share/Steam/steamapps/compatdata/fex-local}
mkdir -p "$STEAM_COMPAT_DATA_PATH"
export FEX_ROOTFS=$HOME/.fex-emu/RootFS/Ubuntu_24_04.sqsh
export FEX_PORTABLE=1
export STEAM_COMPAT_FEX_CONFIG=${STEAM_COMPAT_FEX_CONFIG:-ThunksDB_Vulkan:1,ThunksDB_GL:1}
# Steam's native ARM64 libraries must not be injected into the x86 guest loader.
unset LD_PRELOAD LD_LIBRARY_PATH
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/gpu.py" --exec "$depot/FEXCompatTool" "$@"
