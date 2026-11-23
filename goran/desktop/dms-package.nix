# Use the consumer package set so Qt and runtime dependencies stay aligned.
{ pkgs, dank-material-shell, nativePam ? false, homeDirectory ? "/home/jonathan" }:
let
  nativeBase = import ../../fleet/native-pam/package.nix {
    inherit pkgs homeDirectory;
    package = (dank-material-shell.lib.buildDmsPkgs pkgs).dux-qt-base;
    directory = "lib";
    binary = "libdux-qt-base.so.0";
  };
  base = dank-material-shell.lib.mkDmsShell pkgs;
  dms = (if nativePam then base.override { duxQtBase = nativeBase; } else base).overrideAttrs (old: {
  patches = (old.patches or []) ++ [ ./dms-brightness/manager.patch ];
  postPatch = (old.postPatch or "") + ''
    cp ${./dms-brightness/goran_panel.go} internal/server/brightness/goran_panel.go
    cp ${./dms-brightness/goran_panel_test.go} internal/server/brightness/goran_panel_test.go
  '';
  postFixup = (old.postFixup or "") + ''
    ${pkgs.python3}/bin/python3 ${../../fleet/dms-audio-controls/patch.py} "$out/share/quickshell/dms"
  '' + pkgs.lib.optionalString nativePam ''
    # PAM dlopens its modules from a library loaded by the Go executable.
    # The executable's RPATH supplies that transitive search path as well.
    elf="$out/bin/.dms-wrapped"
    rpath=$(${pkgs.patchelf}/bin/patchelf --print-rpath "$elf")
    ${pkgs.patchelf}/bin/patchelf --force-rpath \
      --set-rpath "$rpath:${pkgs.lib.getLib pkgs.pcre2}/lib:${homeDirectory}/.local/state/hp-os/native-pam/current" "$elf"
    mkdir -p "$out/share/dms-native-pam"
    ln -s ${nativeBase}/share/hp-os-native-pam/binary "$out/share/dms-native-pam/binary"
    ln -s ${nativeBase}/share/hp-os-native-pam/pcre "$out/share/dms-native-pam/pcre"
    # The production wrapper prepends -c before argv[1]. Dux recognizes its
    # internal qs entry point only at argv[1]. Preserve the identical Qt
    # environment and executable while letting the probe select its QML path.
    cp "$out/bin/dms" "$out/bin/dms-pam-probe"
    substituteInPlace "$out/bin/dms-pam-probe" \
      --replace-fail " -c $out/share/quickshell/dms" ""
    ln -s "$out/bin/dms-pam-probe" "$out/share/dms-native-pam/runner"
  '';
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    go test ./internal/server/brightness
    runHook postCheck
  '';
});

in dms
