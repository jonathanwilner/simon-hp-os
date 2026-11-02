# Goran's Ubuntu/Niri equivalent of the shared fleet COSMIC app repair.
# HP-OS owns a separate session bus and portal configuration.
{ lib, pkgs, ... }:
let
  cosmicFiles = pkgs.symlinkJoin {
    name = "cosmic-files-gvfs";
    paths = [ pkgs.cosmic-files ];
    nativeBuildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/cosmic-files" \
        --prefix GIO_EXTRA_MODULES : "${pkgs.gvfs}/lib/gio/modules"
    '';
  };
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
  imports = [ ./cosmic-harmony-theme.nix ];
  home.packages = [ cosmicFiles ];
  xdg.mimeApps.defaultApplications."inode/directory" = [ "com.system76.CosmicFiles.desktop" ];
  # A preserved HP-OS session can still have an older generation in XDG_DATA_DIRS.
  # Resolve Files through the current GVfs-enabled wrapper in every launcher.
  xdg.desktopEntries."com.system76.CosmicFiles" = {
    name = "Files";
    comment = "Browse files and network drives";
    exec = "${cosmicFiles}/bin/cosmic-files %U";
    icon = "com.system76.CosmicFiles";
    terminal = false;
    categories = [ "System" "FileTools" "FileManager" ];
    mimeType = [ "inode/directory" ];
    settings.StartupNotify = "true";
  };
  home.activation.cosmicFilesDock = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    run ${pkgs.python3}/bin/python3 ${./cosmic-files-default.py} "$HOME/.config/hp-os/config.json"
  '';
  # HP-OS owns a private session bus, outside goran-niri.target. Let COSMIC
  # applications activate their config watcher on whichever bus they use.
  xdg.dataFile."dbus-1/services/com.system76.CosmicSettingsDaemon.service".text = ''
    [D-BUS Service]
    Name=com.system76.CosmicSettingsDaemon
    Exec=${pkgs.coreutils}/bin/env COSMIC_SETTINGS_CONFIG_ONLY=1 ${settingsDaemon}/bin/cosmic-settings-daemon
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
