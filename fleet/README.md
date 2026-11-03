# Shared HP-OS desktop configuration

This public flake is the source of truth for common desktop packages and settings. Goran, Simon and NixOS HP-OS desktops consume `homeModules.fleetApps`. Add future common features here, then update the `desktop-fleet` lock in consuming flakes. Do not add a Goran-only copy of a common feature.

The module uses the consuming host package set. Linux ARM64 and x86-64 receive native Electron and the native Vulkan Upscayl engine. Simon remains `aarch64-linux`; his Ubuntu kernel, NVIDIA driver, user name and hardware settings remain in his host profile. Machine credentials and personal services never belong in this public module.

Current common features: Upscayl and the original wallpaper collection. Existing desktop features retain their existing modules until their host assumptions are separated. The module does not change the selected wallpaper.

Consumers add `inputs.desktop-fleet.url = "github:jonathanwilner/simon-hp-os"` and import `desktop-fleet.homeModules.fleetApps`. Run `nix flake update desktop-fleet`, review the lock change, build, and activate through the host deployment procedure. A lock update alone does not activate a configuration.

Simon can merge public main with `bash goran/installer/update-desktop.sh`. His configuration directly imports this same module, so the updater and installer receive the same shared features. Local customizations are retained by the updater recovery and merge workflow. Feature overrides are available under `programs.hp-os-fleet`: `enable`, `upscayl.enable`, and `wallpapers.enable`.

Upscayl updates are managed by Home Manager. On Ubuntu with AppArmor, activation installs a policy for the exact pinned Electron executable using passwordless sudo. This allows its user-namespace sandbox without disabling the sandbox. Linux hosts without that Ubuntu AppArmor tool path skip this activation step.
