{ config, lib, pkgs, owlySource, osConfig ? null, ... }:
let
  cfg = config.programs.hp-os-fleet;
  owly = pkgs.callPackage "${owlySource}/nix/package.nix" {};
  toml = pkgs.formats.toml {};
  systemInstaller = pkgs.callPackage ./ubuntu-system.nix {
    inherit owly owlySource;
    radioConfig = if cfg.owly.settings == {} then null else toml.generate "owly-radio.toml" cfg.owly.settings;
  };
  omdrop = pkgs.callPackage ./omdrop-package.nix { inherit owlySource; };
  controller = pkgs.callPackage ./controller-package.nix {
    inherit omdrop owly;
    allowSteering = cfg.owly.automaticWifiSwitching;
  };
  gui = pkgs.callPackage ./gui-package.nix { inherit omdrop owly controller; };

in {
  options.programs.hp-os-fleet.owly = {
    enable = lib.mkEnableOption "Owly AirDrop tools" // { default = true; };
    automaticWifiSwitching = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Temporarily roam to a compatible access point on the same saved Wi-Fi network when receiving with AirDrop. Restore the original connection on stop, expiry, or failure.";
    };
    settings = lib.mkOption {
      inherit (toml) type;
      default = {};
      description = "Host-specific Ubuntu radio settings. NixOS uses services.owly.settings.";
    };
  };
  config = lib.mkIf (cfg.enable && cfg.owly.enable) {
    # The root helper refuses NixOS; NixOS uses the exported system module.
    home.packages = [ owly omdrop controller gui systemInstaller ];
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
