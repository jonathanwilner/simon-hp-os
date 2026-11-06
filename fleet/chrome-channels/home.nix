{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.chromeChannels;
  channels = [ "beta" "dev" "canary" ];
  package = channel: pkgs.${"google-chrome-${channel}"};
  wrapper = channel: pkgs.writeShellScript "google-chrome-${channel}-desktop" ''
    exec ${package channel}/bin/google-chrome-${channel} ${lib.escapeShellArgs cfg.extraArgs} "$@"
  '';
in {
  options.programs.hp-os-fleet.chromeChannels = {
    enable = lib.mkEnableOption "isolated Chrome Beta, Dev and Canary desktop channels";
    extraArgs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [];
      description = "Host-specific arguments for prerelease Chrome (for example Ubuntu sandbox integration).";
    };
  };
  config = lib.mkIf cfg.enable {
    home.packages = map package channels;
    home.file = lib.genAttrs (map (channel: ".local/bin/google-chrome-${channel}") channels)
      (path: let channel = lib.removePrefix ".local/bin/google-chrome-" path;
       in { source = wrapper channel; executable = true; });
    xdg.desktopEntries = builtins.listToAttrs (map (channel: {
      name = "google-chrome-${if channel == "dev" then "unstable" else channel}";
      value = {
        name = "Google Chrome ${{ beta = "Beta"; dev = "Dev"; canary = "Canary"; }.${channel}}";
        genericName = "Web Browser";
        exec = "${wrapper channel} %U";
        icon = "google-chrome-${if channel == "dev" then "unstable" else channel}";
        terminal = false;
        categories = [ "Network" "WebBrowser" ];
        # Stable retains all default-browser and automation registrations.
      };
    }) channels);
  };
}
