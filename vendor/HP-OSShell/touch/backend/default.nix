{ lib, stdenv, cmake, pkg-config, qt6, wayland, libxkbcommon, librime, rime-data, hunspellDicts, makeWrapper }:
stdenv.mkDerivation {
  pname = "hp-os-input-backend";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [ cmake pkg-config wayland makeWrapper ];
  buildInputs = [ qt6.qtbase wayland libxkbcommon librime ];
  dontWrapQtApps = true;
  doCheck = true;
  preCheck = ''export HP_OS_RIME_DATA=${rime-data}/share/rime-data'';
  postInstall = ''
    wrapProgram $out/libexec/hp-os-input-test-client --prefix QT_PLUGIN_PATH : ${qt6.qtwayland}/lib/qt-6/plugins
    wrapProgram $out/bin/hp-os-input-backend --set-default HP_OS_RIME_DATA ${rime-data}/share/rime-data \
      --set-default HP_OS_DICTIONARY ${hunspellDicts.en_US}/share/hunspell/en_US.dic
  '';
  meta = { description = "Native Wayland input method and local Rime bridge for HP-OS touch keyboard"; license = lib.licenses.mit; platforms = lib.platforms.linux; mainProgram = "hp-os-input-backend"; };
}
