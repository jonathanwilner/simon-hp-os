{ system ? builtins.currentSystem, overlay ? true }:
let
  fleet = builtins.getFlake (toString ../.);
  pkgs = import fleet.inputs.nixpkgs { inherit system; config.allowUnfree = true; overlays = if overlay then [ fleet.overlays.chromeChannels ] else []; };
  home = fleet.inputs.home-manager.lib.homeManagerConfiguration {
    inherit pkgs;
    modules = [ fleet.homeModules.fleetApps {
      home.username = "fleet-test";
      home.homeDirectory = "/home/fleet-test";
      home.stateVersion = "26.05";
      programs.hp-os-fleet.microsoft365.teamsCliPackage = pkgs.writeShellScriptBin "teams-cli" "exit 0";
    } ];
  };
  entries = builtins.filter (name: builtins.match "applications/microsoft365-.*" name != null) (builtins.attrNames home.config.xdg.dataFile);
  desktop = builtins.filter (name: builtins.match "/home/fleet-test/Desktop/Microsoft.*" name != null) (builtins.attrNames home.config.home.file);
in assert home.config.systemd.user.timers.teams-cli-session-warm.Timer.OnUnitInactiveSec == "30min";
assert builtins.match ".*--force.*" home.config.systemd.user.services.teams-cli-session-warm.Service.ExecStart != null;
assert builtins.length entries == 25; assert builtins.length desktop == 25;
{ inherit system entries desktop; sources = map (name: toString home.config.xdg.dataFile.${name}.source) entries; }
