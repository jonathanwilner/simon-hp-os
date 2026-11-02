{
  lib,
  stdenvNoCC,
  coreutils,
  jq,
}:

stdenvNoCC.mkDerivation {
  pname = "hp-os-dms-theme";
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
      "$out/share/doc/hp-os-dms-theme" \
      "$out/share/fonts/truetype/hp-os" \
      "$out/share/hp-os-dms-theme/themes" \
      "$out/share/hp-os-dms-theme/tokens" \
      "$out/share/licenses/hp-os-dms-theme"

    install -m444 fonts/HarmonyOS_Sans*.ttf "$out/share/fonts/truetype/hp-os/"
    install -m444 themes/hp-os.json "$out/share/hp-os-dms-theme/themes/"
    install -m444 tokens/hp-os.json "$out/share/hp-os-dms-theme/tokens/"
    install -m444 fontconfig/60-hp-os-sans.conf "$out/etc/fonts/conf.d/"
    install -m444 README.md "$out/share/doc/hp-os-dms-theme/README.md"
    install -m444 LICENSE_Fonts "$out/share/licenses/hp-os-dms-theme/LICENSE_Fonts"
    install -m444 font-hashes.sha256 "$out/share/doc/hp-os-dms-theme/font-hashes.sha256"

    install -m555 scripts/hp-os-theme-migrate "$out/bin/hp-os-theme-migrate"

    substitute scripts/hp-os-theme-apply "$out/bin/hp-os-theme-apply" \
      --replace-fail '@jq@' '${jq}/bin/jq' \
      --replace-fail '@theme_file@' "$out/share/hp-os-dms-theme/themes/hp-os.json"
    substitute scripts/hp-os-theme-restore "$out/bin/hp-os-theme-restore" \
      --replace-fail '@jq@' '${jq}/bin/jq'
    chmod 555 "$out/bin/hp-os-theme-apply" "$out/bin/hp-os-theme-restore"

    runHook postInstall
  '';

  meta = {
    description = "HP-OS DMS/Niri theme bundled with unmodified HarmonyOS Sans";
    homepage = "https://gitee.com/openharmony/global_system_resources";
    license = lib.licenses.unfreeRedistributable or lib.licenses.unfree;
    platforms = lib.platforms.linux;
    maintainers = [ ];
  };
}
