{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-branding;
  loginTheme = pkgs.runCommand "sddm-hp-os" {} ''
    mkdir -p $out/share/sddm/themes/hp-os
    cp -r ${./sddm/hp-os}/. $out/share/sddm/themes/hp-os/
    chmod -R u+w $out/share/sddm/themes/hp-os
    mkdir -p $out/share/sddm/themes/hp-os/fonts
    ln -s ${lib.escapeShellArg cfg.formaRegular} $out/share/sddm/themes/hp-os/fonts/HPForma-Regular.ttf
    ln -s ${lib.escapeShellArg cfg.formaMedium} $out/share/sddm/themes/hp-os/fonts/HPForma-Medium.ttf
    cat > $out/share/sddm/themes/hp-os/theme.conf <<'CONF'
[General]
preferredSession=${if config.services.displayManager.defaultSession == null then "" else config.services.displayManager.defaultSession + ".desktop"}
reducedMotion=${lib.boolToString cfg.reducedMotion}
CONF
  '';
  bootTheme = pkgs.runCommand "plymouth-hp-os" {} ''
    mkdir -p $out/share/plymouth/themes/hp-os
    cp -r ${./plymouth}/. $out/share/plymouth/themes/hp-os/
    chmod -R u+w $out/share/plymouth/themes/hp-os
    substituteInPlace $out/share/plymouth/themes/hp-os/hp-os.plymouth \
      --replace-fail /usr/share/plymouth/themes/hp-os $out/share/plymouth/themes/hp-os
  '';
in {
  options.programs.hp-os-branding = {
    enable = lib.mkEnableOption "shared HP-OS boot and authenticated login motion";
    reducedMotion = lib.mkOption { type = lib.types.bool; default = false; };
    formaRegular = lib.mkOption { type = lib.types.str; default = "/usr/local/share/fonts/hp/HPFormaDJROffice-Regular.ttf"; description = "Host-local licensed font. Never copied into the public flake."; };
    formaMedium = lib.mkOption { type = lib.types.str; default = "/usr/local/share/fonts/hp/HPFormaDJROffice-Medium.ttf"; };
  };
  config = lib.mkIf cfg.enable {
    boot.plymouth = { enable = lib.mkDefault true; theme = "hp-os"; themePackages = [ bootTheme ]; };
    services.displayManager.sddm.theme = lib.mkIf config.services.displayManager.sddm.enable "hp-os";
    environment.systemPackages = lib.mkIf config.services.displayManager.sddm.enable [ loginTheme ];
    fonts.packages = [ pkgs.dejavu_fonts ];
    systemd.services.display-manager.restartIfChanged = lib.mkForce false;
  };
}
