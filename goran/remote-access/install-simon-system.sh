#!/usr/bin/env bash
# Run after the Simon Home Manager generation has activated.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo after the desktop update.' >&2; exit 2; }
[[ $(uname -m) == aarch64 ]] || { echo 'ARM64 is required' >&2; exit 2; }
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 26.04 ]] || { echo 'Ubuntu 26.04 is required' >&2; exit 2; }
user=simon
home=$(getent passwd "$user" | cut -d: -f6)
[[ $home == /home/simon ]] || exit 2
# Initial setup and regular updates consume the same shared fleet branding.
source_dir=$(cd -- "$(dirname -- "$0")" && pwd)
bash "$source_dir/../../fleet/ubuntu-branding/refresh-managed.sh" "$user"
manifest="$home/.config/hp-os/remote-access.json"
[[ -r $manifest ]] || { echo 'Activate the updated Simon profile first.' >&2; exit 2; }
mapfile -t binaries < <(python3 - "$manifest" <<'PY'
import json,sys
value=json.load(open(sys.argv[1]))
for name in ('sunshine','tailscaled'):
    print(value[name])
PY
)
[[ ${#binaries[@]} == 2 ]] || exit 2
sunshine=${binaries[0]}
tailscaled=${binaries[1]}
[[ $sunshine == /nix/store/*/bin/sunshine-* && -x $sunshine ]] || exit 2
[[ $tailscaled == /nix/store/*/bin/tailscaled && -x $tailscaled ]] || exit 2
# Validate SSH before changing packages; retain configuration and host keys.
if [[ -x /usr/sbin/sshd ]]; then /usr/sbin/sshd -t; fi
apt-get update
apt-get install -y -o Dpkg::Options::=--force-confold openssh-server libcap2-bin curl
/usr/sbin/sshd -t
systemctl enable --now ssh.service
getent group plugdev >/dev/null || groupadd --system plugdev
for group in plugdev video render input; do
  getent group "$group" >/dev/null && usermod -aG "$group" "$user"
done
install -d -m 0755 /usr/local/libexec
install -m 0750 -o root -g plugdev "$sunshine" /usr/local/libexec/hp-os-sunshine.new
setcap cap_sys_admin+p /usr/local/libexec/hp-os-sunshine.new
mv -f /usr/local/libexec/hp-os-sunshine.new /usr/local/libexec/hp-os-sunshine
printf 'uinput\nuhid\n' > /etc/modules-load.d/hp-os-sunshine.conf
modprobe uinput
modprobe uhid
cat > /etc/udev/rules.d/85-hp-os-sunshine.rules <<'RULES'
KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="plugdev", MODE="0660", OPTIONS+="static_node=uinput"
KERNEL=="uhid", SUBSYSTEM=="misc", GROUP="plugdev", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="card[0-9]*", GROUP="plugdev", MODE="0660"
RULES
udevadm control --reload-rules
udevadm trigger --subsystem-match=misc --sysname-match=uinput
udevadm trigger --subsystem-match=misc --sysname-match=uhid
udevadm trigger --subsystem-match=drm
# Respect an existing Tailscale installation and its credentials. A new daemon
# starts logged out. This script never runs tailscale up, login, or an auth key.
if ! systemctl cat tailscaled.service >/dev/null 2>&1 || grep -q "# HP-OS managed Tailscale unit" /etc/systemd/system/tailscaled.service 2>/dev/null; then
  cat > /etc/systemd/system/tailscaled.service <<UNIT
# HP-OS managed Tailscale unit
[Unit]
Description=Tailscale daemon (enrollment remains manual)
After=network-pre.target
Wants=network-pre.target
[Service]
ExecStart=$tailscaled --state=/var/lib/tailscale/tailscaled.state --socket=/run/tailscale/tailscaled.sock
StateDirectory=tailscale
RuntimeDirectory=tailscale
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
fi
install -d -m 0755 /nix/var/nix/gcroots/hp-os-remote
ln -sfn "${sunshine%/bin/*}" /nix/var/nix/gcroots/hp-os-remote/sunshine
if grep -q "# HP-OS managed Tailscale unit" /etc/systemd/system/tailscaled.service 2>/dev/null; then
  ln -sfn "${tailscaled%/bin/*}" /nix/var/nix/gcroots/hp-os-remote/tailscale
fi
systemctl daemon-reload
systemctl enable --now tailscaled.service
loginctl enable-linger "$user"
uid=$(id -u "$user")
runuser -u "$user" -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" systemctl --user restart sunshine.service
printf 'SSH and Tailscale daemon enabled. No Tailscale enrollment was performed.\n'
printf 'Sunshine started. Set its own credentials and pair Moonlight at https://localhost:47990.\n'
printf 'Existing Sunshine settings, SSH keys and Tailscale state were preserved.\n'
printf 'If this account just gained device groups, log out and back in before streaming.\n'
systemctl is-active ssh.service tailscaled.service
for attempt in {1..20}; do
  if /usr/bin/curl --insecure --silent --fail --max-time 2 https://127.0.0.1:47990/ >/dev/null; then
    echo 'Sunshine web interface responds on port 47990.'
    exit 0
  fi
  sleep 1
done
echo 'Sunshine setup is installed, but its web interface is not ready. Check journalctl --user -u sunshine; a new device group may require logout/login.' >&2
exit 1
