{
  lib,
  stdenvNoCC,
  coreutils,
  jq,
}:

stdenvNoCC.mkDerivation {
  pname = "harmonyos-dms-theme";
  version = "7.0.0";
  src = ./.;

  nativeBuildInputs = [ coreutils ];
  dontBuild = true;

  installPhase = ''
    runHook preInstall

    sha256sum --check font-hashes.sha256
    printf '%s  %s\n' \
      '327e0147d4a3ca2d89e81abce45b210576b0f9fe2b29d900f64b58039f12a102' \
      'LICENSE_Fonts' | sha256sum --check -

    install -d \
      "$out/bin" \
      "$out/etc/fonts/conf.d" \
      "$out/share/doc/harmonyos-dms-theme" \
      "$out/share/fonts/truetype/harmonyos" \
      "$out/share/harmonyos-dms-theme/themes" \
      "$out/share/harmonyos-dms-theme/tokens" \
      "$out/share/licenses/harmonyos-dms-theme"

    install -m444 fonts/HarmonyOS_Sans*.ttf "$out/share/fonts/truetype/harmonyos/"
    install -m444 themes/harmonyos.json "$out/share/harmonyos-dms-theme/themes/"
    install -m444 tokens/harmonyos.json "$out/share/harmonyos-dms-theme/tokens/"
    install -m444 fontconfig/60-harmonyos-sans.conf "$out/etc/fonts/conf.d/"
    install -m444 README.md "$out/share/doc/harmonyos-dms-theme/README.md"
    install -m444 LICENSE_Fonts "$out/share/licenses/harmonyos-dms-theme/LICENSE_Fonts"
    install -m444 font-hashes.sha256 "$out/share/doc/harmonyos-dms-theme/font-hashes.sha256"

    substitute scripts/harmonyos-theme-apply "$out/bin/harmonyos-theme-apply" \
      --replace-fail '@jq@' '${jq}/bin/jq' \
      --replace-fail '@theme_file@' "$out/share/harmonyos-dms-theme/themes/harmonyos.json"
    substitute scripts/harmonyos-theme-restore "$out/bin/harmonyos-theme-restore" \
      --replace-fail '@jq@' '${jq}/bin/jq'
    chmod 555 "$out/bin/harmonyos-theme-apply" "$out/bin/harmonyos-theme-restore"

    runHook postInstall
  '';

  meta = {
    description = "HarmonyOS-inspired DMS/Niri theme bundled with unmodified HarmonyOS Sans";
    homepage = "https://gitee.com/openharmony/global_system_resources";
    license = lib.licenses.unfreeRedistributable or lib.licenses.unfree;
    platforms = lib.platforms.linux;
    maintainers = [ ];
  };
}
