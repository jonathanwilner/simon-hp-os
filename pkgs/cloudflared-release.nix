{ lib, stdenvNoCC, fetchurl }:
let
  version = "2026.10.7";
  # Official release assets include Go 1.27.3 and the October 2026
  # certificate security update (minimum cloudflared version: 2026.10.2).
  assets = {
    x86_64-linux = {
      name = "cloudflared-linux-amd64";
      hash = "sha256:1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872";
    };
    aarch64-linux = {
      name = "cloudflared-linux-arm64";
      hash = "sha256:3df43aedc9ff291d1735b5cb576cb97e0b157488796db2e32b28aecabb445775";
    };
  };
  asset = assets.${stdenvNoCC.hostPlatform.system};
in
stdenvNoCC.mkDerivation {
  pname = "cloudflared";
  inherit version;
  src = fetchurl {
    url = "https://github.com/cloudflare/cloudflared/releases/download/${version}/${asset.name}";
    sha256 = lib.removePrefix "sha256:" asset.hash;
  };
  dontUnpack = true;
  dontStrip = true;
  installPhase = ''
    runHook preInstall
    install -Dm755 "$src" "$out/bin/cloudflared"
    runHook postInstall
  '';
  meta = {
    description = "Cloudflare Tunnel client, official upstream release";
    homepage = "https://github.com/cloudflare/cloudflared";
    license = lib.licenses.asl20;
    platforms = builtins.attrNames assets;
    mainProgram = "cloudflared";
  };
}
