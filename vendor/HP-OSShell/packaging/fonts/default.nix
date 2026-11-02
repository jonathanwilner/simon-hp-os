{ lib, stdenvNoCC, fetchurl, unzip }:
let
  provenance = builtins.fromJSON (builtins.readFile ./official-source.json);
in stdenvNoCC.mkDerivation {
  pname = "hp-os-harmonyos-sans";
  version = "2.040-20260612";
  src = fetchurl {
    name = "HarmonyOS-Sans-official.zip";
    url = provenance.url;
    sha256 = provenance.sha256;
  };
  nativeBuildInputs = [ unzip ];
  sourceRoot = "HarmonyOS Sans";
  installPhase = ''
    runHook preInstall
    install -d "$out/share/fonts/truetype/hp-os" "$out/share/licenses/hp-os-harmonyos-sans"
    install -m444 ./*.ttf "$out/share/fonts/truetype/hp-os/"
    install -m444 LICENSE-update.txt "$out/share/licenses/hp-os-harmonyos-sans/LICENSE.txt"
    cp ${./official-source.json} "$out/share/licenses/hp-os-harmonyos-sans/provenance.json"
    printf '%s\n' 'HP-OS uses HarmonyOS Sans Fonts. Copyright 2021 Huawei Device Co., Ltd.' > "$out/share/licenses/hp-os-harmonyos-sans/NOTICE.txt"
    runHook postInstall
  '';
  meta = {
    description = "Unmodified HarmonyOS Sans fonts for HP-OS";
    homepage = provenance.resource_page;
    license = lib.licenses.unfree;
    platforms = lib.platforms.all;
  };
}
