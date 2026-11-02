{
  codexDesktop,
  bundledCliVersion,
  codexCliRelease,
  fetchurl,
  lib,
  stdenvNoCC,
}:
stdenvNoCC.mkDerivation {
  pname = "codex-cli";
  inherit (codexCliRelease) version;

  src = fetchurl {
    inherit (codexCliRelease) url hash;
  };

  dontConfigure = true;
  dontBuild = true;
  # Preserve the upstream package that daemon startup validates and copies.
  dontStrip = true;

  installPhase = ''
    runHook preInstall

    mkdir -p "$out"
    cp -a "vendor/${codexCliRelease.platformTriple}/." "$out/"

    runHook postInstall
  '';

  passthru.desktopVersion = codexDesktop.version;
  passthru.bundledCliVersion = bundledCliVersion;

  meta = {
    description = "Codex CLI and Code Mode host from a hash-pinned official OpenAI npm release";
    homepage = "https://github.com/openai/codex";
    license = lib.licenses.asl20;
    mainProgram = "codex";
    platforms = codexDesktop.meta.platforms or [ stdenvNoCC.hostPlatform.system ];
  };
}
