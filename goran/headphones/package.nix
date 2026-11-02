{ pkgs }:
pkgs.symlinkJoin {
  name = "goran-headphone-controls";
  postBuild = ''
    mkdir -p $out/share/icons/hicolor/256x256/apps
    cp ${pkgs.openfreebuds}/lib/python*/site-packages/openfreebuds_qt/assets/pw.mmk.OpenFreebuds.png \
      $out/share/icons/hicolor/256x256/apps/
  '';
  paths = [ pkgs.openfreebuds pkgs.librepods ];
}
