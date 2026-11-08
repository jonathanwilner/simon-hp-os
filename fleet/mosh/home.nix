{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.mosh;
  hostType = lib.types.submodule {
    options = {
      private = lib.mkOption { type = lib.types.nullOr lib.types.str; default = null; description = "Private DNS name reached through LAN, WARP or WireGuard routing."; };
      tailscale = lib.mkOption { type = lib.types.nullOr lib.types.str; default = null; description = "DNS name resolving to this host's Tailscale address."; };
      hostKeyAlias = lib.mkOption { type = lib.types.str; description = "Existing trusted SSH host-key alias."; };
      user = lib.mkOption { type = lib.types.str; default = ""; description = "SSH user; empty uses the local SSH default."; };
    };
  };
in {
  options.programs.hp-os-fleet.mosh.hosts = lib.mkOption {
    type = lib.types.attrsOf hostType;
    default = {};
    description = "Private fleet destinations. Host identities stay in consumer configuration.";
  };
  config = lib.mkIf config.programs.hp-os-fleet.enable {
    home.packages = [ pkgs.mosh (pkgs.callPackage ./package.nix {}) ];
    home.sessionVariables.MOSH_SERVER_NETWORK_TMOUT = "604800";
    xdg.configFile."fleet-mosh/hosts.json".text = builtins.toJSON cfg.hosts;
  };
}
