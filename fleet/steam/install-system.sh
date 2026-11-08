#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root with desktop username'; exit 2; }
user=${1:?desktop username required}
[[ $user =~ ^[a-z_][a-z0-9_-]*$ && $user != root ]] || exit 2
user_home=$(getent passwd "$user" | cut -d: -f6)
[[ $user_home =~ ^/[a-zA-Z0-9_./-]+$ && $user_home != / ]] || exit 2
# Preserve the previously installed Goran policy when it already covers this
# user's native binaries; duplicate AppArmor attachments are ambiguous.
if [[ -f /etc/apparmor.d/steam-arm64 ]] &&
   grep -Fq "$user_home/.local/share/Steam/steamrtarm64/{steam,steamwebhelper}" /etc/apparmor.d/steam-arm64 &&
   grep -Eq '^[[:space:]]*userns,' /etc/apparmor.d/steam-arm64; then
  apparmor_parser -r /etc/apparmor.d/steam-arm64
  exit 0
fi
# Scoped Chromium sandbox permission. Other applications retain Ubuntu's policy.
policy=$(mktemp)
trap 'rm -f "$policy"' EXIT
cat > "$policy" <<POLICY
abi <abi/5.0>,
include <tunables/global>
profile hp-os-steam-$user $user_home/.local/share/Steam/steamrtarm64/{steam,steamwebhelper} flags=(unconfined) {
  userns,
  @{exec_path} mrix,
}
POLICY
apparmor_parser -Q "$policy"
install -m0644 "$policy" "/etc/apparmor.d/hp-os-steam-$user"
apparmor_parser -r "/etc/apparmor.d/hp-os-steam-$user"
