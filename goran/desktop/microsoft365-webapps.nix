{ config, lib, pkgs, ... }:
let
  catalogue = builtins.fromJSON (builtins.readFile ./microsoft365-webapps/apps.json);
  # Host wrappers retain their established profile and hardware configuration.
  # New fleet devices get native Chrome without Goran's NVIDIA-specific flags.
  browser = if (pkgs.google-chrome.channel or null) == "stable" then pkgs.google-chrome else pkgs.callPackage ../../fleet/chrome-channels/package.nix {
    channel = "stable";
    google-chrome = pkgs.google-chrome;
  };
  launcher = pkgs.writeShellScript "hp-os-microsoft365" ''
    if [ -x "$HOME/.local/bin/chrome-live-control" ]; then
      exec "$HOME/.local/bin/chrome-live-control" "$@"
    fi
    exec ${browser}/bin/google-chrome-stable \
      --ozone-platform=wayland \
      --user-data-dir="$HOME/.config/google-chrome-live-control" "$@"
  '';
  desktopDir = if config.xdg.userDirs.desktop != null then config.xdg.userDirs.desktop else "${config.home.homeDirectory}/Desktop";
  # Chromium derives a Wayland app ID from the launch URL and profile basename.
  # Match the existing shared Default profile, including path-bearing web apps.
  windowClass = app:
    let parts = builtins.match "https://([^/]+)(/.*)" app.url;
    in "chrome-${lib.replaceStrings [ "/" ] [ "_" ] "${builtins.elemAt parts 0}_${builtins.elemAt parts 1}"}-Default";
  applications = map (app: {
    inherit app;
    desktop = pkgs.makeDesktopItem {
      name = "microsoft365-${app.id}";
      desktopName = app.name;
      genericName = "Microsoft 365 Web App";
      comment = "${app.name} in your Microsoft 365 Chrome session";
      # Reuse the managed work profile, its passkey keyring and site identity policy.
      exec = ''"${launcher}" --app=${app.url}'';
      icon = "${./microsoft365-webapps/icons}/${app.icon}";
      terminal = false;
      categories = [ "Office" ];
      keywords = [ "Microsoft" "Microsoft 365" "Office 365" ] ++ app.keywords;
      extraConfig = {
        StartupWMClass = windowClass app;
        "X-HP-OS-AppGroup" = "Microsoft 365";
        "X-HP-OS-WebApp-URL" = app.url;
      };
    };
  }) catalogue;
in {
  # XDG applications are indexed by both fuzzel and the HP-OS Start/app launcher.
  xdg.dataFile = builtins.listToAttrs (map ({ app, desktop }: {
    name = "applications/microsoft365-${app.id}.desktop";
    value.source = "${desktop}/share/applications/microsoft365-${app.id}.desktop";
  }) applications);

  home.activation.microsoft365Desktop = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    $DRY_RUN_CMD ${pkgs.python3}/bin/python3 ${./microsoft365-webapps/seed-desktop.py}
  '';

  # A new account may activate Home Manager before HP-OS creates its layout.
  # Seed that first layout when it appears; keep later user edits unchanged.
  systemd.user.paths.microsoft365-desktop = {
    Unit.Description = "Seed Microsoft 365 icons after the first HP-OS login";
    Path.PathChanged = "%h/.local/state/hp-os/user/desktop-items.json";
    Install.WantedBy = [ "default.target" ];
  };
  systemd.user.services.microsoft365-desktop = {
    Unit = {
      Description = "Seed the shared Microsoft 365 desktop catalogue";
      ConditionPathExists = "!%h/.local/state/hp-os/user/microsoft365-desktop-v1.json";
    };
    Service = {
      Type = "oneshot";
      ExecStart = "${pkgs.python3}/bin/python3 ${./microsoft365-webapps/seed-desktop.py}";
    };
  };

  # Actual executable .desktop files give the HP-OS desktop the same app icons.
  home.file = builtins.listToAttrs (map ({ app, desktop }: {
    name = "${desktopDir}/${app.name}.desktop";
    value = {
      source = "${desktop}/share/applications/microsoft365-${app.id}.desktop";
      executable = true;
    };
  }) applications);
}
