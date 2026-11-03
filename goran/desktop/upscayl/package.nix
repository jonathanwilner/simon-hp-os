{ lib, stdenvNoCC, fetchurl, appimageTools, electron, makeWrapper, asar, upscayl-ncnn }:
let
  version = "2.15.0";
  payload = appimageTools.extractType2 {
    pname = "upscayl-assets";
    inherit version;
    src = fetchurl {
      url = "https://github.com/upscayl/upscayl/releases/download/v${version}/upscayl-${version}-linux.AppImage";
      hash = "sha256-ZFlFfliby5nneepELc5gi6zaM5FrcBmohit8YlKqgik=";
    };
  };
in stdenvNoCC.mkDerivation {
  pname = "upscayl";
  inherit version;
  dontUnpack = true;
  nativeBuildInputs = [ makeWrapper asar ];
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/upscayl/bin" "$out/bin"
    asar extract ${payload}/resources/app.asar app
    substituteInPlace app/export/electron/main-window.js \
      --replace-fail 'electron_updater_1.autoUpdater.checkForUpdates();' \
        'console.log("Updates are managed by Home Manager");'
    asar pack app "$out/share/upscayl/app.asar"
    cp -r ${payload}/resources/models "$out/share/upscayl/models"
    ln -s ${upscayl-ncnn}/bin/upscayl-bin "$out/share/upscayl/bin/upscayl-bin"
    makeWrapper ${electron}/bin/electron "$out/bin/upscayl" \
      --set ELECTRON_IS_DEV 0 \
      --add-flags "$out/share/upscayl/app.asar --disable-setuid-sandbox" \
      --prefix LD_LIBRARY_PATH : /run/opengl-driver/lib
    install -Dm644 ${payload}/upscayl.png "$out/share/icons/hicolor/512x512/apps/upscayl.png"
    install -Dm644 ${payload}/upscayl.desktop "$out/share/applications/upscayl.desktop"
    substituteInPlace "$out/share/applications/upscayl.desktop" \
      --replace-fail 'Exec=AppRun --no-sandbox %U' "Exec=$out/bin/upscayl %U"
    runHook postInstall
  '';
  meta = {
    description = "Upscayl with native Electron and Vulkan upscaling engine";
    homepage = "https://github.com/upscayl/upscayl";
    license = lib.licenses.agpl3Plus;
    platforms = lib.platforms.linux;
    mainProgram = "upscayl";
  };
}
