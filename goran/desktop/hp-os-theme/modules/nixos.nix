{ self }:
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.jw.hposDmsTheme;
  system = pkgs.stdenv.hostPlatform.system;
  themePackage = self.packages.${system}.default;
in
{
  options.jw.hposDmsTheme = {
    enable = lib.mkEnableOption "the HP-OS DMS/Niri desktop theme";

    user = lib.mkOption {
      type = lib.types.str;
      default = "jonathan";
      description = "Home Manager user whose DMS configuration receives the theme.";
    };
  };

  config = lib.mkIf cfg.enable {
    fonts.packages = [
      themePackage
      pkgs.fira
      # DMS normally loads these from its QML bundle. Install system-level
      # copies too so popups still resolve icons during an early FontLoader
      # failure, cache refresh, or shell restart instead of falling back to
      # HarmonyOS Sans and displaying ligature names/tofu glyphs.
      pkgs.material-symbols
      pkgs.nerd-fonts.symbols-only
    ];
    fonts.fontconfig.defaultFonts.sansSerif = lib.mkBefore [
      "HarmonyOS Sans"
      "HarmonyOS Sans SC"
      "HarmonyOS Sans TC"
      "HarmonyOS Sans Naskh Arabic UI"
    ];
    fonts.fontconfig.localConf = lib.mkAfter (builtins.readFile ../fontconfig/60-hp-os-sans.conf);
    fonts.fontconfig.defaultFonts.monospace = lib.mkBefore [ "Fira Mono" ];

    environment.systemPackages = [ themePackage ];

    home-manager.users.${cfg.user} = {
      imports = [ self.homeManagerModules.default ];
      jw.hposDmsTheme = {
        enable = true;
        package = themePackage;
      };
    };
  };
}
