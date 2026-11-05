# Shared clipboard UI and client. Device enrollment stays in private runtime files.
{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.relay;
  client = pkgs.writeShellApplication {
    name = "relay-agent";
    runtimeInputs = [ pkgs.python3 pkgs.wl-clipboard ];
    text = ''exec python3 ${./relay_agent.py} --config "$HOME/.config/relay/linux.json"'';
  };
  launcher = pkgs.writeShellApplication {
    name = "relay";
    runtimeInputs = [ pkgs.python3 pkgs.zenity pkgs.xdg-utils pkgs.systemd ];
    text = ''export PYTHONPATH=${./.}
      exec python3 ${./relay_setup.py} --config "$HOME/.config/relay/linux.json" "$@"'';
  };
  control = pkgs.writeShellApplication {
    name = "relay-control";
    runtimeInputs = [ pkgs.python3 pkgs.systemd ];
    text = ''export PYTHONPATH=${./.}
      exec python3 ${./relay-control.py} "$@"'';
  };
in {
  options.programs.hp-os-fleet.relay.enable = lib.mkEnableOption "Relay clipboard controls" // { default = true; };
  config = lib.mkIf (config.programs.hp-os-fleet.enable && cfg.enable && !(config.services.relayClipboard.enable or false)) {
    home.packages = [ client launcher control ];
    xdg.desktopEntries.Relay = {
      name = "Relay";
      genericName = "Clipboard sync";
      comment = "Connect devices and open clipboard history";
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
        ConditionPathExists = "%h/.config/relay/linux.json";
      };
      Service = {
        ExecCondition = "${pkgs.writeShellScript "relay-enrollment-enabled" ''
          exec ${pkgs.python3}/bin/python3 -c 'import json,pathlib,sys; p=pathlib.Path.home()/".config/relay/linux.json"; sys.exit(0 if json.loads(p.read_text()).get("enabled", False) else 1)'
        ''}";
        ExecStart = "${client}/bin/relay-agent";
        EnvironmentFile = "-%t/relay-clipboard.env";
        Restart = "on-failure";
        RestartSec = 15;
        UMask = "0077";
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadWritePaths = [ "-%h/.cache/relay" ];
        RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
    home.activation.relayCache = lib.hm.dag.entryBefore [ "reloadSystemd" ] ''
      run mkdir -p "$HOME/.cache/relay"
    '';
  };
}
