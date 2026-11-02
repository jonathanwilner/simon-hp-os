{ config, pkgs, lib, dank-material-shell, dms-plugin-registry, ... }:
let
  system = pkgs.stdenv.hostPlatform.system;
  dms = dank-material-shell.packages.${system}.default.overrideAttrs (old: {
    patches = (old.patches or []) ++ [ ./dms-brightness/manager.patch ];
    postPatch = (old.postPatch or "") + ''
      cp ${./dms-brightness/goran_panel.go} internal/server/brightness/goran_panel.go
      cp ${./dms-brightness/goran_panel_test.go} internal/server/brightness/goran_panel_test.go
    '';
    doCheck = true;
    checkPhase = ''
      runHook preCheck
      go test ./internal/server/brightness
      runHook postCheck
    '';
  });
  themePath = "${config.xdg.configHome}/DankMaterialShell/themes/hp-os.json";
  initialSettings = builtins.toJSON {
    currentThemeName = "custom";
    customThemeFile = themePath;
    fontFamily = "HarmonyOS Sans";
    monoFontFamily = "Fira Mono";
    useAutoLocation = true;
    blurEnabled = true;
    blurredWallpaperLayer = false;
    niriOutputSettings."eDP-1".layout = {
      defaultColumnWidth = { type = "proportion"; value = 0.5; };
      presetColumnWidths = map (value: { type = "proportion"; inherit value; }) [ 0.5 0.66667 1.0 ];
    };
    audioScrollMode = "nothing";
    audioVisualizerEnabled = false;
    soundsEnabled = false;
  };
  settingsSeed = pkgs.writeText "goran-dms-initial-settings.json" initialSettings;
