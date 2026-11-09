{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.release;
  tools = pkgs.callPackage ./package.nix {};
  consumerConfig = pkgs.writeText "fleet-consumers.json" (builtins.toJSON { consumers = cfg.consumers; });
  dashboard = pkgs.callPackage ../../pkgs/nom-dashboard.nix {};
in {
  options.programs.hp-os-fleet.release = {
    revision = lib.mkOption { type = lib.types.str; default = "unknown"; description = "Exact shared fleet revision included in this generation."; };
    checkout = lib.mkOption { type = lib.types.nullOr lib.types.str; default = null; description = "Optional writer checkout; consumers report from their installed record and lock."; };
    autoSubmit = lib.mkOption { type = lib.types.bool; default = true; description = "Install a preserving post-commit hook in an existing shared checkout; main commits validate before push."; };
    consumerLock = lib.mkOption { type = lib.types.nullOr lib.types.str; default = null; description = "Consumer lock file used for release drift reporting."; };
    controller = lib.mkOption { type = lib.types.nullOr lib.types.attrs; default = null; description = "Trusted writer canary and consumer registration; never include secrets."; };
    consumers = lib.mkOption { type = lib.types.listOf lib.types.attrs; default = []; description = "Explicit consumer checkouts, branches, flakes, and validation commands to reconcile."; };
  };
  config = lib.mkIf config.programs.hp-os-fleet.enable {
    home.packages = [ tools ];
    xdg.configFile."hp-os-fleet/revision".text = cfg.revision + "\n";
    home.activation.recordFleetRelease = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      if [ -z "''${DRY_RUN_CMD:-}" ]; then
        ${pkgs.python3}/bin/python3 - "$newGenPath" ${lib.escapeShellArg cfg.revision} <<'PY'
import json, os, pathlib, sys
state = pathlib.Path(os.environ.get('XDG_STATE_HOME', pathlib.Path.home() / '.local/state')) / 'hp-os-fleet'
state.mkdir(parents=True, exist_ok=True)
active = state / 'active-generation'
if active.is_symlink():
    active.unlink()
active.symlink_to(pathlib.Path(sys.argv[1]).resolve())
target = state / 'installed.json'
temporary = state / 'installed.json.tmp'
temporary.write_text(json.dumps({'fleet_revision': sys.argv[2], 'generation': str(pathlib.Path(sys.argv[1]).resolve())}) + '\n')
temporary.replace(target)
PY
      fi
    '';
    home.activation.installFleetSubmitHook = lib.hm.dag.entryAfter [ "linkGeneration" ] (lib.optionalString (cfg.autoSubmit && cfg.checkout != null) ''
      if [ -z "''${DRY_RUN_CMD:-}" ] && [ -e ${lib.escapeShellArg (cfg.checkout + "/.git")} ]; then
        ${tools}/bin/fleet-publish install-hook --checkout ${lib.escapeShellArg cfg.checkout}
      fi
    '');
    systemd.user.services.fleet-release-report = {
      Unit.Description = "Report desktop fleet release and activation drift";
      Service = {
        Type = "oneshot";
        Environment = [ "NOM_TMUX_KEEP_SESSION=0" ];
        ExecStart = "${dashboard}/bin/nom-tmux fleet-release-report -- ${tools}/bin/fleet-report" + lib.optionalString (cfg.checkout != null) " --checkout ${lib.escapeShellArg cfg.checkout}" + lib.optionalString (cfg.consumerLock != null) " --consumer-lock ${lib.escapeShellArg cfg.consumerLock}" + " --active-generation %h/.local/state/hp-os-fleet/active-generation";
      };
    };
    systemd.user.timers.fleet-release-report = {
      Unit.Description = "Refresh desktop fleet release status";
      Timer = { OnBootSec = "5m"; OnUnitActiveSec = "30m"; Persistent = true; };
      Install.WantedBy = [ "timers.target" ];
    };
    systemd.user.services.fleet-release-controller = lib.mkIf (cfg.controller != null) {
      Unit.Description = "Promote tested desktop releases through canary acceptance";
      Service = {
        Type = "oneshot";
        Environment = [ "NOM_TMUX_KEEP_SESSION=0" ];
        ExecStart = "${dashboard}/bin/nom-tmux fleet-release-controller -- ${tools}/bin/fleet-controller --config ${pkgs.writeText "fleet-controller.json" (builtins.toJSON cfg.controller)}";
      };
    };
    systemd.user.timers.fleet-release-controller = lib.mkIf (cfg.controller != null) {
      Unit.Description = "Check validated desktop candidates for canary deployment";
      Timer = { OnBootSec = "5m"; OnUnitActiveSec = "10m"; Persistent = true; };
      Install.WantedBy = [ "timers.target" ];
    };
    systemd.user.services.fleet-consumers = lib.mkIf (cfg.consumers != []) {
      Unit.Description = "Validate and publish tested desktop fleet consumer pins";
      Service = {
        Type = "oneshot";
        Environment = [ "NOM_TMUX_KEEP_SESSION=0" ];
        ExecStart = "${dashboard}/bin/nom-tmux fleet-consumers -- ${tools}/bin/fleet-consumers --config ${consumerConfig}";
      };
    };
    systemd.user.timers.fleet-consumers = lib.mkIf (cfg.consumers != []) {
      Unit.Description = "Reconcile tested desktop fleet releases";
      Timer = { OnBootSec = "5m"; OnUnitActiveSec = "15m"; Persistent = true; };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
