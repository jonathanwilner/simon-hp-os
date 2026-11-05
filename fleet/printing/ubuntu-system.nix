{ writeShellApplication, callPackage, coreutils, gnugrep, iproute2, python3 }:
let radio = callPackage ./radio.nix {};
in writeShellApplication {
  name = "hp-os-aware-install-system";
  runtimeInputs = [ coreutils gnugrep iproute2 python3 ];
  excludeShellChecks = [ "SC1091" ];
  text = ''
    [[ $EUID -eq 0 ]] || { echo 'Run with sudo and an explicitly selected dedicated adapter.' >&2; exit 1; }
    source /etc/os-release
    [[ "$ID" == ubuntu ]] || { echo 'Ubuntu only. NixOS uses nixosModules.aware-printing.' >&2; exit 1; }
    refresh=false
    if [[ "''${1:-}" == --refresh ]]; then
      refresh=true
      shift
    fi
    interface="''${1:-}"
    user="''${SUDO_USER:-}"
    [[ "$interface" =~ ^[a-zA-Z0-9_.-]{1,15}$ && -n "$user" && "$user" != root ]] || {
      echo 'Usage: sudo hp-os-aware-install-system DEDICATED_INTERFACE' >&2; exit 2;
    }
    if [[ "$refresh" == true ]]; then
      [[ -f /etc/hp-os-aware-print-interface && -f /etc/systemd/system/hp-os-aware-print-radio.service ]] || {
        echo 'No existing radio installation to refresh.' >&2; exit 1;
      }
      [[ $(cat /etc/hp-os-aware-print-interface) == "$interface" ]] || {
        echo 'Refresh must retain the configured dedicated adapter.' >&2; exit 1;
      }
    else
      ${radio}/bin/hp-os-aware-radio check "$interface"
      if [[ -f /etc/hp-os-aware-print-interface ]] && [[ $(cat /etc/hp-os-aware-print-interface) != "$interface" ]]; then
        echo 'A different printing adapter is already configured. Stop and remove that setup before selecting another.' >&2; exit 1
      fi
    fi
    /usr/bin/getent group aware-print >/dev/null || /usr/sbin/groupadd --system aware-print
    /usr/sbin/usermod -aG aware-print "$user"
    install -d /etc/NetworkManager/conf.d /etc/systemd/system /nix/var/nix/gcroots/hp-os-aware-print
    ln -sfn ${radio} /nix/var/nix/gcroots/hp-os-aware-print/radio
    printf '%s\n' "$interface" > /etc/hp-os-aware-print-interface
    cat > /etc/NetworkManager/conf.d/92-hp-os-aware-print.conf <<CONFIG
    [device-hp-os-aware-base]
    match-device=interface-name:$interface
    managed=0
    [device-hp-os-aware-nan]
    match-device=interface-name:hposnan0
    managed=0
    [device-hp-os-aware-ndi]
    match-device=interface-name:hposndi0
    managed=0
    CONFIG
    cat > /etc/systemd/system/hp-os-aware-print-radio.service <<UNIT
    [Unit]
    Description=Dedicated Wi-Fi Aware printing radio
    After=NetworkManager.service
    [Service]
    Type=simple
    Group=aware-print
    RuntimeDirectory=hp-os-aware-print
    RuntimeDirectoryMode=0750
    ExecStart=${radio}/bin/hp-os-aware-radio run $interface
    ExecStartPost=${radio}/bin/hp-os-aware-radio setup $interface
    TimeoutStartSec=20
    TimeoutStopSec=10
    Restart=no
    UNIT
    /usr/bin/systemctl daemon-reload
    if [[ "$refresh" == false ]]; then
      /usr/bin/nmcli general reload conf
      /usr/bin/nmcli device set "$interface" managed no
    fi
    if [[ "$refresh" == true ]]; then
      echo 'Updated package references. Existing radio session continues until you stop and start it.'
      exit 0
    fi
    echo 'Installed. Log out and back in for printing-group access.'
    echo 'Start the dedicated radio with: sudo systemctl start hp-os-aware-print-radio'
    echo 'Stop it with: sudo systemctl stop hp-os-aware-print-radio'
    echo 'The radio remains off until explicitly started.'
  '';
}
