{ pkgs }:
let
  inherit (pkgs) lib;
  versions = builtins.fromJSON (builtins.readFile ./versions.json);
  names = builtins.attrNames versions;
  runtimeLibraries = with pkgs; [
    (pkgs.libx11 or pkgs.xorg.libX11) (pkgs.libxcursor or pkgs.xorg.libXcursor) (pkgs.libxi or pkgs.xorg.libXi) (pkgs.libxrandr or pkgs.xorg.libXrandr) libxkbcommon wayland
    vulkan-loader libGL alsa-lib fontconfig freetype dbus
  ];
  native = lib.genAttrs names (name:
    let release = versions.${name}; in
    pkgs.stdenv.mkDerivation {
      pname = name;
      inherit (release) version;
      src = pkgs.fetchurl release.assets.${pkgs.stdenv.hostPlatform.system};
      nativeBuildInputs = [ pkgs.autoPatchelfHook pkgs.makeWrapper ];
      buildInputs = [ pkgs.stdenv.cc.cc.lib ] ++ runtimeLibraries;
      dontBuild = true;
      installPhase = ''
        runHook preInstall
        mkdir -p "$out"
        cp -r bin share "$out/"
        chmod +x "$out/bin/"*
        for executable in "$out/bin/"*; do
          wrapProgram "$executable" --prefix LD_LIBRARY_PATH : ${lib.makeLibraryPath runtimeLibraries}
        done
        substituteInPlace "$out/share/applications/ai.storyteller.${name}.desktop" \
          --replace-fail "Exec=${name} " "Exec=$out/bin/${name} " \
          --replace-warn "TryExec=${name}" "TryExec=$out/bin/${name}"
        runHook postInstall
      '';
      meta = {
        description = "ArtCraft ${name} creative application";
        homepage = "https://getartcraft.com/apps";
        changelog = release.release;
        license = [ lib.licenses.mit lib.licenses.asl20 ];
        platforms = [ "x86_64-linux" "aarch64-linux" ];
        mainProgram = name;
        sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
      };
    });
  web = lib.genAttrs names (name:
    let release = versions.${name}; in
    pkgs.stdenvNoCC.mkDerivation {
      pname = "${name}-web";
      inherit (release) version;
      src = pkgs.fetchurl release.assets.web;
      nativeBuildInputs = [ pkgs.unzip ];
      dontBuild = true;
      installPhase = ''
        runHook preInstall
        mkdir -p "$out"
        # Publish the whole upstream bundle. Layouts differ per app: photocraft
        # ships app/ with the loader and its .part-aa payload, vectorcraft ships
        # fonts/, icons/ and licenses/, and every app needs snippets/.
        # Cargo build intermediates are dropped when a release includes them.
        cp -r . "$out"/
        chmod -R u+w "$out"
        rm -rf "$out"/src "$out"/target "$out"/vendor "$out"/.cargo \
          "$out"/Cargo.toml "$out"/Cargo.lock "$out"/rust-toolchain*
        # The part loader at app/<name>-web.js imports ./snippets/... relative to
        # app/, while the release ships snippets/ at the bundle root. Keep both
        # resolutions working.
        if [ -d "$out/app" ] && [ -d "$out/snippets" ] && [ ! -e "$out/app/snippets" ]; then
          cp -r "$out/snippets" "$out/app/snippets"
        fi
        test -f "$out/index.html"
        test -n "$(find "$out" -name '*.wasm' -print -quit)"
        runHook postInstall
      '';
      meta = {
        description = "Static WebAssembly build of ${name}";
        homepage = "https://getartcraft.com/apps";
        changelog = release.release;
        license = [ lib.licenses.mit lib.licenses.asl20 ];
        platforms = lib.platforms.all;
        sourceProvenance = [ lib.sourceTypes.binaryBytecode ];
      };
    });
  combinedWeb = pkgs.runCommand "artcraft-web-suite" { } ''
    mkdir -p "$out"
    ${lib.concatMapStringsSep "\n" (name: ''ln -s ${web.${name}} "$out/${name}"'') names}
    cp ${./local-index.html} "$out/index.html"
    cp ${./versions.json} "$out/versions.json"
  '';
in
native // lib.mapAttrs' (name: value: lib.nameValuePair "${name}-web" value) web // {
  suite = pkgs.symlinkJoin {
    name = "artcraft-suite";
    paths = builtins.attrValues native;
  };
  web = combinedWeb;
  serve = pkgs.writeShellApplication {
    name = "artcraft-serve";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      exec python3 ${./serve.py} --port "''${ARTCRAFT_PORT:-8175}" --directory ${combinedWeb} "$@"
    '';
  };
  update = pkgs.writeShellApplication {
    name = "artcraft-update";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      target="''${1:-flakes/artcraft-suite}"
      shift || true
      if [[ ! -w "$target/versions.json" ]]; then
        echo "Run from the repository root, or pass a writable artcraft-suite directory." >&2
        exit 1
      fi
      exec python3 "$target/update.py" "$@"
    '';
  };
}
