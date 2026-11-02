# Import this module, then set services.relayClipboard.enable and configFile.
{ config, lib, pkgs, ... }:
let
  cfg = config.services.relayClipboard;
  agent = pkgs.writeShellApplication {
    name = "relay-agent";
    runtimeInputs = [ pkgs.python3 pkgs.wl-clipboard ];
    text = ''exec python3 ${./relay_agent.py} "$@"'';
  };
in {
  options.services.relayClipboard = {
    enable = lib.mkEnableOption "Relay Wayland clipboard synchronization";
    configFile = lib.mkOption {
      type = lib.types.str;
      default = "${config.xdg.configHome}/relay/linux.json";
      description = "Private runtime JSON config. Credentials must never enter the Nix store.";
    };
  };
  config = lib.mkIf cfg.enable {
    home.packages = [ agent ];
    systemd.user.services.relay-clipboard = {
      Unit = {
        Description = "Relay Wayland clipboard synchronization";
        PartOf = [ "graphical-session.target" ];
        After = [ "graphical-session.target" ];
        ConditionPathExists = cfg.configFile;
      };
      Service = {
        ExecStart = "${agent}/bin/relay-agent --config ${lib.escapeShellArg cfg.configFile}";
        Restart = "on-failure";
        RestartSec = 15;
        UMask = "0077";
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
  };
}
