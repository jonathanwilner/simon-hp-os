# Shared HP-OS desktop configuration

This public flake is the source of truth for common desktop packages and settings. Goran, Simon and NixOS HP-OS desktops consume `homeModules.fleetApps`. Add future common features here, then update the `desktop-fleet` lock in consuming flakes. Do not add a Goran-only copy of a common feature.

The module uses the consuming host package set. Linux ARM64 and x86-64 receive native Electron and the native Vulkan Upscayl engine. Simon remains `aarch64-linux`; his Ubuntu kernel, NVIDIA driver, user name and hardware settings remain in his host profile. Machine credentials and personal services never belong in this public module.

Current common features: Upscayl and the original wallpaper collection. Existing desktop features retain their existing modules until their host assumptions are separated. The module does not change the selected wallpaper.

Consumers add `inputs.desktop-fleet.url = "github:jonathanwilner/simon-hp-os"` and import `desktop-fleet.homeModules.fleetApps`. Run `nix flake update desktop-fleet`, review the lock change, build, and activate through the host deployment procedure. A lock update alone does not activate a configuration.

Simon can merge public main with `bash goran/installer/update-desktop.sh`. His configuration directly imports this same module, so the updater and installer receive the same shared features. Local customizations are retained by the updater recovery and merge workflow. Feature overrides are available under `programs.hp-os-fleet`: `enable`, `upscayl.enable`, and `wallpapers.enable`.

Upscayl updates are managed by Home Manager. On Ubuntu with AppArmor, activation installs a policy for the exact pinned Electron executable using passwordless sudo. This allows its user-namespace sandbox without disabling the sandbox. Linux hosts without that Ubuntu AppArmor tool path skip this activation step.

## Application launcher baseline

`launcher-apps.nix` installs Goran's portable terminal, media, audio, network,
scanner, remote desktop, recording and editor applications in every consuming
Home Manager account. Ghostty, Alacritty, Foot and fuzzel use each host's native
package set on ARM64 and x86-64. Package desktop entries provide executable
paths and icons to both fuzzel and the HP-OS app launcher. New accounts receive
Goran's light fuzzel appearance and Ghostty as the terminal for console apps.
Existing fuzzel settings and the theme service's writable file remain intact.

This baseline excludes Goran's Ubuntu and NVIDIA control panels, Googlebook VM
application bridges, installed Steam game shortcuts, personal proxy launchers,
and private service tools. Those entries require their corresponding runtime
or host configuration. Microsoft 365, search, Steam, Sunshine, COSMIC files,
BlueBubbles and other service integrations continue through their own modules.
The baseline installs applications without starting or restarting them.
