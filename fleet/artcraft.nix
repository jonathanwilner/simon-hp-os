# The upstream native suite publishes both ARM64 and x86-64 releases.
# GPU-specific presentation overrides belong to individual host modules.
{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.artcraft;
  native = import ../flakes/artcraft-suite/packages.nix { inherit pkgs; };
in {
  options.programs.hp-os-fleet.artcraft = {
    enable = lib.mkEnableOption "native Artcraft creative applications";
    package = lib.mkOption {
      type = lib.types.package;
      default = native.suite;
      description = "Native architecture suite without GPU vendor overrides.";
    };
  };
  config = lib.mkIf (config.programs.hp-os-fleet.enable && cfg.enable) {
    home.packages = [ cfg.package ];
  };
}
