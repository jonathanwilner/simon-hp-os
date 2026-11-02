self: { config, lib, pkgs, ... }:
let cfg = config.programs.hp-os; in {
  imports = [ ./touch-options.nix (lib.mkRenamedOptionModule [ "programs" "harmonyshell" ] [ "programs" "hp-os" ]) ];
  options.programs.hp-os = {
    enable = lib.mkEnableOption "HP-OS login session";
    package = lib.mkOption { type = lib.types.package; default = self.packages.${pkgs.stdenv.hostPlatform.system}.default; };
    enableNetworkManager = lib.mkOption { type = lib.types.bool; default = true; };
    installOfficialFonts = lib.mkOption { type = lib.types.bool; default = false; description = "Install unmodified official HarmonyOS Sans after accepting the font license terms."; };
    enableBluetooth = lib.mkOption { type = lib.types.bool; default = true; };
  };
  config = lib.mkIf cfg.enable {
    # The HP-OS wrapper carries its own compositor. Keep the existing Niri
    # package selection and its login session unchanged.
    programs.niri.enable = lib.mkDefault true;
    services.displayManager.sessionPackages = [ cfg.package ];
    environment.systemPackages = [ cfg.package pkgs.networkmanagerapplet pkgs.blueman ];
    environment.etc."hp-os/touch.json".text = builtins.toJSON cfg.touchSupport;
    hardware.sensor.iio.enable = lib.mkIf
      (cfg.touchSupport.enable && cfg.touchSupport.rotation.mode != "off") true;
    # Grant only posture switches, never all keyboard evdev devices.
    services.udev.extraRules = lib.mkIf
      (cfg.touchSupport.enable && (cfg.touchSupport.keyboard.mode == "tablet-only" || cfg.touchSupport.rotation.mode == "tablet-only")) ''
      SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_SWITCH}=="1", TAG+="uaccess"
    '';
    # brightnessctl needs its udev rules as well as the bundled executable.
    services.udev.packages = [ pkgs.brightnessctl ];
    security.polkit.enable = true;
    services.upower.enable = true;
    services.power-profiles-daemon.enable = lib.mkDefault true;
    networking.networkmanager.enable = lib.mkIf cfg.enableNetworkManager (lib.mkDefault true);
    hardware.bluetooth.enable = lib.mkIf cfg.enableBluetooth (lib.mkDefault true);
    services.pipewire = { enable = lib.mkDefault true; pulse.enable = lib.mkDefault true; wireplumber.enable = lib.mkDefault true; };
    xdg.portal = {
      enable = true;
      extraPortals = [ pkgs.xdg-desktop-portal-gtk pkgs.xdg-desktop-portal-gnome ];
      # xdg-desktop-portal lowercases XDG_CURRENT_DESKTOP entries. HP-OS
      # therefore gets its own preference without changing the Niri session.
      config.hp-os = {
        default = [ "gnome" "gtk" ];
        "org.freedesktop.impl.portal.FileChooser" = [ "gtk" ];
      };
    };
    fonts.packages = [ pkgs.material-symbols pkgs.noto-fonts-cjk-sans pkgs.noto-fonts-color-emoji ]
      ++ lib.optionals cfg.installOfficialFonts [ (pkgs.callPackage ./fonts {}) ];
  };
}
