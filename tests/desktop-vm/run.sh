#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == --raise-memlock ]]; then
  sudo prlimit --pid "$$" --memlock=unlimited
  shift
fi
export HPOS_VM_STATE="${HPOS_VM_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/hp-os-desktop-vm}"
mkdir -p "$HPOS_VM_STATE"
chmod 700 "$HPOS_VM_STATE"
if [[ ! -f "$HPOS_VM_STATE/id_ed25519" ]]; then
  ssh-keygen -q -t ed25519 -N '' -f "$HPOS_VM_STATE/id_ed25519"
fi
export NIX_DISK_IMAGE="$HPOS_VM_STATE/disk.qcow2"
vm_result=$(readlink -f "${HPOS_VM_RESULT:-./result-desktop-vm}")
nix-store --option min-free 0 --add-root "$HPOS_VM_STATE/running-vm" --indirect --realise "$vm_result" >/dev/null
exec "$vm_result/bin/run-hp-os-test-vm"
