{ system ? builtins.currentSystem }:
let
  fleet = builtins.getFlake (toString ../.);
  pkgs = import fleet.inputs.nixpkgs { inherit system; config.allowUnfree = true; };
  home = fleet.inputs.home-manager.lib.homeManagerConfiguration {
    inherit pkgs;
    modules = [ fleet.homeModules.fleetApps {
      home.username = "fleet-test";
      home.homeDirectory = "/home/fleet-test";
      home.stateVersion = "26.05";
    } ];
  };
  entries = builtins.filter (name: builtins.match "applications/microsoft365-.*" name != null) (builtins.attrNames home.config.xdg.dataFile);
  desktop = builtins.filter (name: builtins.match "/home/fleet-test/Desktop/Microsoft.*" name != null) (builtins.attrNames home.config.home.file);
in assert builtins.length entries == 25; assert builtins.length desktop == 25;
{ inherit system entries desktop; }
