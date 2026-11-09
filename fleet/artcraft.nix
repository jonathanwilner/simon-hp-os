# The upstream native suite publishes both ARM64 and x86-64 releases.
# GPU-specific presentation overrides belong to individual host modules.
{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.artcraft;
  native = import ../flakes/artcraft-suite/packages.nix { inherit pkgs; };
  catalog = pkgs.writeShellApplication {
    name = "artcraft-catalog";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      exec python3 ${../flakes/artcraft-suite/update.py} --versions ${../flakes/artcraft-suite/versions.json} --report "$@"
    '';
  };
in {
  options.programs.hp-os-fleet.artcraft = {
    enable = lib.mkEnableOption "native Artcraft creative applications";
    checkForUpdates = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Check upstream daily and save a report; installation stays declarative.";
    };
    package = lib.mkOption {
      type = lib.types.package;
      default = native.suite;
      description = "Native architecture suite without GPU vendor overrides.";
    };
  };
  config = lib.mkIf (config.programs.hp-os-fleet.enable && cfg.enable) {
    home.packages = [ cfg.package native.update catalog ];
    systemd.user.services.artcraft-catalog = lib.mkIf cfg.checkForUpdates {
      Unit.Description = "Check Artcraft releases and discover optional applications";
      Service = {
        Type = "oneshot";
        ExecStart = "${pkgs.writeShellScript "artcraft-catalog-report" ''
          set -eu
          directory="''${XDG_STATE_HOME:-$HOME/.local/state}/artcraft"
          mkdir -p "$directory"
          temporary=$(mktemp "$directory/report.XXXXXX")
          trap 'rm -f "$temporary"' EXIT
          ${catalog}/bin/artcraft-catalog > "$temporary"
          if ! cmp -s "$temporary" "$directory/catalog.txt"; then
            mv "$temporary" "$directory/catalog.txt"
            ${pkgs.python3}/bin/python3 ${./session/notify.py} ${pkgs.libnotify}/bin/notify-send "Artcraft catalog updated" "Run artcraft-catalog to review releases and choose new apps." || true
          fi
        ''}";
      };
    };
    systemd.user.timers.artcraft-catalog = lib.mkIf cfg.checkForUpdates {
      Unit.Description = "Daily Artcraft release discovery";
      Timer = { OnCalendar = "daily"; Persistent = true; RandomizedDelaySec = "1h"; };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
