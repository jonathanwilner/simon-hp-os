{ lib, stdenvNoCC, makeWrapper, touchBackend, touchPython, quickshell, touchGestures ? true,
  qt6, squeekboard, niri, glib, wayland-utils, rime-data, iio-sensor-proxy, pulseaudio, wl-clipboard,
  noto-fonts, noto-fonts-cjk-sans, noto-fonts-color-emoji, makeFontsConf }:
let
  fonts = makeFontsConf { fontDirectories = [ noto-fonts noto-fonts-cjk-sans noto-fonts-color-emoji ]; };
in stdenvNoCC.mkDerivation {
  pname = "hp-os-touch-support";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/share/hp-os-touch"
    cp -r controller qml "$out/share/hp-os-touch/"
    makeWrapper ${touchPython}/bin/python3 "$out/bin/touch-support" \
      --add-flags "$out/share/hp-os-touch/controller/touch_support.py" \
      --set HP_OS_TOUCH_BACKEND ${touchBackend}/bin/hp-os-input-backend \
      --set HP_OS_TOUCH_QML "$out/bin/hp-os-keyboard" \
      --set HP_OS_TOUCH_SETTINGS_COMMAND "$out/bin/hp-os-keyboard-settings" \
      --set HP_OS_TOUCH_SQUEEKBOARD ${squeekboard}/bin/squeekboard \
      --set HP_OS_TOUCH_NIRI ${niri}/bin/niri \
      --set HP_OS_TOUCH_PATCHED "${if touchGestures then "1" else "0"}" \
      --set HP_OS_TOUCH_RIME_DATA ${rime-data}/share/rime-data \
      --prefix PATH : ${lib.makeBinPath [ glib wayland-utils niri squeekboard iio-sensor-proxy ]}
    makeWrapper ${quickshell}/bin/qs "$out/bin/hp-os-keyboard" \
      --add-flags "-n -p $out/share/hp-os-touch/qml" \
      --set FONTCONFIG_FILE ${fonts} \
      --prefix PATH : "$out/bin:${lib.makeBinPath [ touchPython pulseaudio wl-clipboard ]}" \
      --prefix QML2_IMPORT_PATH : ${lib.makeSearchPath "lib/qt-6/qml" [ qt6.qtdeclarative qt6.qtmultimedia ]}
    makeWrapper ${quickshell}/bin/qs "$out/bin/hp-os-keyboard-settings" \
      --add-flags "-n -p $out/share/hp-os-touch/qml/settings.qml" \
      --set HP_OS_TOUCH_SETTINGS 1 \
      --set FONTCONFIG_FILE ${fonts} \
      --prefix PATH : "$out/bin:${lib.makeBinPath [ touchPython pulseaudio wl-clipboard ]}"
  '';
  meta = { description = "HP-OS touch keyboard and posture controller"; license = lib.licenses.gpl3Only; platforms = lib.platforms.linux; };
}
