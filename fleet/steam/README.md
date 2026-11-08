# Steam on ARM64 fleet desktops

The shared fleet installs a native ARM64 Steam launcher and explicit Ubuntu
bootstrap command. Steam keeps its client, account, games, and updates under
`~/.local/share/Steam`. Home Manager activation never downloads Steam or FEX.
The default applies to ARM64; existing x86 Steam configuration stays in its
host modules. Disable with `programs.hp-os-fleet.steam.enable = false`.

After activating the fleet profile, run as the desktop user:

```sh
nom-tmux install-steam-arm64 -- hp-os-steam-bootstrap
hp-os-steam-gpu-check
steam
```

The bootstrap installs Ubuntu dependencies, scoped AppArmor sandbox permission,
the official native Steam public beta and ARM64 Runtime 4. Downloads validate
published hashes. Existing clients and runtime installations are preserved.
Use `--client-only` to omit FEX. FEX builds use pinned upstream commit
`14c92681f4d62cf84d901460e0358de09c8847a7` and a verified Ubuntu 24.04 x86 root
filesystem. Builds default to four jobs and are separate from Home Manager.
The local compatibility tool targets Linux x86 games. Windows games require
an ARM64 Proton tool; this module does not configure one or change per-game
settings. Sign-in and licensed games remain user-owned state.

GPU selection reads DRM device drivers and PCI vendor IDs. A Qualcomm-only
host prefers its installed ARM64 Freedreno Vulkan ICD. NVIDIA hosts retain
their installed host driver. Hybrid/unknown GPUs retain normal loader selection.
Explicit `VK_DRIVER_FILES` and `VK_ICD_FILENAMES` choices take precedence.
No NVIDIA driver package or NVIDIA environment override is applied generically.
Qualcomm bootstrap installs Ubuntu Mesa Vulkan/DRI packages; it does not replace
the kernel or install third-party GPU drivers. The native client and FEX tool
share this selection policy. Native GTK, audio, X11 and graphics libraries come
from Ubuntu, matching its driver stack.

`hp-os-steam-gpu-check` reports detected hardware, kernel page size, Vulkan
renderer, and OpenGL renderer when an X display is available. Verify a hardware
renderer before claiming graphics acceleration. A working Steam window does
not establish game compatibility. FEX graphics and actual games require
separate acceptance on each GPU family.

Consumers migrating from the private `goran/steam/home.nix` module must remove
that import to avoid competing launcher packages. Existing `~/.local/bin/steam`
may remain on PATH ahead of the profile; update that symlink to the shared
profile launcher during migration after verifying the client still starts.
Never copy Goran's Steam filesystem UUID or mount configuration to another host.

For automated provisioning, run `sudo hp-os-steam-prepare-system USER` first,
then run `hp-os-steam-bootstrap --user-only` as that desktop user under
`nom-tmux`. Both phases accept `--client-only`. This keeps authentication
outside the tracked user download/build process and avoids password files.
