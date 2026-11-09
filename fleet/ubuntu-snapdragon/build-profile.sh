#!/usr/bin/env bash
set -euo pipefail
run=$(realpath "${1:?run directory}")
build_only=${2:?build-only flag}
cd "$run/profile"
# Local identity lives in this generated path flake; all public inputs are pinned.
nix flake lock
python3 "$run/source/fleet/release/client_build.py" "path:$PWD#homeConfigurations.desktop.activationPackage" --out-link "$run/candidate"
[[ $build_only == false ]] || exit 0
profile=${XDG_STATE_HOME:-$HOME/.local/state}/nix/profiles/home-manager
previous=$(readlink -f "$profile" || true)
if [[ -n $previous && -x $previous/activate ]]; then
  nix-store --add-root "$run/previous" --indirect --realise "$previous" >/dev/null
fi
source "$run/source/goran/installer/desktop-update-guards.sh"
export HOME_MANAGER_BACKUP_EXT="hp-os-$(basename "$run")"
activate_with_rollback "$(readlink -f "$run/candidate")" "$profile" "$previous"
