{ config, lib, pkgs, owlySource, osConfig ? null, ... }:
let
  cfg = config.programs.hp-os-fleet;
  owly = pkgs.callPackage "${owlySource}/nix/package.nix" {};
  toml = pkgs.formats.toml {};
  systemInstaller = pkgs.callPackage ./ubuntu-system.nix {
    inherit owly owlySource;
    desktopUser = config.home.username;
    radioConfig = if cfg.owly.settings == {} then null else toml.generate "owly-radio.toml" cfg.owly.settings;
  };
  omdrop = pkgs.callPackage ./omdrop-package.nix { inherit owlySource; };
  controller = pkgs.callPackage ./controller-package.nix {
    inherit omdrop owly;
    allowSteering = cfg.owly.automaticWifiSwitching;
    preferredChannels = cfg.owly.preferredChannels;
  };
  identity = pkgs.callPackage ./identity/package.nix { inherit omdrop; };
  gui = pkgs.callPackage ./gui-package.nix { inherit omdrop owly controller; };

in {
  options.programs.hp-os-fleet.owly = {
    enable = lib.mkEnableOption "Owly AirDrop tools" // { default = true; };
    autostartReceiving = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Start persistent AirDrop receiving with the user manager and retry failures. Stop receiving pauses automatic startup until the service restarts or receiving is enabled manually.";
    };
    automaticWifiSwitching = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Temporarily roam to a compatible access point on the same saved Wi-Fi network when receiving with AirDrop. Restore the original connection on stop, expiry, or failure.";
    };
    preferredChannels = lib.mkOption {
      type = lib.types.listOf (lib.types.enum [ 6 44 149 ]);
      default = [];
      description = "Preferred shared AirDrop Wi-Fi channels, in priority order. With automatic Wi-Fi switching enabled, prefer an available access point on these channels on the same saved network. Fall back to the current compatible access point or strongest available compatible access point.";
    };
    identityExpiryNotifications = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Check imported Apple identity validity daily and notify when renewal is needed. Credentials remain in the user home, outside the Nix store. This does not renew credentials automatically.";
    };
    settings = lib.mkOption {
      inherit (toml) type;
      default = {};
      description = "Host-specific Ubuntu radio settings. NixOS uses services.owly.settings.";
    };
  };
  config = lib.mkIf (cfg.enable && cfg.owly.enable) {
    # The root helper refuses NixOS; NixOS uses the exported system module.
    home.packages = [ owly omdrop controller identity gui systemInstaller ];
    systemd.user.services.hp-os-omdrop-auto = lib.mkIf cfg.owly.autostartReceiving {
      Unit = {
        Description = "Keep Omdrop receiving while the user manager runs";
        PartOf = [ "default.target" ];
        StartLimitIntervalSec = 0;
      };
      Service = {
        ExecStart = "${controller}/bin/hp-os-omdrop-controller automatic";
        ExecStop = "${controller}/bin/hp-os-omdrop-controller off";
        Restart = "on-failure";
        RestartSec = "60s";
        TimeoutStopSec = "90s";
      };
      Install.WantedBy = [ "default.target" ];
    };
    systemd.user.services.hp-os-omdrop-identity-check = lib.mkIf cfg.owly.identityExpiryNotifications {
      Unit.Description = "Check OM Drop Apple identity expiry";
      Service = {
        Type = "oneshot";
        ExecStart = "${identity}/bin/hp-os-omdrop-identity check --notify --json";
      };
    };
    systemd.user.timers.hp-os-omdrop-identity-check = lib.mkIf cfg.owly.identityExpiryNotifications {
      Unit.Description = "Daily OM Drop Apple identity expiry check";
      Timer = { OnCalendar = "daily"; Persistent = true; RandomizedDelaySec = "15m"; };
      Install.WantedBy = [ "timers.target" ];
    };
    xdg.configFile."hp-os/omdrop".source = "${gui}/share/omdrop";
    xdg.configFile."DankMaterialShell/plugins/omdrop".source = "${gui}/share/omdrop";
    # Merge the native DMS control into mutable user settings without replacing
    # their existing layout. HP-OS uses its own native control-center tile.
    home.activation.omdropDmsControl = lib.hm.dag.entryAfter [ "writeBoundary" "linkGeneration" "goranDmsVpnWidgets" ] ''
      if [ -z "''${DRY_RUN_CMD:-}" ]; then
        directory="${config.xdg.configHome}/DankMaterialShell"
        ${pkgs.coreutils}/bin/mkdir -p "$directory"
        plugins="$directory/plugin_settings.json"
        settings="$directory/settings.json"
        if [ ! -e "$plugins" ]; then printf '{}\n' > "$plugins"; fi
        ${pkgs.jq}/bin/jq '.omdrop = ((.omdrop // {}) + {enabled: true})' "$plugins" > "$plugins.omdrop-tmp"
        ${pkgs.coreutils}/bin/mv "$plugins.omdrop-tmp" "$plugins"
        if [ ! -e "$settings" ]; then printf '{}\n' > "$settings"; fi
        if [ -e "$settings" ]; then
          ${pkgs.jq}/bin/jq '
            .controlCenterWidgets = (.controlCenterWidgets // [
              {id: "volumeSlider", enabled: true, width: 50},
              {id: "brightnessSlider", enabled: true, width: 50},
              {id: "wifi", enabled: true, width: 50},
              {id: "bluetooth", enabled: true, width: 50},
              {id: "audioOutput", enabled: true, width: 50},
              {id: "audioInput", enabled: true, width: 50},
              {id: "nightMode", enabled: true, width: 50},
              {id: "darkMode", enabled: true, width: 50}])
            | if any(.controlCenterWidgets[]?; .id == "plugin_omdrop") then
                .controlCenterWidgets |= map(if .id == "plugin_omdrop" then .enabled = true else . end)
              else .controlCenterWidgets += [{id: "plugin_omdrop", enabled: true, width: 50}] end
          ' "$settings" > "$settings.omdrop-tmp"
          ${pkgs.coreutils}/bin/mv "$settings.omdrop-tmp" "$settings"
        fi
      fi
    '';
    xdg.desktopEntries.owly-setup = {
      name = "Set Up AirDrop";
      comment = "Install the pinned Owly radio service on Ubuntu";
      exec = "sudo ${systemInstaller}/bin/hp-os-owly-install-system";
      icon = "network-wireless";
      terminal = true;
      categories = [ "Network" "Settings" ];
      noDisplay = osConfig != null;
    };
    xdg.desktopEntries.owly-radio = {
      name = "Omdrop AirDrop";
      genericName = "Send and receive files with Apple devices";
      comment = "Open the graphical Omdrop panel, device radar and Wi-Fi status";
      exec = "${gui}/bin/hp-os-omdrop";
      icon = "network-wireless";
      terminal = false;
      categories = [ "Network" "FileTransfer" ];
      settings.Keywords = "Owly;AirDrop;Omdrop;Send;Receive;";
    };
    # Keep old desktop IDs usable for existing pinned launchers.
    xdg.desktopEntries.owly-receive = {
      name = "Receive with AirDrop";
      exec = "${gui}/bin/hp-os-omdrop";
      icon = "folder-download";
      terminal = false;
      noDisplay = true;
    };
    xdg.desktopEntries.owly-status = {
      name = "AirDrop Status";
      exec = "${gui}/bin/hp-os-omdrop";
      icon = "network-wireless";
      terminal = false;
      noDisplay = true;
    };
  };
}
