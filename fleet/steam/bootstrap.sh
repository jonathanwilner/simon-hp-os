#!/usr/bin/env bash
# Run explicitly under nom-tmux. Keep client data outside the Nix store.
set -euo pipefail
export PATH=/usr/bin:/bin
[[ $EUID != 0 && $(uname -m) == aarch64 ]] || { echo 'Run as the ARM64 desktop user'; exit 2; }
. /etc/os-release
[[ $ID == ubuntu ]] || { echo 'This bootstrap supports Ubuntu ARM64'; exit 2; }
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
with_fex=true
user_only=false
for arg in "$@"; do
  case "$arg" in
    --client-only) with_fex=false ;;
    --user-only) user_only=true ;;
    *) echo 'Usage: hp-os-steam-bootstrap [--client-only] [--user-only]'; exit 2 ;;
  esac
done
mkdir -p "$HOME/.local/state/hp-os-steam"
exec 9>"$HOME/.local/state/hp-os-steam/bootstrap.lock"
flock -n 9 || { echo 'Another Steam bootstrap is running'; exit 1; }
if [[ $user_only == false ]]; then
  args=()
  [[ $with_fex == true ]] || args+=(--client-only)
  sudo bash "$source_dir/prepare-system.sh" "$(id -un)" "${args[@]}"
fi
python3 "$source_dir/gpu.py"
if [[ ! -x $HOME/.local/share/Steam/steamrtarm64/steam ]]; then
  python3 "$source_dir/install-steam-arm64.py"
fi
if [[ ! -x $HOME/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/pressure-vessel/bin/steam-runtime-launcher-service ]]; then
  bash "$source_dir/install-runtime-arm64.sh"
fi
if [[ $with_fex == true ]]; then
  rev=14c92681f4d62cf84d901460e0358de09c8847a7
  export FEX_BUILD_JOBS=${FEX_BUILD_JOBS:-4}
  [[ -x $HOME/.local/opt/fex-$rev/bin/FEX ]] || bash "$source_dir/build-fex.sh"
  bash "$source_dir/setup-fex-rootfs.sh"
  [[ -x $HOME/.local/opt/fex-steam-$rev/FEXCompatTool ]] || bash "$source_dir/build-fex-steam.sh"
  bash "$source_dir/install-fex-compat.sh"
fi
python3 "$source_dir/seed-desktop.py"
printf 'Steam client ready. Start steam from the desktop. FEX requested: %s\n' "$with_fex"
