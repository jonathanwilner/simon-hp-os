{ config, lib, pkgs, ... }:
let cfg = config.programs.hp-os-fleet.desktopControls;
in {
  options.programs.hp-os-fleet.desktopControls.enable =
    lib.mkEnableOption "portable HP-OS battery, notification and file manager controls";
  config = lib.mkIf cfg.enable {
    home.packages = [ pkgs.cosmic-files ];
    home.activation.hpOsFleetDesktopControls = lib.hm.dag.entryAfter [ "linkGeneration" "hposNiriBindings" ] ''
      run ${pkgs.python3}/bin/python3 ${./migrate.py} \
        ${lib.escapeShellArg "${config.xdg.configHome}/hp-os/config.json"} \
        ${lib.escapeShellArg "${config.xdg.stateHome}/hp-os-fleet/desktop-controls-v1"}
    '';
  };
}
