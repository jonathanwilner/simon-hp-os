{ lib, writeShellApplication, writeText, callPackage, iproute2, iw, coreutils, gnugrep, python3 }:
let
  supplicant = callPackage ./supplicant.nix {};
  config = writeText "hp-os-aware-wpa.conf" ''
    ctrl_interface=DIR=/run/hp-os-aware-print/wpa GROUP=aware-print
    update_config=0
    ap_scan=0
    p2p_disabled=1
  '';
in writeShellApplication {
  name = "hp-os-aware-radio";
  runtimeInputs = [ supplicant iproute2 iw coreutils gnugrep python3 ];
  text = ''
    mode="''${1:-}"
    interface="''${2:-}"
    [[ "$interface" =~ ^[a-zA-Z0-9_.-]{1,15}$ ]] || { echo 'Specify one dedicated wireless interface.' >&2; exit 2; }
    runtime=/run/hp-os-aware-print
    case "$mode" in
      run|check)
        [[ $EUID -eq 0 ]] || { echo 'Radio provisioning requires root.' >&2; exit 1; }
        phy=$(readlink -f "/sys/class/net/$interface/phy80211")
        [[ -d "$phy" ]] || { echo 'Selected adapter has no wireless PHY.' >&2; exit 1; }
        # All interfaces sharing this physical radio must be unused.
        for candidate in /sys/class/net/*; do
          [[ $(readlink -f "$candidate/phy80211" 2>/dev/null || true) == "$phy" ]] || continue
          name=$(basename "$candidate")
          ip -j address show dev "$name" | python3 -c 'import json,sys; a=json.load(sys.stdin); sys.exit(1 if any(x.get("addr_info") for x in a) else 0)' || {
            echo "Radio interface $name has IP addresses. Refusing to disrupt it." >&2; exit 1;
          }
          if [[ -n $(ip route show dev "$name") || -n $(ip -6 route show dev "$name") ]] || iw dev "$name" link 2>/dev/null | grep -q '^Connected to'; then
            echo "Radio interface $name is routed or associated. Select a dedicated spare adapter." >&2; exit 1
          fi
        done
        if [[ "$mode" == check ]]; then exit 0; fi
        runtime=/run/hp-os-aware-print
        mkdir -p "$runtime/wpa"
        chmod 0750 "$runtime" "$runtime/wpa"
        chgrp aware-print "$runtime" "$runtime/wpa"
        install -m 0660 -g aware-print /dev/null "$runtime/session.lock"
        exec wpa_supplicant -Dnl80211 -i "$interface" -c ${config} -g "$runtime/global"
        ;;
      setup)
        for _ in $(seq 1 50); do
          if [[ -S "$runtime/global" ]]; then break; fi
          sleep 0.1
        done
        global() {
          local result
          result=$(wpa_cli -g "$runtime/global" raw "$@")
          [[ "$result" == OK ]] || { printf '%s\n' "$result" >&2; return 1; }
        }
        local_command() {
          local result
          result=$(wpa_cli -p "$runtime/wpa" -i hposnan0 raw "$@")
          [[ "$result" == OK ]] || { printf '%s\n' "$result" >&2; return 1; }
        }
        global $'INTERFACE_ADD hposnan0\t\tnl80211\tDIR=/run/hp-os-aware-print/wpa GROUP=aware-print\t\t\tcreate\tnan'
        local_command NAN_SET master_pref 10
        local_command NAN_SET dual_band 0
        local_command NAN_START
        local_command NAN_SCHED_CONFIG_MAP map_id=1 2437:0e000000
        global $'INTERFACE_ADD hposndi0\t\tnl80211\tDIR=/run/hp-os-aware-print/wpa GROUP=aware-print\t\t\tcreate\tnan_data'
        ip link set hposndi0 addrgenmode eui64
        ip link set hposndi0 up
        ;;
      *) echo 'Usage: hp-os-aware-radio run|setup DEDICATED_INTERFACE' >&2; exit 2 ;;
    esac
  '';
}
