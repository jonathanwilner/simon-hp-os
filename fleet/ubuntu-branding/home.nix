{ config, lib, pkgs, ... }:
{
  config = lib.mkIf (config.programs.hp-os-fleet.enable && pkgs.stdenv.hostPlatform.isLinux) {
    # Privileged Ubuntu integration is explicit; Home Manager never switches a
    # running display manager or rewrites boot images during activation.
    home.packages = [ (pkgs.callPackage ./package.nix {}) ];
  };
}
