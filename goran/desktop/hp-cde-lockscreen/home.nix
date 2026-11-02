{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-cde-lockscreen;
  dms = config.programs.dank-material-shell.package;
  launcher = pkgs.writeShellScript "dms-hp-cde-run" (builtins.readFile ./run.sh);
  files = [ "dms-hp-cde-lock.py" "dms-wifi-scan.py" "CdeFrame.qml" "hp-vue-banner.png" ];
in {
  options.programs.hp-cde-lockscreen = {
    enable = lib.mkEnableOption "HP CDE visuals for the existing DMS lock screen";
    sourceDirectory = lib.mkOption {
      type = lib.types.str;
      default = "${dms}/share/quickshell/dms";
      description = "Existing DMS QML source, including any host-specific patches.";
    };
  };
  config = lib.mkIf cfg.enable {
    xdg.dataFile = builtins.listToAttrs (map (name: {
      name = "hp-cde-lockscreen/${name}";
      value = { source = ./. + "/${name}"; force = true; };
    }) files) // {
      "hp-cde-lockscreen/run" = { source = launcher; force = true; };
    };
    # Sort after messaging's 80-* override while retaining its ExecStartPre.
    xdg.configFile."systemd/user/dms.service.d/90-hp-cde-lockscreen.conf" = {
      force = true;
      text = ''
        [Service]
        Environment="DMS_CDE_SOURCE=${cfg.sourceDirectory}"
        Environment="DMS_CDE_BIN=${dms}/bin/dms"
        Environment="DMS_CDE_PYTHON=${pkgs.python3}/bin/python3"
        ExecStart=
        ExecStart=%h/.local/share/hp-cde-lockscreen/run
      '';
    };
  };
}
