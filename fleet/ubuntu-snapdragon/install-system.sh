#!/usr/bin/env bash
# Install additive Ubuntu login integration after the Home Manager build.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root'; exit 1; }
. /etc/os-release
[[ $ID == ubuntu && $(uname -m) == aarch64 ]] || exit 1
user=${1:?desktop user required}
default_session=${2:-preserve}
[[ $default_session == preserve || $default_session == hp-os ]] || exit 2
[[ $user =~ ^[a-z_][a-z0-9_-]*$ ]] || exit 1
user_home=$(getent passwd "$user" | cut -d: -f6)
[[ -x $user_home/.nix-profile/bin/hp-os-session && -x $user_home/.nix-profile/bin/snapdragon-dms-session ]] || exit 1
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Retain the preceding integration for diagnosis or manual rollback.
backup=/var/lib/hp-os-snapdragon/integration-$(date -u +%Y%m%dT%H%M%SZ)-$$
install -d -m0700 "$backup"
for path in /etc/apparmor.d/chrome-nix /etc/pam.d/hp-os-snapdragon /etc/pam.d/hp-os-snapdragon-account /etc/pam.d/dankshell /etc/tmpfiles.d/snapdragon-nix-pam.conf /usr/local/bin/hp-os-login /usr/local/bin/snapdragon-dms-login /usr/local/libexec/hp-os-ubuntu-account-check /usr/share/wayland-sessions/hp-os-snapdragon.desktop /usr/share/wayland-sessions/dms-snapdragon.desktop; do
  [[ ! -e $path && ! -L $path ]] || cp -a --parents "$path" "$backup/"
done
# Permit the Nix Chrome sandbox through Ubuntu's scoped AppArmor policy.
install -m0644 "$source_dir/chrome-nix.apparmor" /etc/apparmor.d/chrome-nix
apparmor_parser -r /etc/apparmor.d/chrome-nix
install -d /usr/share/wayland-sessions /usr/local/bin
for session in hp-os snapdragon-dms; do
  cat > "/usr/local/bin/$session-login" <<SCRIPT
#!/bin/sh
[ ! -f /etc/profile.d/nix.sh ] || . /etc/profile.d/nix.sh
exec "\$HOME/.nix-profile/bin/$session-session" "\$@"
SCRIPT
  chmod 755 "/usr/local/bin/$session-login"
done
cat > /usr/share/wayland-sessions/hp-os-snapdragon.desktop <<'DESKTOP'
[Desktop Entry]
Name=HP-OS (Snapdragon)
Comment=HP-OS fleet desktop on Ubuntu ARM64
Exec=/usr/local/bin/hp-os-login
Type=Application
DesktopNames=HP-OS
DESKTOP
cat > /usr/share/wayland-sessions/dms-snapdragon.desktop <<'DESKTOP'
[Desktop Entry]
Name=Niri + DMS (Snapdragon)
Comment=Dank Material Shell on Ubuntu ARM64
Exec=/usr/local/bin/snapdragon-dms-login
Type=Application
DesktopNames=niri
DESKTOP
# Nix PAM delegates password checks to Ubuntu's packaged privileged helper.
helper=/usr/sbin/unix_chkpwd
[[ -x $helper && $(stat -c %u "$helper") == 0 && ( -g $helper || -u $helper ) ]]
target=/run/wrappers/bin/unix_chkpwd
if [[ -e $target || -L $target ]]; then
  [[ -L $target && $(readlink "$target") == "$helper" ]] || exit 1
fi
printf 'd /run/wrappers 0755 root root -\nd /run/wrappers/bin 0755 root root -\nL /run/wrappers/bin/unix_chkpwd - - - - /usr/sbin/unix_chkpwd\n' > /etc/tmpfiles.d/snapdragon-nix-pam.conf
systemd-tmpfiles --create /etc/tmpfiles.d/snapdragon-nix-pam.conf
# Nix PAM cannot parse Ubuntu's Debian-specific @include directives. Keep the
# system login stack intact and authenticate local desktop passwords explicitly.
install -d -m0755 /usr/local/libexec
install -m0755 -o root -g root "$user_home/.nix-profile/bin/hp-os-ubuntu-account-check" /usr/local/libexec/hp-os-ubuntu-account-check
printf 'account include common-account\n' > /etc/pam.d/hp-os-snapdragon-account
chmod 0644 /etc/pam.d/hp-os-snapdragon-account
cat > /etc/pam.d/hp-os-snapdragon <<'PAM'
auth optional pam_faildelay.so delay=3000000
auth requisite pam_nologin.so
auth required pam_unix.so
auth required pam_exec.so quiet /usr/local/libexec/hp-os-ubuntu-account-check
account required pam_unix.so
PAM
chmod 0644 /etc/pam.d/hp-os-snapdragon
# DMS detects this administrator-managed service before its bundled defaults.
printf 'auth include hp-os-snapdragon\naccount include hp-os-snapdragon\n' > /etc/pam.d/dankshell
chmod 0644 /etc/pam.d/dankshell
"$user_home/.nix-profile/bin/non-nixos-gpu-setup"
if [[ $default_session == hp-os ]]; then
  account="/org/freedesktop/Accounts/User$(id -u "$user")"
  busctl call org.freedesktop.Accounts "$account" org.freedesktop.Accounts.User SetXSession s hp-os-snapdragon
  busctl call org.freedesktop.Accounts "$account" org.freedesktop.Accounts.User SetSession s hp-os-snapdragon
  busctl call org.freedesktop.Accounts "$account" org.freedesktop.Accounts.User SetSessionType s wayland
fi
# Refresh the shared greeter on hosts that explicitly selected HP-OS branding.
# Boot-only branding preserves GDM and existing login/session selection. Custom
# initrds without matching modules require their original owning workflow.
can_rebuild=yes
for image in /boot/initrd.img-*; do
  [[ -e $image && ! -L $image ]] || continue
  [[ -d /lib/modules/${image#/boot/initrd.img-} ]] || can_rebuild=no
done
if [[ $can_rebuild == yes ]]; then
  "$user_home/.nix-profile/bin/hp-os-install-branding" "$user" hp-os-snapdragon install --boot-only
else
  echo 'Boot branding deferred: custom initrd has no matching installed kernel modules. Keep the working boot image and use its owning rebuild workflow.'
  touch "$backup/boot-branding-deferred"
fi
if [[ -e /var/lib/hp-os-ubuntu-branding/login/complete ]]; then
  "$user_home/.nix-profile/bin/hp-os-install-branding" "$user" hp-os-snapdragon install --login-only
fi
echo 'Both login options installed. Ubuntu GNOME and the active session are preserved.'
