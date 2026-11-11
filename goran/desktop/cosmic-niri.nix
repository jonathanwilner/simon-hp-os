# Goran's Ubuntu/Niri equivalent of the shared fleet COSMIC app repair.
# HP-OS owns a separate session bus and portal configuration.
{ lib, pkgs, ... }:
let
  cosmicFiles = pkgs.callPackage ../../fleet/cosmic/files-package.nix { };
  settingsDaemon = pkgs.callPackage ../../pkgs/cosmic-settings-daemon/package.nix {
    # COSMIC_SETTINGS_CONFIG_ONLY disables the battery monitor in this session.
    withBatterySounds = false;
  };
  portalGtk = pkgs.callPackage ../../pkgs/xdg-desktop-portal-gtk-network {
    portalGtk = pkgs.xdg-desktop-portal-gtk;
  };
  portalLauncher = pkgs.writeShellScript "goran-gtk-portal-session" ''
    if [ "''${XDG_CURRENT_DESKTOP:-}" = niri ]; then
      exec ${portalGtk}/libexec/xdg-desktop-portal-gtk
    fi
    exec /usr/libexec/xdg-desktop-portal-gtk
  '';
in {
  imports = [ ../../fleet/cosmic/home.nix ];
  home.packages = [ cosmicFiles ];
  home.activation.cosmicFilesDock = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    run ${pkgs.python3}/bin/python3 ${./cosmic-files-default.py} "$HOME/.config/hp-os/config.json"
  '';
  xdg.configFile."systemd/user/xdg-desktop-portal-gtk.service.d/network.conf".text = ''
    [Service]
    ExecStart=
    ExecStart=${portalLauncher}
  '';
  systemd.user.services.cosmic-settings-daemon = {
    Unit = {
      Description = "COSMIC app configuration watcher for Goran Niri";
      PartOf = [ "goran-niri.target" ];
      After = [ "graphical-session.target" ];
      ConditionEnvironment = [ "XDG_CURRENT_DESKTOP=niri" ];
    };
    Service = {
      ExecStartPre = "${pkgs.coreutils}/bin/mkdir -p %h/.config/cosmic %h/.local/state/cosmic";
      ExecStart = "${settingsDaemon}/bin/cosmic-settings-daemon";
      Environment = [ "COSMIC_SETTINGS_CONFIG_ONLY=1" ];
      Type = "dbus";
      BusName = "com.system76.CosmicSettingsDaemon";
      Restart = "on-failure";
      RestartSec = "2s";
    };
    Install.WantedBy = [ "goran-niri.target" ];
  };
}
