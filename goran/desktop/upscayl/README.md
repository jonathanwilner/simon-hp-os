# Upscayl on Ubuntu ARM64

Home Manager installs the `upscayl` command and desktop entry for Goran and Simon.
The package uses Upscayl 2.15.0's original JavaScript interface and models from
the checksum-pinned upstream release. Native Nix Electron and `upscayl-ncnn`
replace the release's x86-64 executables. No x86 emulation is used.

`ELECTRON_IS_DEV=0` selects the packaged interface and its adjacent `bin` and
`models` directories. The launcher disables Electron's setuid sandbox helper;
Ubuntu supplies user-namespace sandboxing. The Home Manager NVIDIA bridge at
`/run/opengl-driver/lib` supplies graphics libraries.

Upstream source and license: https://github.com/upscayl/upscayl/tree/v2.15.0
The GUI and native engine are AGPL-3.0 software. Update the pinned release hash
when changing the GUI version, and verify the engine's model/CLI compatibility.
