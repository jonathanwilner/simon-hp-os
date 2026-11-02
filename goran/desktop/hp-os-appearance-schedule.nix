{ config, lib, pkgs, ... }:
let
  cfg = config.programs.goran-hp-os.appearanceSchedule;
  scheduler = pkgs.writeShellScriptBin "hp-os-appearance-schedule" ''
    exec ${pkgs.python3}/bin/python3 ${./hp-os-appearance-schedule.py} \
      --sunwait ${pkgs.sunwait}/bin/sunwait \
      --appearance ${config.programs.hp-os.package}/bin/hp-os-appearance \
      --latitude ${toString cfg.latitude} --longitude ${toString cfg.longitude} "$@"
  '';
in {
  options.programs.goran-hp-os.appearanceSchedule = {
    enable = lib.mkEnableOption "local sunrise/sunset application appearance" // { default = true; };
    # Match the established DMS_THEME_LAT/LON fleet location in home.nix.
    latitude = lib.mkOption { type = lib.types.float; default = 34.05; description = "Latitude for local sunrise and sunset (Los Angeles by default)."; };
    longitude = lib.mkOption { type = lib.types.float; default = -118.24; description = "Longitude for local sunrise and sunset (Los Angeles by default)."; };
  };
  config = lib.mkIf (config.programs.goran-hp-os.enable && cfg.enable) {
    assertions = [
      { assertion = cfg.latitude >= -90 && cfg.latitude <= 90; message = "HP-OS appearance latitude must be between -90 and 90."; }
      { assertion = cfg.longitude >= -180 && cfg.longitude <= 180; message = "HP-OS appearance longitude must be between -180 and 180."; }
    ];
    home.packages = [ scheduler ];
    systemd.user.services.hp-os-appearance-schedule = {
      Unit.Description = "Apply sunrise/sunset appearance to the active HP-OS session";
      Service = { Type = "oneshot"; ExecStart = "${scheduler}/bin/hp-os-appearance-schedule"; TimeoutStartSec = 45; };
    };
    systemd.user.timers.hp-os-appearance-schedule = {
      Unit.Description = "Check HP-OS sunrise/sunset appearance every minute";
      Timer = { OnStartupSec = "10s"; OnUnitActiveSec = "1min"; AccuracySec = "1s"; };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
