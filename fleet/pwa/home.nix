{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.pwa;
  python = pkgs.python3.withPackages (ps: [ ps.websocket-client ]);
  repair = pkgs.writeShellScript "repair-chrome-pwa-launchers" ''
    exec ${pkgs.python3}/bin/python3 ${./launchers.py} \
      ${lib.escapeShellArg "${config.xdg.dataHome}/applications"} \
      ${lib.escapeShellArg "${config.home.profileDirectory}/bin/google-chrome-stable"} \
      ${lib.escapeShellArg "${config.home.homeDirectory}/.local/bin/hp-os-pwa-browser"} \
      ${lib.escapeShellArg "${config.home.homeDirectory}/.config/google-chrome-live-control"}
  '';
in {
  options.programs.hp-os-fleet.pwa.enable = lib.mkEnableOption
    "Chrome web app launchers and desktop light/dark appearance for the managed browser";

  config = lib.mkIf cfg.enable {
    home.file.".local/bin/hp-os-pwa-browser" = {
      source = import ./browser.nix { inherit pkgs; };
      executable = true;
    };
    home.activation.repairChromePwaLaunchers = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      run ${repair}
    '';
    systemd.user.paths.chrome-pwa-launchers = {
      Unit.Description = "Watch Chrome-generated web app launchers";
      Path.PathChanged = "${config.xdg.dataHome}/applications";
      Install.WantedBy = [ "default.target" ];
    };
    systemd.user.services.chrome-pwa-launchers = {
      Unit.Description = "Resolve Chrome web app launchers for the desktop session";
      Service = { Type = "oneshot"; ExecStart = toString repair; };
    };
    systemd.user.services.chrome-pwa-appearance = {
      Unit.Description = "Follow the desktop color scheme in Chrome web app windows";
      Service = {
        ExecStart = "${python}/bin/python3 ${./appearance.py}";
        Restart = "on-failure";
        RestartSec = 5;
      };
      Install.WantedBy = [ "default.target" ];
    };
  };
}
