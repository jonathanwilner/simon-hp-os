{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet;
  client = pkgs.callPackage ./package.nix {};
  gui = pkgs.callPackage ./gui-package.nix { inherit client; };
in {
  options.programs.hp-os-fleet.printing.enable = lib.mkEnableOption "Wi-Fi Aware IPP printing client" // { default = true; };
  config = lib.mkIf (cfg.enable && cfg.printing.enable) {
    xdg.configFile."hp-os/printing".source = "${gui}/share/hp-os-printing";
    home.packages = [ client gui (pkgs.callPackage ./ubuntu-system.nix {}) ];
    xdg.desktopEntries.hp-os-aware-print = {
      name = "Wi-Fi Aware Printing";
      comment = "Check the dedicated printing radio and discover compatible IPP printers";
      exec = "${gui}/bin/hp-os-aware-print-gui";
      icon = "printer";
      terminal = false;
      categories = [ "Utility" "Settings" ];
      settings.Keywords = "Printer;Wi-Fi Aware;NAN;IPP;";
    };
  };
}
