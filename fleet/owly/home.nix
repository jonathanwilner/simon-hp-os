{ config, lib, pkgs, owlySource, ... }:
let
  cfg = config.programs.hp-os-fleet;
  owly = pkgs.callPackage "${owlySource}/nix/package.nix" {};
  downloads = if config.xdg.userDirs.download != null then config.xdg.userDirs.download else "${config.home.homeDirectory}/Downloads";
  toml = pkgs.formats.toml {};
  systemInstaller = pkgs.callPackage ./ubuntu-system.nix {
    inherit owly;
    radioConfig = if cfg.owly.settings == {} then null else toml.generate "owly-radio.toml" cfg.owly.settings;
  };
  status = pkgs.writeShellScriptBin "hp-os-owly-status" ''
    ${owly}/bin/owly doctor
    printf '\nPress Enter to close.\n'
    read -r _
  '';
in {
  options.programs.hp-os-fleet.owly = {
    enable = lib.mkEnableOption "Owly AirDrop tools" // { default = true; };
    settings = lib.mkOption {
      inherit (toml) type;
      default = {};
      description = "Host-specific Ubuntu radio settings. NixOS uses services.owly.settings.";
    };
  };
  config = lib.mkIf (cfg.enable && cfg.owly.enable) {
    # The root helper refuses NixOS; NixOS uses the exported system module.
    home.packages = [ owly status systemInstaller ];
    xdg.desktopEntries.owly-setup = {
      name = "Set Up AirDrop";
      comment = "Install the pinned Owly radio service on Ubuntu";
      exec = "sudo ${systemInstaller}/bin/hp-os-owly-install-system";
      icon = "network-wireless";
      terminal = true;
      categories = [ "Network" "Settings" ];
      noDisplay = lib.mkDefault false;
    };
    xdg.desktopEntries.owly-radio = {
      name = "AirDrop Radio";
      comment = "Start Owly Wi-Fi sharing until this terminal closes; some cards disconnect Wi-Fi";
      exec = "${owly}/bin/owly radio up";
      icon = "network-wireless";
      terminal = true;
      categories = [ "Network" "FileTransfer" ];
    };
    xdg.desktopEntries.owly-receive = {
      name = "Receive with AirDrop";
      comment = "Receive files in Downloads after starting AirDrop Radio";
      exec = "${owly}/bin/owly receive --dir \"${downloads}\"";
      icon = "folder-download";
      terminal = true;
      categories = [ "Network" "FileTransfer" ];
    };
    xdg.desktopEntries.owly-status = {
      name = "AirDrop Status";
      comment = "Check Wi-Fi card support and Owly system integration";
      exec = "${status}/bin/hp-os-owly-status";
      icon = "network-wireless";
      terminal = true;
      categories = [ "Network" "Settings" ];
    };
  };
}
