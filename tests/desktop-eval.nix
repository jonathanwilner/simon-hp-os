{ source, system }:
let
  fleet = builtins.getFlake source;
  pkgs = import fleet.inputs.nixpkgs { inherit system; };
  evaluate = enabled: fleet.inputs.nixpkgs.lib.nixosSystem {
    inherit system;
    modules = [ fleet.nixosModules.desktop { programs.hp-os-fleet.desktop.enable = enabled; } ];
  };
  enabled = (evaluate true).config;
  disabled = (evaluate false).config;
  home = fleet.inputs.home-manager.lib.homeManagerConfiguration {
    inherit pkgs;
    modules = [ ../fleet/release/home.nix ({ lib, ... }: {
      options.programs.hp-os-fleet.enable = lib.mkOption { type = lib.types.bool; default = true; };
      config = { home.username = "test"; home.homeDirectory = "/home/test"; home.stateVersion = "25.05"; };
    }) ];
  };
  service = home.config.systemd.user.services.fleet-release-report.Service;
in assert enabled.services.printing.enable;
assert enabled.programs.system-config-printer.enable;
assert !disabled.services.printing.enable;
assert !builtins.elem pkgs.ripgrep disabled.environment.systemPackages;
assert builtins.elem pkgs.ripgrep enabled.environment.systemPackages;
assert builtins.elem pkgs.fd enabled.environment.systemPackages;
assert !enabled.services.openssh.enable;
assert builtins.match ".*--checkout.*" (builtins.head service.ExecStart) == null;
assert builtins.elem "NOM_TMUX_KEEP_SESSION=0" service.Environment;
{
  inherit system;
  packages = map (p: p.pname or p.name) enabled.environment.systemPackages;
  reportCommand = service.ExecStart;
  activeGeneration = home.config.home.activation.recordFleetRelease.data;
  polkit = enabled.security.polkit.extraConfig;
}
