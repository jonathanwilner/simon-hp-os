{ pkgs }:
let
  inherit (pkgs) lib stdenv;
  inherit (stdenv.hostPlatform) isAarch64 isDarwin isLinux;
  commandLink =
    name: target:
    pkgs.runCommand name { meta.mainProgram = name; } ''
      test -x "${target}"
      mkdir -p "$out/bin"
      ln -s "${target}" "$out/bin/${name}"
    '';

  # Apktool's Linux jar carries an x86-64 AAPT2. On Linux, use the Nix-managed
  # compiler through Apktool's existing PATH fallback.
  aapt =
    if isAarch64 && isLinux then
      pkgs.stdenvNoCC.mkDerivation {
        pname = "aapt2";
        version = "35.0.105";
        src = pkgs.fetchurl {
          url = "https://github.com/SuperJMN/DotnetAndroidArm64Shims/releases/download/35.0.105/shims-linux-arm64-35.0.105.tar.gz";
          hash = "sha256-u1hnQ/dsvU5x5ZfU4XoMBQSZt1u9bND2l+wixvjkqyg=";
        };
        sourceRoot = ".";
        installPhase = ''
          runHook preInstall
          install -Dm755 aapt2 "$out/bin/aapt2"
          runHook postInstall
        '';
        dontStrip = true;
        meta = {
          mainProgram = "aapt2";
          platforms = [ "aarch64-linux" ];
          license = lib.licenses.asl20;
          sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
        };
      }
    else
      pkgs.aapt;

  apktool = (pkgs.apktool.override { inherit aapt; }).overrideAttrs (
    old:
    {
      passthru = (old.passthru or { }) // {
        inherit aapt;
      };
    }
    // lib.optionalAttrs isLinux {
      nativeBuildInputs = old.nativeBuildInputs ++ [ pkgs.zip ];
      installPhase = old.installPhase + ''
        zip -qd "$out/libexec/apktool/apktool.jar" prebuilt/linux/aapt2
      '';
    }
  );

  # The public archive lacks ARM64 decompilers. Nixpkgs builds Ghidra
  # and its native components from source for both ARM64 targets.
  ghidra = if isAarch64 then pkgs.ghidra else pkgs.ghidra-bin;
in
{
  inherit (pkgs)
    asar
    binwalk
    go
    jadx
    ;
  inherit apktool ghidra;
  nm = commandLink "nm" "${
    lib.getBin (if isDarwin then pkgs.cctools else pkgs.binutils-unwrapped)
  }/bin/nm";
  otool = commandLink "otool" (
    if isDarwin then
      "${lib.getBin pkgs.cctools}/bin/otool"
    else
      "${lib.getBin pkgs.llvmPackages.llvm}/bin/llvm-otool"
  );
  sqlite3 = lib.getBin pkgs.sqlite;
  tshark = lib.getBin pkgs.wireshark-cli;
}
