{ config, lib, pkgs, ... }:
{
  options.programs.hp-os-fleet.mediaKeys.enable =
    lib.mkEnableOption "shared audio and media key commands" // { default = true; };
  options.programs.hp-os-fleet.mediaKeys.package = lib.mkOption {
    type = lib.types.package;
    default = pkgs.callPackage ./media-key-package.nix { };
    description = "Pinned audio and media key command used by compositor bindings.";
  };

  config = lib.mkIf (config.programs.hp-os-fleet.enable && config.programs.hp-os-fleet.mediaKeys.enable) {
    home.packages = [ config.programs.hp-os-fleet.mediaKeys.package ];
  };
}
