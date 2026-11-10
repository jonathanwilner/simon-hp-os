self: { config, lib, pkgs, ... }:
let cfg = config.programs.hp-os; in {
  imports = [ ./touch-options.nix (lib.mkRenamedOptionModule [ "programs" "harmonyshell" ] [ "programs" "hp-os" ]) ];
  options.programs.hp-os = {
    enable = lib.mkEnableOption "HP-OS tools and isolated login session";
    package = lib.mkOption { type = lib.types.package; default = self.packages.${pkgs.stdenv.hostPlatform.system}.default; };
  };
  config = lib.mkIf cfg.enable {
    home.packages = [ cfg.package ];
    xdg.configFile."hp-os/touch.json".text = builtins.toJSON cfg.touchSupport;
    # Explicit start only: HP-OS has a private session bus. Its login wrapper
    # starts the controller inside that session, never in a sibling desktop.
    systemd.user.services.hp-os-touch = lib.mkIf
      (cfg.touchSupport.enable && cfg.touchSupport.keyboard.mode != "off" && cfg.touchSupport.keyboard.backend != "none") {
      Unit.Description = "HP-OS touch controller (explicit session environment required)";
      Service = {
        ExecStart = "${cfg.package}/bin/touch-support run";
        Restart = "on-failure";
        RestartSec = 3;
        UMask = "0077";
      };
    };
    systemd.user.services.hp-os-rotation = lib.mkIf
      (cfg.touchSupport.enable && cfg.touchSupport.rotation.mode != "off") {
      Unit.Description = "HP-OS display rotation (explicit session environment required)";
      Service = {
        ExecStart = "${cfg.package}/bin/touch-support rotation-run";
        Restart = "on-failure";
        RestartSec = 3;
        UMask = "0077";
      };
    };
    home.activation.hposRuntimeRefresh = lib.hm.dag.entryAfter [ "installPackages" "linkGeneration" ] ''
      $DRY_RUN_CMD ${cfg.package}/bin/hp-os refresh
    '';
    # Intentionally no Niri service autostart: selection happens at login.
    fonts.fontconfig.enable = true;
    # Sync only shortcuts after regular Niri files have been activated. Niri
    # watches this file and reloads it without restarting either desktop.
    home.activation.hposNiriBindings = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      $DRY_RUN_CMD ${cfg.package}/bin/hp-os sync-bindings
    '';

  };
}
