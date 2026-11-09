# Opt-in system integration. Hardware, identities, networking and login sessions
# stay in each consumer's host configuration.
{ config, lib, pkgs, ... }:
let cfg = config.programs.hp-os-fleet.desktop;
in {
  options.programs.hp-os-fleet.desktop.enable = lib.mkEnableOption "shared HP-OS NixOS desktop integration";
  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ pkgs.ripgrep pkgs.fd pkgs.tmux pkgs.python3 (pkgs.callPackage ../../pkgs/nom-dashboard.nix {}) ];
    services.printing.enable = lib.mkDefault true;
    programs.system-config-printer.enable = lib.mkDefault true;
    security.polkit.enable = lib.mkDefault true;
    # Match the existing desktop permissions for administrators. These action
    # families cover desktop prompts; systemd management and sudo stay local.
    security.polkit.extraConfig = ''
      polkit.addRule(function(action, subject) {
        if (subject.isInGroup("wheel") && (
          action.id.indexOf("org.freedesktop.color-manager.") == 0 ||
          action.id.indexOf("org.opensuse.cupspkhelper.mechanism.") == 0 ||
          action.id == "org.freedesktop.NetworkManager.enable-disable-statistics" ||
          action.id == "org.freedesktop.packagekit.system-sources-refresh" ||
          action.id.indexOf("org.freedesktop.Flatpak.") == 0
        )) {
          return polkit.Result.YES;
        }
      });
    '';
  };
}
