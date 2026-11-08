#!/usr/bin/env bash
set -euo pipefail
rev=14c92681f4d62cf84d901460e0358de09c8847a7
prefix=${FEX_PREFIX:-$HOME/.local/opt/fex-$rev}
rootfs=$HOME/.fex-emu/RootFS/Ubuntu_24_04.sqsh
url=https://rootfs.fex-emu.gg/Ubuntu_24_04/2026-08-11/Ubuntu_24_04.sqsh
hash=3517e0e5ea25a473
mkdir -p "$(dirname "$rootfs")"
if [[ ! -f $rootfs ]]; then
  curl -fL --retry 3 "$url" -o "$rootfs.part"
  mv "$rootfs.part" "$rootfs"
fi
[[ $("$prefix/bin/FEXRootFSFetcher" "$rootfs") == *"has hash: $hash" ]] || {
  echo 'RootFS checksum mismatch; preserve and investigate downloaded image' >&2
  exit 1
}
# Preserve other settings if FEX was configured previously.
python3 - "$HOME/.fex-emu/Config.json" "$rootfs" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text()) if path.exists() else {}
data.setdefault('Config', {})['RootFS'] = sys.argv[2]
path.write_text(json.dumps(data, indent=2) + '\n')
PY
export FEX_ROOTFS="$rootfs"
[[ $("$prefix/bin/FEX" /usr/bin/uname -m) == x86_64 ]]
"$prefix/bin/FEX" /bin/bash -c 'printf "FEX x86-64 Bash execution passed\n"; /usr/bin/getconf LONG_BIT'
ln -sfn "$prefix" "$HOME/.local/opt/fex-current"
