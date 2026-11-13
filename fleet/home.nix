# Public desktop policy. Keep identity, hardware and secrets in host modules.
{ config, lib, pkgs, osConfig ? {}, ... }:
let
  cfg = config.programs.hp-os-fleet;
  runtimePackage = if lib.attrByPath [ "programs" "hp-os" "enable" ] false config then config.programs.hp-os.package
    else if lib.attrByPath [ "programs" "hp-os" "enable" ] false osConfig then osConfig.programs.hp-os.package
    else null;
  refreshRuntime = pkgs.writeShellScript "hp-os-refresh-installed" ''
    export PATH="${config.home.profileDirectory}/bin:/run/current-system/sw/bin:$PATH"
    ${if runtimePackage != null then "exec ${runtimePackage}/bin/hp-os refresh" else ''
      if command -v hp-os >/dev/null; then exec hp-os refresh; fi
    ''}
  '';
in {
  imports = [ ./cosmic/home.nix ./hp-os-controls/home.nix ./artcraft.nix ./appearance/home.nix ./session/home.nix ./niri/home.nix ./microsoft365/home.nix ../goran/desktop/microsoft365-webapps.nix ./ubuntu-branding/home.nix ./steam/home.nix ./mosh/home.nix ./release/home.nix ./chrome-channels/home.nix ../goran/desktop/upscayl/home.nix ./launcher-apps.nix ./media-keys.nix ./owly/home.nix ./relay/home.nix ./printing/home.nix ];
  options.programs.hp-os-fleet = {
    enable = lib.mkEnableOption "shared HP-OS fleet desktop defaults" // { default = true; };
    upscayl.enable = lib.mkEnableOption "native Upscayl" // { default = true; };
    wallpapers.enable = lib.mkEnableOption "original HP-OS wallpaper collection" // { default = true; };
  };
  config = lib.mkIf cfg.enable {
    # Keep the HP-OS theme's fallback chain complete in every login session.
    home.packages = [ pkgs.adwaita-icon-theme pkgs.hicolor-icon-theme ];
    # Reconcile installed and running HP-OS generations after package links
    # change. The controller touches only explicitly owned HP-OS shell PIDs.
    home.activation.refreshHpOsRuntime = lib.hm.dag.entryAfter [ "reloadSystemd" ] ''
      # System activation also updates homes without a running user manager.
      # The installed timer starts with timers.target at the next user login.
      if ${pkgs.systemd}/bin/systemctl --user show-environment >/dev/null 2>&1; then
        # Launch from the persistent user unit, outside the activation cgroup.
        $DRY_RUN_CMD ${pkgs.systemd}/bin/systemctl --user start --no-block hp-os-runtime-refresh.timer
        $DRY_RUN_CMD ${pkgs.systemd}/bin/systemctl --user start --no-block hp-os-runtime-refresh.service
      fi
    '';
    # A locked shell remains running. Retry the generation comparison after
    # unlock; current generations and other desktop sessions are no-ops.
    systemd.user.services.hp-os-runtime-refresh = {
      Unit = {
        Description = "Refresh an outdated unlocked HP-OS shell";
        # Preserve a refresh already between stopping and launching its shell.
        # sd-switch applies this to both active and activating old units.
        X-SwitchMethod = "keep-old";
      };
      Service = {
        Type = "oneshot";
        ExecStart = "${refreshRuntime}";
        # A replacement shell outlives this generation-comparison process.
        KillMode = "process";
      };
    };
    systemd.user.timers.hp-os-runtime-refresh = {
      Unit.Description = "Retry deferred HP-OS runtime upgrades";
      Timer = { OnStartupSec = "1min"; OnUnitActiveSec = "1min"; };
      Install.WantedBy = [ "timers.target" ];
    };
    home.file."Pictures/Wallpapers/HP-OS" = lib.mkIf cfg.wallpapers.enable {
      source = ../goran/desktop/wallpapers/images;
      recursive = true;
    };
  };
}
