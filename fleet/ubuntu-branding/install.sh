#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 2; }
source /etc/os-release
[[ $ID == ubuntu ]] || { echo 'HP-OS branding integration requires Ubuntu.' >&2; exit 2; }
base=$(cd -- "$(dirname -- "$0")" && pwd)
user=${1:?Usage: hp-os-install-branding USER SESSION_ID [install|restore] [--login-only|--boot-only|--no-rebuild]}
session=${2:?Supply the Wayland session ID}
mode=${3:-install}
option=${4:-}
[[ $# -le 4 && ( $mode == install || $mode == restore ) ]] || exit 2
case $option in
  --login-only) exec /bin/bash "$base/install-login.sh" "$user" "$session" "$mode" ;;
  --boot-only) exec /bin/bash "$base/install-boot.sh" "$mode" ;;
  ''|--no-rebuild) ;;
  *) echo 'Unknown option' >&2; exit 2 ;;
esac
/bin/bash "$base/install-boot.sh" "$mode" ${option:+"$option"}
/bin/bash "$base/install-login.sh" "$user" "$session" "$mode"
