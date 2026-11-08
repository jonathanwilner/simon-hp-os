{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.release;
  tools = pkgs.stdenvNoCC.mkDerivation {
    pname = "hp-os-fleet-release";
    version = "1";
    src = ./.;
    nativeBuildInputs = [ pkgs.makeWrapper ];
    installPhase = ''
      mkdir -p $out/lib $out/bin
      cp *.py $out/lib/
      for entry in status publish consumers canary; do
        makeWrapper ${pkgs.python3}/bin/python3 $out/bin/fleet-$entry \
          --add-flags $out/lib/$entry.py \
          --prefix PATH : ${lib.makeBinPath [ pkgs.git pkgs.gh pkgs.nix pkgs.coreutils pkgs.iproute2 pkgs.tmux ]}
      done
    '';
  };
  consumerConfig = pkgs.writeText "fleet-consumers.json" (builtins.toJSON { consumers = cfg.consumers; });
  dashboard = pkgs.callPackage ../../pkgs/nom-dashboard.nix {};
in {
  options.programs.hp-os-fleet.release = {
    revision = lib.mkOption { type = lib.types.str; default = "unknown"; description = "Exact shared fleet revision included in this generation."; };
    checkout = lib.mkOption { type = lib.types.str; default = "${config.home.homeDirectory}/src/simon-hp-os"; description = "Shared fleet source checkout for release status."; };
    autoSubmit = lib.mkOption { type = lib.types.bool; default = true; description = "Install a preserving post-commit hook in an existing shared checkout; main commits validate before push."; };
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
target = state / 'installed.json'
temporary = state / 'installed.json.tmp'
temporary.write_text(json.dumps({'fleet_revision': sys.argv[2], 'generation': str(pathlib.Path(sys.argv[1]).resolve())}) + '\n')
temporary.replace(target)
PY
      fi
    '';
    home.activation.installFleetSubmitHook = lib.hm.dag.entryAfter [ "linkGeneration" ] (lib.optionalString cfg.autoSubmit ''
      if [ -z "''${DRY_RUN_CMD:-}" ] && [ -e ${lib.escapeShellArg (cfg.checkout + "/.git")} ]; then
        ${tools}/bin/fleet-publish install-hook --checkout ${lib.escapeShellArg cfg.checkout}
      fi
    '');
    systemd.user.services.fleet-consumers = lib.mkIf (cfg.consumers != []) {
      Unit.Description = "Validate and publish tested desktop fleet consumer pins";
      Service = {
        Type = "oneshot";
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
