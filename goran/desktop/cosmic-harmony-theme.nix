{ config, lib, pkgs, ... }:
let
  applyTheme = pkgs.writeShellApplication {
    name = "hp-os-cosmic-theme";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      exec python3 ${./cosmic-harmony-theme.py} \
        --defaults ${pkgs.cosmic-settings}/share/cosmic "$@"
    '';
  };
in {
  # Native COSMIC config remains writable so its watcher can reload palettes.
  # Both modes are prepared; HP-OS owns the sunrise/sunset mode selection.
  home.packages = [ applyTheme ];
  home.activation.cosmicHarmonyTheme = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    run ${applyTheme}/bin/hp-os-cosmic-theme --config ${lib.escapeShellArg config.xdg.configHome}
  '';
  xdg.configFile."fontconfig/conf.d/91-cosmic-harmony-fallback.conf".text = ''
    <?xml version="1.0"?>
    <!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
    <fontconfig>
      <match target="pattern">
        <test name="family"><string>HarmonyOS Sans</string></test>
        <edit name="family" mode="append"><string>HarmonyOS Sans SC</string></edit>
      </match>
    </fontconfig>
  '';
}