in {
  imports = [
    ./hp-cde-lockscreen/home.nix
    dank-material-shell.homeModules.dank-material-shell
    dms-plugin-registry.homeModules.default
  ];

  programs.hp-cde-lockscreen.enable = true;

  programs.dank-material-shell = {
    enable = true;
    package = dms;
    systemd = {
      enable = true;
      target = "goran-niri.target";
    };
    enableSystemMonitoring = true;
    enableVPN = true;
    enableDynamicTheming = true;
    enableCalendarEvents = true;
    enableClipboardPaste = true;
    plugins.tailscale.enable = true;
    plugins.warpToggle = {
      enable = true;
      # DMS runs without a terminal; use the same explicit ToS acceptance as
      # install-networking.sh for status, toggles, and the live listener.
      src = lib.mkForce (dms-plugin-registry.packages.${system}.warpToggle.overrideAttrs (old: {
        postPatch = (old.postPatch or "") + ''
          substituteInPlace WarpToggleService.qml \
            --replace-fail '[cliBinary, "status"]' '[cliBinary, "--accept-tos", "status"]' \
            --replace-fail '[cliBinary, command]' '[cliBinary, "--accept-tos", command]' \
            --replace-fail '[root.cliBinary, "-l", "status"]' '[root.cliBinary, "--accept-tos", "-l", "status"]'
        '';
      }));
    };
  };

  xdg.configFile."DankMaterialShell/themes/plan9-acme.json".source = ./plan9-acme.json;
  xdg.configFile."DankMaterialShell/plugins/wallhavenCarousel".source =
    pkgs.callPackage ./wallhaven-carousel/package.nix { };
  xdg.configFile."DankMaterialShell/plugins/niriHdr".source = ./dms-hdr;

  xdg.desktopEntries.wallhaven-search = {
    name = "Search Wallhaven Wallpapers";
    comment = "Search, preview, and download wallpapers in DMS";
    exec = "${dms}/bin/dms ipc call wallhavenCarousel discover";
    icon = "preferences-desktop-wallpaper";
    categories = [ "Utility" ];
  };
  xdg.desktopEntries.wallhaven-library = {
    name = "Wallhaven Wallpaper Library";
    exec = "${dms}/bin/dms ipc call wallhavenCarousel open";
    icon = "preferences-desktop-wallpaper";
    categories = [ "Utility" ];
  };
  xdg.desktopEntries.wallpaper-carousel = {
    name = "Wallpaper Carousel";
    exec = "${dms}/bin/dms ipc call wallpaperCarousel open";
    icon = "preferences-desktop-wallpaper";
    categories = [ "Utility" ];
  };

  # Ubuntu's update notifier publishes Yaru-only tray icon names. Quickshell's
  # GTK platform theme reads this setting when resolving StatusNotifier icons.
  dconf.settings."org/gnome/desktop/interface".icon-theme = "Yaru";

  # DMS edits settings at runtime. Seed the Slazenger defaults once, then leave
  # the user's settings writable across Home Manager activations.
  home.activation.goranDmsSettingsInit = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    settings="${config.xdg.configHome}/DankMaterialShell/settings.json"
    if [ ! -e "$settings" ]; then
      $DRY_RUN_CMD ${pkgs.coreutils}/bin/mkdir -p "$(dirname "$settings")"
      $DRY_RUN_CMD ${pkgs.coreutils}/bin/install -m 0644 ${settingsSeed} "$settings"
    fi
  '';

  # Keep runtime settings writable while ensuring the VPN control is visible.
  home.activation.goranDmsVpnWidgets = lib.hm.dag.entryAfter [ "goranDmsSettingsInit" ] ''
    if [ -z "''${DRY_RUN_CMD:-}" ]; then
      settings="${config.xdg.configHome}/DankMaterialShell/settings.json"
      plugins="${config.xdg.configHome}/DankMaterialShell/plugin_settings.json"
      if [ ! -e "$plugins" ]; then
        printf '{}\n' > "$plugins"
      fi
      ${pkgs.jq}/bin/jq 'reduce ["warpToggle", "tailscale", "niriHdr"][] as $id
        (.; .[$id] = ((.[$id] // {}) + {enabled: true}))' \
        "$plugins" > "$plugins.tmp"
      mv "$plugins.tmp" "$plugins"
      ${pkgs.jq}/bin/jq '
        .barConfigs = (.barConfigs // [{
          id: "default", name: "Main Bar", enabled: true, position: 0,
          screenPreferences: ["all"], showOnLastDisplay: true,
          leftWidgets: ["launcherButton", "workspaceSwitcher", "focusedWindow"],
          centerWidgets: ["music", "clock", "weather"],
          rightWidgets: ["systemTray", "clipboard", "cpuUsage", "memUsage",
            "notificationButton", "battery", "controlCenterButton"]
        }])
        | .controlCenterWidgets = (.controlCenterWidgets // [
            {id: "volumeSlider", enabled: true, width: 50},
            {id: "brightnessSlider", enabled: true, width: 50},
            {id: "wifi", enabled: true, width: 50},
            {id: "bluetooth", enabled: true, width: 50},
            {id: "audioOutput", enabled: true, width: 50},
            {id: "audioInput", enabled: true, width: 50},
            {id: "nightMode", enabled: true, width: 50},
            {id: "darkMode", enabled: true, width: 50}
          ])
        | if any(.controlCenterWidgets[]?; .id == "plugin_niriHdr") then .
          else .controlCenterWidgets += [{id: "plugin_niriHdr", enabled: true, width: 50}]
          end
        | .barConfigs |= map(
          reduce ["tailscale", "warpToggle"][] as $id (.;
            if any((.leftWidgets + .centerWidgets + .rightWidgets)[]?;
                (if type == "object" then .id else . end) == $id)
            then .
            else .rightWidgets = ([$id] + (.rightWidgets // []))
            end))
      ' "$settings" > "$settings.tmp"
      mv "$settings.tmp" "$settings"
    fi
  '';

  systemd.user.services.dms.Service.Environment = [
    "DEPTHSCAPE_ENGINE=${pkgs.callPackage ./depthscape/package.nix { }}/bin/depthscape-engine"
    # Use the QML module built against the same Nix Qt as Quickshell.
    "QML2_IMPORT_PATH=${pkgs.qt6.qt5compat}/lib/qt-6/qml"
    "QML_IMPORT_PATH=${pkgs.qt6.qt5compat}/lib/qt-6/qml"
    "DMS_GORAN_BRIGHTNESS=%h/.nix-profile/bin/goran-brightness"
    # Ubuntu registers this passive indicator even without a Pro subscription.
    # Goran's N1X kernel is not covered by Livepatch.
    "DMS_HIDE_TRAYIDS=livepatch"
    "PATH=%h/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin"
    # Flatpak exports the BlueBubbles StatusNotifier icon here. The Ubuntu
    # systemd user environment does not include this path by default.
    "XDG_DATA_DIRS=%h/.local/share/flatpak/exports/share:%h/.nix-profile/share:/usr/local/share:/usr/share:/var/lib/snapd/desktop"
    "QT_LOGGING_RULES=quickshell.*.debug=false;quickshell.*.info=false"
  ];
}
