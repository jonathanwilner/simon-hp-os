# Public desktop policy. Keep identity, hardware and secrets in host modules.
{ config, lib, pkgs, ... }:
let cfg = config.programs.hp-os-fleet;
in {
  imports = [ ./mosh/home.nix ./release/home.nix ./chrome-channels/home.nix ../goran/desktop/upscayl/home.nix ./launcher-apps.nix ./media-keys.nix ./owly/home.nix ./relay/home.nix ./printing/home.nix ];
  options.programs.hp-os-fleet = {
    enable = lib.mkEnableOption "shared HP-OS fleet desktop defaults" // { default = true; };
    upscayl.enable = lib.mkEnableOption "native Upscayl" // { default = true; };
    wallpapers.enable = lib.mkEnableOption "original HP-OS wallpaper collection" // { default = true; };
  };
  config = lib.mkIf cfg.enable {
    home.file."Pictures/Wallpapers/HP-OS" = lib.mkIf cfg.wallpapers.enable {
      source = ../goran/desktop/wallpapers/images;
      recursive = true;
    };
  };
}
