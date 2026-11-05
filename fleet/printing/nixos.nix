{ config, lib, pkgs, ... }:
let
  cfg = config.services.hp-os-aware-print;
  radio = pkgs.callPackage ./radio.nix {};
  interface = if cfg.interface == null then "unset" else cfg.interface;
in {
  options.services.hp-os-aware-print = {
    enable = lib.mkEnableOption "dedicated Wi-Fi Aware printing radio";
    interface = lib.mkOption {
      type = lib.types.nullOr (lib.types.strMatching "[a-zA-Z0-9_.-]{1,15}");
      default = null;
      description = "Dedicated spare wireless interface. Never select an adapter carrying the host uplink.";
    };
    users = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [];
      description = "Local users allowed to control the dedicated printing radio.";
    };
  };
  config = lib.mkIf cfg.enable {
    assertions = [{ assertion = cfg.interface != null; message = "Wi-Fi Aware printing requires an explicitly selected dedicated adapter."; }];
    users.groups.aware-print = {};
    users.users = lib.genAttrs cfg.users (_: { extraGroups = [ "aware-print" ]; });
    networking.networkmanager.unmanaged = [ "interface-name:${interface}" "interface-name:hposnan0" "interface-name:hposndi0" ];
    environment.systemPackages = [ (pkgs.callPackage ./package.nix {}) ];
    systemd.services.hp-os-aware-print-radio = {
      description = "Dedicated Wi-Fi Aware printing radio";
      after = [ "NetworkManager.service" ];
      # Explicit user start keeps radio use off after installation and reboot.
      serviceConfig = {
        Type = "simple";
        ExecStart = "${radio}/bin/hp-os-aware-radio run ${interface}";
        ExecStartPost = "${radio}/bin/hp-os-aware-radio setup ${interface}";
        RuntimeDirectory = "hp-os-aware-print";
        RuntimeDirectoryMode = "0750";
        Group = "aware-print";
        TimeoutStartSec = 20;
        TimeoutStopSec = 10;
        Restart = "no";
      };
    };
  };
}
