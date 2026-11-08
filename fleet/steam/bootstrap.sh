#!/usr/bin/env bash
# Run explicitly under nom-tmux. Keep client data outside the Nix store.
set -euo pipefail
export PATH=/usr/bin:/bin
[[ $EUID != 0 && $(uname -m) == aarch64 ]] || { echo 'Run as the ARM64 desktop user'; exit 2; }
. /etc/os-release
[[ $ID == ubuntu ]] || { echo 'This bootstrap supports Ubuntu ARM64'; exit 2; }
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
with_fex=true
case "${1:-}" in
  --client-only) with_fex=false ;;
  '') ;;
  *) echo 'Usage: hp-os-steam-bootstrap [--client-only]'; exit 2 ;;
esac
mkdir -p "$HOME/.local/state/hp-os-steam"
exec 9>"$HOME/.local/state/hp-os-steam/bootstrap.lock"
flock -n 9 || { echo 'Another Steam bootstrap is running'; exit 1; }
# Retain the driver installed by Ubuntu. Never install an NVIDIA driver on
# behalf of another GPU, or replace the vendor kernel/userspace pairing.
sudo apt-get install -y libgtk2.0-0t64 libasound2t64 libx11-6 libxrandr2 libxrender1 libxcb1 libegl1 libgl1 libvulkan1 mesa-utils vulkan-tools squashfs-tools squashfuse curl python3 apparmor
python3 "$source_dir/gpu.py"
if python3 "$source_dir/gpu.py" | grep -q '"kind": "qualcomm"'; then
  sudo apt-get install -y mesa-vulkan-drivers libgl1-mesa-dri
fi
sudo bash "$source_dir/install-system.sh" "$(id -un)"
if [[ ! -x $HOME/.local/share/Steam/steamrtarm64/steam ]]; then
  python3 "$source_dir/install-steam-arm64.py"
fi
if [[ ! -x $HOME/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/pressure-vessel/bin/steam-runtime-launcher-service ]]; then
  bash "$source_dir/install-runtime-arm64.sh"
fi
if [[ $with_fex == true ]]; then
  rev=14c92681f4d62cf84d901460e0358de09c8847a7
  sudo apt-get install -y git build-essential cmake ninja-build clang-21 clang-tools-21 lld-21 llvm-21-dev libclang-21-dev nasm pkg-config libssl-dev libxxhash-dev qt6-base-dev qt6-declarative-dev libasound2-dev libdrm-dev libwayland-dev libegl-dev libgl-dev libx11-dev libxrandr-dev libxrender-dev libxcb1-dev libstdc++-14-dev-i386-cross libgcc-14-dev-i386-cross libstdc++-14-dev-amd64-cross libgcc-14-dev-amd64-cross
  export FEX_BUILD_JOBS=${FEX_BUILD_JOBS:-4}
  [[ -x $HOME/.local/opt/fex-$rev/bin/FEX ]] || bash "$source_dir/build-fex.sh"
  bash "$source_dir/setup-fex-rootfs.sh"
  [[ -x $HOME/.local/opt/fex-steam-$rev/FEXCompatTool ]] || bash "$source_dir/build-fex-steam.sh"
  bash "$source_dir/install-fex-compat.sh"
fi
python3 "$source_dir/seed-desktop.py"
printf 'Steam client ready. Start steam from the desktop. FEX requested: %s\n' "$with_fex"
