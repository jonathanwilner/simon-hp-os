# Fleet debugging tools

This flake supports x86-64 Linux, ARM64 Linux, and Apple Silicon macOS. It keeps its own Nixpkgs lock so a fleet can use the same tools even when its hosts pin different Nixpkgs revisions.

| Commands | Linux | macOS |
| --- | --- | --- |
| `asar`, `go version -m`, `jadx`, `jadx-gui`, `apktool`, `tshark`, `binwalk`, `sqlite3` | Nix packages for the host | Nix packages for the host |
| `otool` | LLVM's Mach-O reader | Apple cctools |
| `nm` | GNU Binutils | Apple cctools |
| `ghidra`, `ghidra-analyzeHeadless` | Ghidra release on x86-64 and the Nixpkgs source build on ARM64 | Nixpkgs source build with Apple Silicon native components |

On ARM64 Linux, Apktool rebuilds Android resources with a pinned, native [AAPT2 build](https://github.com/SuperJMN/DotnetAndroidArm64Shims/releases/tag/35.0.105). Its official JAR bundles an x86-64 Linux resource compiler. This flake replaces the bundled Linux binary with a launcher for the Nix-managed compiler. Apktool on macOS uses its bundled universal resource compiler.

## Add it to a fleet

Add this input to the consumer flake. For an immutable reference, replace `feat/fleet-debug-tools` with the commit you want to pin.

```nix
inputs.debug-tools.url = "github:jonathanwilner/simon-hp-os/feat/fleet-debug-tools?dir=flakes/debug-tools";
```

Add `inputs.debug-tools.homeModules.default` to the Home Manager configuration's modules. In an existing Home Manager module that receives `inputs` as an argument, use this form.

```nix
{ inputs, ... }:
{
  imports = [ inputs.debug-tools.homeModules.default ];
  programs.fleet-debug-tools.enable = true;
}
```

For a system-wide NixOS installation, import `inputs.debug-tools.nixosModules.default` in the NixOS module list and set the same option. Both modules support `programs.fleet-debug-tools.exclude = [ "ghidra" ];` for hosts with their own Ghidra installation. Existing packages take precedence if they expose the same commands.

## Try it without changing a profile

```sh
nix shell 'github:jonathanwilner/simon-hp-os/feat/fleet-debug-tools?dir=flakes/debug-tools'
```

From this directory in a checkout, use `nix shell path:.` for the full bundle or `nix shell path:.#jadx` for an individual package. For the package smoke test, run `nix flake check path:.` on each supported system. The check uses local fixtures for an ASAR archive, Go binaries, an APK rebuild, a packet capture, a SQLite query, and Ghidra decompilation. Live packet capture uses the host's existing capture permissions.
