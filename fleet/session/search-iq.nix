# CPU-only local search service. Accounts opt in to the model download.
{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.session.searchIq;
  package = import ../../pkgs/hp-os-search-iq { inherit pkgs; };
in {
  options.programs.hp-os-fleet.session.searchIq.enable = lib.mkEnableOption "Ask IQ local CPU search service";
  config = lib.mkIf (config.programs.hp-os-fleet.enable && cfg.enable) {
    home.packages = [ package ];
    systemd.user.services.hp-os-search-iq = {
      Unit.Description = "Ask IQ local search assistant";
      Service = {
        ExecStart = "${package}/bin/hp-os-search-iq";
        Restart = "on-failure";
        RestartSec = 5;
        MemoryMax = "2G";
        CPUQuota = "200%";
        Nice = 10;
        NoNewPrivileges = true;
        PrivateTmp = true;
        UMask = "0077";
      };
      Install.WantedBy = [ "default.target" ];
    };
  };
}
