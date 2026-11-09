#!/usr/bin/env bash
# Separate privileged phase supports unattended deploys without password files.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 && $(uname -m) == aarch64 ]] || exit 2
. /etc/os-release
[[ $ID == ubuntu ]] || exit 2
user=${1:?desktop username required}
[[ $user =~ ^[a-z_][a-z0-9_-]*$ && $user != root ]] || exit 2
getent passwd "$user" >/dev/null
[[ ${2:-} == '' || ${2:-} == --client-only ]] || exit 2
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Retain Ubuntu's driver/kernel pairing. No NVIDIA driver is installed here.
apt-get install -y libgtk2.0-0t64 libsdl2-2.0-0 libasound2t64 libx11-6 libxrandr2 libxrender1 libxcb1 libegl1 libgl1 libvulkan1 mesa-utils vulkan-tools squashfs-tools squashfuse curl python3 apparmor
if python3 "$source_dir/gpu.py" | grep -q '"kind": "qualcomm"'; then
  apt-get install -y mesa-vulkan-drivers libgl1-mesa-dri
fi
if [[ ${2:-} != --client-only ]]; then
  apt-get install -y git build-essential cmake ninja-build clang-21 clang-tools-21 lld-21 llvm-21-dev libclang-21-dev nasm pkg-config libssl-dev libxxhash-dev qt6-base-dev qt6-declarative-dev libasound2-dev libdrm-dev libwayland-dev libegl-dev libgl-dev libx11-dev libxrandr-dev libxrender-dev libxcb1-dev libstdc++-14-dev-i386-cross libgcc-14-dev-i386-cross libstdc++-14-dev-amd64-cross libgcc-14-dev-amd64-cross
fi
bash "$source_dir/install-system.sh" "$user"
