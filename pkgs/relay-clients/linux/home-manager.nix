# Import this module, then set services.relayClipboard.enable and configFile.
{ config, lib, pkgs, ... }:
let
  cfg = config.services.relayClipboard;
  agent = pkgs.writeShellApplication {
    name = "relay-agent";
    runtimeInputs = [ pkgs.python3 pkgs.wl-clipboard ];
    text = ''exec python3 ${./relay_agent.py} "$@"'';
  };
  launcher = pkgs.writeShellApplication {
    name = "relay";
    runtimeInputs = [ pkgs.python3 pkgs.zenity pkgs.xdg-utils pkgs.systemd ];
    text = ''export PYTHONPATH=${./.}
      exec python3 ${./relay_setup.py} --config ${lib.escapeShellArg cfg.configFile} "$@"'';
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
    home.packages = [ agent launcher ];
    xdg.desktopEntries.Relay = {
      name = "Relay";
      genericName = "Clipboard sync";
      comment = "Set up Relay, connect devices, and open clipboard history";
      exec = "${launcher}/bin/relay";
      icon = "edit-paste";
      terminal = false;
      categories = [ "Utility" ];
    };
    systemd.user.services.relay-clipboard = {
      Unit = {
        Description = "Relay Wayland clipboard synchronization";
        PartOf = [ "graphical-session.target" ];
        After = [ "graphical-session.target" ];
        ConditionPathExists = cfg.configFile;
      };
      Service = {
        ExecStart = "${agent}/bin/relay-agent --config ${lib.escapeShellArg cfg.configFile}";
        EnvironmentFile = "-%t/relay-clipboard.env";
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
