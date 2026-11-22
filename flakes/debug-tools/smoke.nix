{
  runCommandCC,
  stdenv,
  tools,
  ghidra,
  aapt,
  unzip,
}:
let
  inherit (stdenv.hostPlatform) isAarch64 isDarwin;
  ghidraPlatform =
    if isDarwin then
      "mac_arm_64"
    else if isAarch64 then
      "linux_arm_64"
    else
      "linux_x86_64";
in
runCommandCC "fleet-debug-tools-smoke"
  {
    nativeBuildInputs = [
      tools
      aapt
      unzip
    ];
  }
  ''
    export PATH="${tools}/bin:$PATH"
    export HOME="$TMPDIR/home"
    mkdir -p "$HOME" payload
    printf 'fleet-debug-tools\n' > payload/check.txt
    asar pack payload payload.asar
    asar extract payload.asar unpacked
    cmp payload/check.txt unpacked/check.txt

    cat > main.go <<'GO'
    package main

    func main() {}
    GO
    export GOCACHE="$TMPDIR/go-cache" GOTOOLCHAIN=local CGO_ENABLED=0
    go build -o native main.go
    go version -m native | grep 'GOARCH'
    nm native | grep -m 1 'main.main' > symbols
    GOOS=darwin GOARCH=arm64 go build -o macho main.go
    otool -h macho | grep -i 'magic'

    jadx --version
    apktool --version
    mkdir -p res/values
    printf '%s\n' '<resources><string name="app_name">Fleet Debug Tools</string></resources>' > res/values/strings.xml
    printf '%s\n' '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.example.debugtools"><application /></manifest>' > AndroidManifest.xml
    aapt2 compile --dir res -o compiled.zip
    aapt2 link --manifest AndroidManifest.xml -o sample.apk compiled.zip
    apktool decode sample.apk -o decoded
    grep 'Fleet Debug Tools' decoded/res/values/strings.xml
    apktool build decoded -o rebuilt.apk
    unzip -t rebuilt.apk

    export XDG_CACHE_HOME="$HOME/.cache"
    printf '0000  01 02 03 04\n' > packet.txt
    text2pcap -q -u 1234,4321 packet.txt packet.pcapng
    test "$(tshark -r packet.pcapng -T fields -e udp.dstport)" = 4321
    binwalk --version
    test "$(sqlite3 :memory: 'select 6 * 7;')" = 42

    decompiler="${ghidra}/lib/ghidra/Ghidra/Features/Decompiler/os/${ghidraPlatform}/decompile"
    test -x "$decompiler"
    printf '%s\n' 'int main(void) { return 0; }' > tiny.c
    "$CC" tiny.c -o tiny
    cat > FleetSmoke.java <<'JAVA'
    import ghidra.app.decompiler.DecompInterface;
    import ghidra.app.script.GhidraScript;
    import ghidra.program.model.listing.Function;

    public class FleetSmoke extends GhidraScript {
        public void run() {
            var decompiler = new DecompInterface();
            try {
                if (!decompiler.openProgram(currentProgram)) {
                    throw new IllegalStateException(decompiler.getLastMessage());
                }
                for (Function function : currentProgram.getFunctionManager().getFunctions(true)) {
                    if (!function.isThunk()) {
                        var result = decompiler.decompileFunction(function, 30, monitor);
                        if (!result.decompileCompleted()) {
                            throw new IllegalStateException(result.getErrorMessage());
                        }
                        println("Fleet Ghidra decompilation passed");
                        return;
                    }
                }
                throw new IllegalStateException("No function was found in the fixture");
            } finally {
                decompiler.dispose();
            }
        }
    }
    JAVA
    mkdir projects
    export JAVA_TOOL_OPTIONS="-Duser.home=$HOME"
    ghidra-analyzeHeadless projects smoke -import tiny -scriptPath "$PWD" \
      -postScript FleetSmoke.java -deleteProject > ghidra.log 2>&1 &&
      grep 'Fleet Ghidra decompilation passed' ghidra.log || {
      cat ghidra.log
      exit 1
    }

    touch "$out"
  ''
