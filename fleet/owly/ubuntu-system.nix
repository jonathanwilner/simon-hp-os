{ lib, writeShellApplication, callPackage, owly, owlySource, coreutils, radioConfig ? null, desktopUser ? null
, omdrop ? callPackage ./omdrop-package.nix { inherit owlySource; } }:
writeShellApplication {
  name = "hp-os-owly-install-system";
  excludeShellChecks = [ "SC1091" ];
  runtimeInputs = [ coreutils ];
  text = ''
    [[ $EUID -eq 0 ]] || { echo 'Run with sudo to install the Owly system service.' >&2; exit 1; }
    # Ubuntu owns networking and system services. Keep native nmcli matched
    # with its running NetworkManager; all Owly binaries remain Nix-owned.
    source /etc/os-release
    [[ "$ID" == ubuntu ]] || { echo 'Ubuntu only. NixOS uses desktop-fleet.nixosModules.owly.' >&2; exit 1; }
    desktop_user=${lib.escapeShellArg (if desktopUser == null then "" else desktopUser)}
    if [[ -z "$desktop_user" ]]; then desktop_user="''${SUDO_USER:-}"; fi
    [[ -n "$desktop_user" && "$desktop_user" != root ]] || { echo 'Run through sudo as the desktop user.' >&2; exit 1; }
    /usr/bin/id "$desktop_user" >/dev/null
    /usr/sbin/groupadd -f omdrop
    /usr/sbin/usermod -aG omdrop "$desktop_user"
    install -d /etc/polkit-1/rules.d
    install -m 0644 ${builtins.toFile "49-hp-os-omdrop.rules" (import ./radio-policy.nix)} /etc/polkit-1/rules.d/49-hp-os-omdrop.rules
    package=${owly}
    install -d /etc/systemd/system/owlyd.service.d /etc/dbus-1/system.d \
      /usr/share/dbus-1/system-services /usr/share/polkit-1/actions \
      /etc/NetworkManager/conf.d /etc/systemd/network /nix/var/nix/gcroots/owly
    ln -sfn "$package" /nix/var/nix/gcroots/owly/package
    ln -sfn ${omdrop} /nix/var/nix/gcroots/owly/omdrop
    ln -sfn ${omdrop}/share/polkit-1/actions/org.omarchy.omdrop.radio.policy /usr/share/polkit-1/actions/org.omarchy.omdrop.radio.policy
    ln -sfn "$package/lib/systemd/system/owlyd.service" /etc/systemd/system/owlyd.service
    ln -sfn "$package/share/dbus-1/system.d/io.github.t4t5.Owly.conf" /etc/dbus-1/system.d/io.github.t4t5.Owly.conf
    ln -sfn "$package/share/dbus-1/system-services/io.github.t4t5.Owly.service" /usr/share/dbus-1/system-services/io.github.t4t5.Owly.service
    ln -sfn "$package/share/polkit-1/actions/io.github.t4t5.Owly.policy" /usr/share/polkit-1/actions/io.github.t4t5.Owly.policy
    ln -sfn "$package/lib/NetworkManager/conf.d/90-owly-unmanaged.conf" /etc/NetworkManager/conf.d/90-owly-unmanaged.conf
    ln -sfn "$package/lib/systemd/network/10-owly-awdl0.link" /etc/systemd/network/10-owly-awdl0.link
    printf '[Service]\nEnvironment=PATH=/usr/sbin:/usr/bin:/sbin:/bin\n' > /etc/systemd/system/owlyd.service.d/native-tools.conf
    ${lib.optionalString (radioConfig != null) ''
      install -d /etc/owly
      ln -sfn ${radioConfig} /etc/owly/radio.toml
      ln -sfn ${radioConfig} /nix/var/nix/gcroots/owly/radio-config
    ''}
    /usr/bin/systemctl daemon-reload
    /usr/bin/systemctl reload dbus
    /usr/bin/udevadm control --reload
    /usr/bin/nmcli general reload conf
    # D-Bus activates the daemon when requested. Never start a radio lease
    # or restart a running lease as part of installation or update.
    printf 'Owly system integration installed from %s. Radio remains user-controlled.\n' "$package"
  '';
}
