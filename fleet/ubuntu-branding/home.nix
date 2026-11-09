{ config, lib, pkgs, ... }:
{
  config = lib.mkIf (config.programs.hp-os-fleet.enable && pkgs.stdenv.hostPlatform.isLinux) {
    # Privileged Ubuntu integration is explicit; Home Manager never switches a
    # running display manager or rewrites boot images during activation.
    # Shared instructions, separate from either runtime's session databases.
    home.file.".codex/skills/hp-os-motion-design".source = ./skills/hp-os-motion-design;
    home.file.".agents/skills/hp-os-motion-design".source = ./skills/hp-os-motion-design;
    home.packages = [ (pkgs.callPackage ./package.nix {}) ];
  };
}
