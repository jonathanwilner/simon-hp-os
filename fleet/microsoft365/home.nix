{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.microsoft365;
  browserRunning = pkgs.writeShellScript "microsoft365-browser-running" ''
    port=9222
    if [ -r ${lib.escapeShellArg "${cfg.sessionWarm.profileDirectory}/DevToolsActivePort"} ]; then
      IFS= read -r candidate < ${lib.escapeShellArg "${cfg.sessionWarm.profileDirectory}/DevToolsActivePort"} || true
      case "$candidate" in
        *[!0-9]*|"") ;;
        *) port="$candidate" ;;
      esac
    fi
    exec ${pkgs.curl}/bin/curl --fail --silent --output /dev/null --max-time 2 "http://127.0.0.1:$port/json/version"
  '';
in {
  options.programs.hp-os-fleet.microsoft365 = {
    teamsCliPackage = lib.mkOption {
      type = lib.types.nullOr lib.types.package;
      default = null;
      description = "Caller-supplied Teams CLI with session-warm support. Authentication remains local to each user.";
    };
    sessionWarm = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = cfg.teamsCliPackage != null;
        description = "Maintain an existing Microsoft browser session without opening a browser or signing in.";
      };
      profileDirectory = lib.mkOption {
        type = lib.types.str;
        default = "${config.home.homeDirectory}/.config/google-chrome-live-control";
        description = "Existing Chrome profile used by Microsoft web apps.";
      };
    };
  };
  config = lib.mkMerge [
    (lib.mkIf (cfg.teamsCliPackage != null) {
      home.packages = [ cfg.teamsCliPackage ];
    })
    (lib.mkIf cfg.sessionWarm.enable {
      assertions = [{ assertion = cfg.teamsCliPackage != null; message = "Microsoft session upkeep requires teamsCliPackage."; }];
      systemd.user.services.teams-cli-session-warm = {
        Unit.Description = "Refresh the existing Microsoft 365 browser session";
        Service = {
          Type = "oneshot";
          ExecCondition = toString browserRunning;
          SuccessExitStatus = "0 1";
          ExecStart = "${cfg.teamsCliPackage}/bin/teams-cli session-warm --force --notify --quiet --profile-dir ${lib.escapeShellArg cfg.sessionWarm.profileDirectory}";
          Environment = "PATH=${lib.makeBinPath [ pkgs.libnotify pkgs.xdg-utils ]}:${config.home.profileDirectory}/bin:/usr/bin:/bin";
          TimeoutStartSec = "3min";
          Nice = 10;
          IOSchedulingClass = "idle";
          UMask = "0077";
        };
      };
      systemd.user.timers.teams-cli-session-warm = {
        Unit.Description = "Periodic Microsoft 365 browser session refresh";
        Timer = {
          OnStartupSec = "3min";
          OnUnitInactiveSec = "30min";
          RandomizedDelaySec = "1min";
          Persistent = true;
          Unit = "teams-cli-session-warm.service";
        };
        Install.WantedBy = [ "timers.target" ];
      };
    })
  ];
}
