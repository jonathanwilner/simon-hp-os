{
  codexDesktop,
  lib,
  stdenv,
}:
stdenv.mkDerivation {
  pname = "codex-browser-use-node-repl";
  inherit (codexDesktop) version;

  dontUnpack = true;
  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall

    install -Dm0755 \
      ${codexDesktop}/opt/codex-desktop/resources/cua_node/bin/node_repl \
      "$out/bin/node_repl"

    runHook postInstall
  '';

  meta = {
    description = "Codex Browser Use Node REPL MCP runtime";
    homepage = "https://github.com/ilysenko/codex-desktop-linux";
    license = lib.licenses.unfree;
    platforms = codexDesktop.meta.platforms or [ stdenv.hostPlatform.system ];
  };
}
