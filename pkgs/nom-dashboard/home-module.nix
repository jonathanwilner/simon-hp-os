{ config, lib, pkgs, ... }:
let
  cfg = config.services.nomDashboard;
  dashboard = pkgs.callPackage ../nom-dashboard.nix { };
in {
  options.services.nomDashboard = {
    enable = lib.mkEnableOption "shared nom task and progress reporting";
    enableTimer = lib.mkOption { type = lib.types.bool; default = true; };
    remote = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Central dashboard destination; empty publishes locally.";
    };
  };
  config = lib.mkIf cfg.enable {
    home.packages = [ dashboard ];
    xdg.configFile."nom-dashboard/reporting.env".text = ''
      export NOM_DASHBOARD_REMOTE=${lib.escapeShellArg cfg.remote}
    '';
    systemd.user.services.nom-dashboard-sync = lib.mkIf cfg.enableTimer {
      Unit.Description = "Publish machine task status and progress to the Nix dashboard";
      Service = {
        Type = "oneshot";
        ExecStart = "${dashboard}/bin/nom-dashboard-sync ${lib.escapeShellArg cfg.remote}";
        TimeoutStartSec = 90;
      };
    };
    systemd.user.timers.nom-dashboard-sync = lib.mkIf cfg.enableTimer {
      Unit.Description = "Refresh machine task progress every thirty seconds";
      Timer = { OnBootSec = "10s"; OnUnitActiveSec = "30s"; AccuracySec = "5s"; };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
