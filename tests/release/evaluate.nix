{ source, system }:
let
  f = builtins.getFlake source;
  pkgs = import f.inputs.nixpkgs { inherit system; config.allowUnfree = true; };
  hm = f.inputs.home-manager.lib.homeManagerConfiguration {
    inherit pkgs;
    modules = [ f.homeModules.fleetApps {
      home.username = "fleet-ci";
      home.homeDirectory = "/home/fleet-ci";
      home.stateVersion = "26.05";
    } ];
  };
  ghostty = hm.config.programs.hp-os-fleet.ghostty.package;
in assert pkgs.lib.versionAtLeast ghostty.version "1.4";
assert ghostty.drvPath == f.packages.${system}.ghostty.drvPath;
{
  packages = builtins.mapAttrs (_: p: p.drvPath) f.packages.${system};
  homePackages = builtins.listToAttrs (builtins.map (p: { name = p.name; value = p.drvPath; }) hm.config.home.packages);
  checks = builtins.mapAttrs (_: p: p.drvPath) f.checks.${system};
  launcher = hm.config.home.file.".local/bin/fuzzel-launch".text;
  activation = hm.activationPackage.drvPath;
  simonActivation = f.homeConfigurations.simon-daytona.activationPackage.drvPath;
}
