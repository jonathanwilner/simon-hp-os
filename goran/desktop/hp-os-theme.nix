{ config, lib, pkgs, ... }:
let
  theme = pkgs.callPackage ./hp-os-theme/package.nix { };
  sync = import ./theme-sync.nix { inherit config pkgs; };
  themePath = "${config.xdg.configHome}/DankMaterialShell/themes/hp-os.json";
in {
  home.packages = [ theme pkgs.fira ];
  systemd.user.services.dms.Service.Environment = [
    "GIO_EXTRA_MODULES=${pkgs.dconf.lib}/lib/gio/modules"
    "GSETTINGS_BACKEND=dconf"
  ];
  fonts.fontconfig.defaultFonts = {
    sansSerif = [ "HarmonyOS Sans" "HarmonyOS Sans SC" "Noto Sans" ];
    monospace = [ "Fira Mono" "Noto Sans Mono" ];
  };
  xdg.configFile."fontconfig/conf.d/99-hp-os.conf".source =
    "${theme}/etc/fonts/conf.d/60-hp-os-sans.conf";
  xdg.configFile."DankMaterialShell/themes/hp-os.json".source =
    "${theme}/share/hp-os-dms-theme/themes/hp-os.json";
  xdg.configFile."hp-os-theme/tokens.json".source =
    "${theme}/share/hp-os-dms-theme/tokens/hp-os.json";

  gtk = {
    enable = true;
    theme = { name = "Adwaita"; package = pkgs.gnome-themes-extra; };
    font = { name = "HarmonyOS Sans"; size = 11; };
    gtk3.extraCss = ''@import url("dank-colors.css");'';
    gtk4.extraCss = ''@import url("dank-colors.css");'';
  };
  qt = {
    enable = true;
    platformTheme.name = "kde";
    style.name = "breeze";
  };
  # The sync service updates these writable files when DMS changes mode.
  xdg.configFile."gtk-3.0/settings.ini".force = true;
  xdg.configFile."gtk-4.0/settings.ini".force = true;
  xdg.configFile."gtk-3.0/gtk.css".force = true;
  xdg.configFile."gtk-4.0/gtk.css".force = true;
  dconf.settings."org/gnome/desktop/interface" = {
    font-name = "HarmonyOS Sans 11";
    document-font-name = "HarmonyOS Sans 11";
    monospace-font-name = "Fira Mono 11";
  };

  xdg.configFile."ghostty/config".text = ''
    # Keep titlebars visible even in windows created before Niri's CSD fix.
    window-decoration = client
    font-family = "Fira Mono"
    font-style = "Regular"
    font-size = 13
    # Add vertical breathing room while preserving the terminal column grid.
    adjust-cell-height = 2
    theme = light:hp-os-light,dark:hp-os-dark
    minimum-contrast = 4.5
    faint-opacity = 0.75
    keybind = ctrl+shift+c=copy_to_clipboard
    keybind = ctrl+shift+v=paste_from_clipboard
    keybind = ctrl+v=paste_from_clipboard
    keybind = ctrl+insert=copy_to_clipboard
    keybind = shift+insert=paste_from_clipboard
  '';
  xdg.configFile."ghostty/themes/hp-os-light".source = ./terminal-themes/hp-os-light;
  xdg.configFile."ghostty/themes/hp-os-dark".source = ./terminal-themes/hp-os-dark;
  xdg.configFile."alacritty/alacritty.toml".text = ''
    [general]
    import = [ "${config.xdg.configHome}/alacritty/hp-os.toml" ]
    live_config_reload = true
    [font]
    normal = { family = "Fira Mono", style = "Regular" }
    bold = { family = "Fira Mono", style = "Bold" }
    size = 13.0
    offset = { x = 0, y = 2 }
    [keyboard]
    bindings = [
      { key = "C", mods = "Control|Shift", action = "Copy" },
      { key = "V", mods = "Control|Shift", action = "Paste" },
      { key = "V", mods = "Control", action = "Paste" },
      { key = "Insert", mods = "Control", action = "Copy" },
      { key = "Insert", mods = "Shift", action = "Paste" },
    ]
  '';
  xdg.configFile."alacritty/themes/hp-os-light.toml".source = ./terminal-themes/hp-os-light.toml;
  xdg.configFile."alacritty/themes/hp-os-dark.toml".source = ./terminal-themes/hp-os-dark.toml;

  home.activation.goranHposTheme = lib.hm.dag.entryAfter [
    "linkGeneration" "goranDmsSettingsInit" "goranDmsVpnWidgets"
  ] ''
    export DMS_SHELL_DIR=${config.programs.dank-material-shell.package}/share/quickshell/dms
    $DRY_RUN_CMD ${theme}/bin/hp-os-theme-apply --theme-file ${lib.escapeShellArg themePath}
  '';
  home.activation.goranHposRefresh = lib.hm.dag.entryAfter [
    "reloadSystemd" "goranHposTheme"
  ] ''
    $DRY_RUN_CMD ${pkgs.fontconfig}/bin/fc-cache -f "$HOME/.nix-profile/share/fonts"
    if [ -z "''${DRY_RUN_CMD:-}" ] && ${pkgs.systemd}/bin/systemctl --user is-active --quiet dms.service; then
      ${pkgs.systemd}/bin/systemctl --user restart dms.service
      ${pkgs.systemd}/bin/systemctl --user restart dms-theme-sync.service
    fi
  '';
  systemd.user.services.dms-theme-sync = {
    Unit = {
      Description = "Sync HP-OS desktop and terminal themes with DMS";
      # DMS starts after the session target. Explicitly put theme sync after
      # that target too, so its WantedBy dependency cannot order it before
      # the target and create a target -> DMS -> theme sync -> target cycle.
      After = [ "goran-niri.target" "dms.service" ];
      PartOf = [ "goran-niri.target" ];
    };
    Service = { Type = "oneshot"; ExecStart = "${sync}"; };
    Install.WantedBy = [ "goran-niri.target" ];
  };
  systemd.user.paths.dms-theme-sync = {
    Unit = {
      Description = "Watch DMS palette, typography, and light/dark changes";
      PartOf = [ "goran-niri.target" ];
    };
    Path.PathChanged = [
      "%h/.cache/DankMaterialShell/dms-colors.json"
      "%h/.config/DankMaterialShell/settings.json"
      "%h/.local/state/DankMaterialShell/session.json"
    ];
    Install.WantedBy = [ "goran-niri.target" ];
  };
}
