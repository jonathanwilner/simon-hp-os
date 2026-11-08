{ config, lib, pkgs, ... }:
let cfg = config.programs.hp-os-fleet;
in {
  options.programs.hp-os-fleet.steam.enable = lib.mkEnableOption "native ARM64 Steam launcher and explicit Ubuntu bootstrap" // {
    default = pkgs.stdenv.hostPlatform.isAarch64;
  };
  config = lib.mkIf (cfg.enable && cfg.steam.enable && pkgs.stdenv.hostPlatform.isAarch64) {
    home.packages = [ (import ./package.nix { inherit pkgs; }) ];
    # Client installation is explicit. Home activation never downloads clients
    # or modifies Steam account, library or per-game compatibility settings.
  };
}
