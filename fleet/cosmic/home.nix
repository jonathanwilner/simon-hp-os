# COSMIC applications in HP-OS use the desktop's private session bus.
{ config, lib, pkgs, ... }:
let
  cosmicFiles = pkgs.callPackage ./files-package.nix { };
  settingsDaemon = pkgs.callPackage ../../pkgs/cosmic-settings-daemon/package.nix {
    withBatterySounds = false;
  };
in {
  imports = [ ../../goran/desktop/cosmic-hp-os-theme.nix ];
  config = lib.mkIf config.programs.hp-os-fleet.enable {
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
    # D-Bus activation follows the application's bus. Full COSMIC desktop
    # control stays disabled so DMS retains keyboard, audio and power ownership.
    xdg.dataFile."dbus-1/services/com.system76.CosmicSettingsDaemon.service".text = ''
      [D-BUS Service]
      Name=com.system76.CosmicSettingsDaemon
      Exec=${pkgs.coreutils}/bin/env COSMIC_SETTINGS_CONFIG_ONLY=1 ${settingsDaemon}/bin/cosmic-settings-daemon
    '';
  };
}
