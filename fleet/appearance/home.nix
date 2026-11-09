# Portable appearance assets and first-login defaults. Hardware stays in hosts.
{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.appearance;
  theme = pkgs.callPackage ../../goran/desktop/hp-os-theme/package.nix { };
  seed = pkgs.writeText "hp-os-fleet-appearance-defaults.json" (builtins.toJSON {
    "ghostty/config" = ''
      window-decoration = client
      font-family = Fira Mono
      font-size = 13
      adjust-cell-height = 2
      theme = light:hp-os-light,dark:hp-os-dark
      minimum-contrast = 4.5
      keybind = ctrl+shift+c=copy_to_clipboard
      keybind = ctrl+shift+v=paste_from_clipboard
      keybind = ctrl+insert=copy_to_clipboard
      keybind = shift+insert=paste_from_clipboard
    '';
    "alacritty/alacritty.toml" = ''
      [general]
      import = ["${config.xdg.configHome}/alacritty/themes/hp-os-dark.toml"]
      live_config_reload = true
      [font]
      normal = { family = "Fira Mono", style = "Regular" }
      size = 13.0
      [keyboard]
      bindings = [
        { key = "C", mods = "Control|Shift", action = "Copy" },
        { key = "V", mods = "Control|Shift", action = "Paste" },
        { key = "Insert", mods = "Control", action = "Copy" },
        { key = "Insert", mods = "Shift", action = "Paste" },
      ]
    '';
  });
  defaults = pkgs.writeText "hp-os-fleet-dms-defaults.json" (builtins.toJSON {
    currentThemeName = "custom";
    customThemeFile = "${config.xdg.configHome}/DankMaterialShell/themes/hp-os.json";
    fontFamily = "HarmonyOS Sans";
    monoFontFamily = "Fira Mono";
    batteryNotifyLow = true;
    batteryNotifyCritical = true;
    batteryLowThreshold = 20;
    batteryCriticalThreshold = 10;
  });
in {
  options.programs.hp-os-fleet.appearance = {
    enable = lib.mkEnableOption "portable HP-OS appearance and first-login defaults";
    wallhaven.enable = lib.mkEnableOption "Wallhaven search and library plugin" // { default = true; };
    dmsPackage = lib.mkOption {
      type = lib.types.nullOr lib.types.package;
      default = null;
      description = "DMS command for optional wallpaper launchers.";
    };
  };
  config = lib.mkIf (config.programs.hp-os-fleet.enable && cfg.enable) {
    home.packages = [ theme pkgs.fira pkgs.noto-fonts pkgs.noto-fonts-cjk-sans pkgs.noto-fonts-color-emoji ];
    fonts.fontconfig.enable = true;
    fonts.fontconfig.defaultFonts = {
      sansSerif = lib.mkDefault [ "HarmonyOS Sans" "HarmonyOS Sans SC" "Noto Sans" ];
      monospace = lib.mkDefault [ "Fira Mono" "Noto Sans Mono" ];
      emoji = lib.mkDefault [ "Noto Color Emoji" ];
    };
    xdg.configFile = {
      "DankMaterialShell/themes/hp-os.json".source = "${theme}/share/hp-os-dms-theme/themes/hp-os.json";
      "hp-os-theme/tokens.json".source = "${theme}/share/hp-os-dms-theme/tokens/hp-os.json";
      "ghostty/themes/hp-os-light".source = ../../goran/desktop/terminal-themes/hp-os-light;
      "ghostty/themes/hp-os-dark".source = ../../goran/desktop/terminal-themes/hp-os-dark;
      "alacritty/themes/hp-os-light.toml".source = ../../goran/desktop/terminal-themes/hp-os-light.toml;
      "alacritty/themes/hp-os-dark.toml".source = ../../goran/desktop/terminal-themes/hp-os-dark.toml;
    } // lib.optionalAttrs cfg.wallhaven.enable {
      "DankMaterialShell/plugins/wallhavenCarousel".source = pkgs.callPackage ../../goran/desktop/wallhaven-carousel/package.nix { };
    };
    xdg.desktopEntries = lib.mkIf (cfg.wallhaven.enable && cfg.dmsPackage != null) {
      wallhaven-search = {
        name = "Search Wallhaven Wallpapers";
        exec = "${cfg.dmsPackage}/bin/dms ipc call wallhavenCarousel discover";
        icon = "preferences-desktop-wallpaper";
        categories = [ "Utility" ];
      };
      wallhaven-library = {
        name = "Wallhaven Wallpaper Library";
        exec = "${cfg.dmsPackage}/bin/dms ipc call wallhavenCarousel open";
        icon = "preferences-desktop-wallpaper";
        categories = [ "Utility" ];
      };
    };
    home.activation.hpOsFleetAppearanceDefaults = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      $DRY_RUN_CMD ${pkgs.python3}/bin/python3 ${./seed.py} \
        ${lib.escapeShellArg config.xdg.configHome} ${seed} ${defaults}
    '';
  };
}
