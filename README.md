# Simon HP-OS desktop

A reproducible HP-OS desktop for Simon's Ubuntu 26.04 ARM64 N1X machine.
Ubuntu manages the kernel, NVIDIA driver and system services. Home Manager
manages the desktop and applications under `/home/simon`.

Based on iNiR by snowarch (https://github.com/snowarch/inir).
This is a modified downstream integration, with its own HP-OS configuration.

## Install the desktop update

For the touch update, local merges and native flake integration, use the
[Simon touch update guide](goran/installer/SIMON-TOUCH-UPDATE.md).

Use the existing Simon Ubuntu installation with NVIDIA driver **615.78.08**,
Nix, Git, Python and tmux. Run these commands as `simon`, without sudo:

Download the updater and its instructions from **https://files.thewilners.com/s/hp-os**.
Extract the ZIP, open a terminal in the extracted `simon-hp-os-updater` folder,
and run `bash update-hp-os.sh --attach`.

See the [step-by-step guide](goran/installer/SIMON-QUICK-START.md) for preserving
local changes, conflict recovery and verification.

Alternatively, download and run the single updater tool directly:

```sh
curl --fail --location --output /tmp/update-hp-os.sh \
  https://raw.githubusercontent.com/jonathanwilner/simon-hp-os/main/update-hp-os.sh
bash /tmp/update-hp-os.sh --attach
```

The tool creates `~/src/simon-hp-os` from public HTTPS source. It detects an old
`~/src/nixos-amd` checkout only when that repository contains Simon's profile.
Local configuration changes are migrated before updating. The old checkout
remains unchanged. Conflicts or an unknown baseline stop the update for review.
For another old checkout, use `--from /path/to/old-checkout`. If needed, specify
its known clean baseline with `--legacy-base COMMIT`. `--build-only` builds the
candidate without activation; `--no-attach` leaves the tracked task running in
tmux. Use `--checkout PATH` to select the public checkout location.


No private GitHub membership, SSH deploy key or Tailscale connection is needed
to fetch this configuration. Subsequent updates use **Update Applications**
in the launcher or `simon-desktop-update`. Save work and log out after activation
to load the new compositor. The updater retains the preceding generation.

[Update and rollback guide](goran/installer/DESKTOP-UPDATE.md) ·
[Office and Relay enrollment](goran/installer/SIMON-APPS.md) ·
[Sunshine, SSH and Tailscale setup](goran/remote-access/README.md)

This is a desktop update, not a disk installer. Keep the supported Ubuntu driver
and native PAM prerequisites from the original Simon installation.

## Included features

- HP-OS shell, touchscreen gestures and long press, with laptop on-screen keyboard off.
- Sunrise/sunset appearance, matching COSMIC Files with network-share support,
  notification history, working volume steps, and Emacs theme switching.
- Ghostty 1.4 with the N1X presentation fix, seven ArtCraft apps, Microsoft 365
  web launchers and document handlers, BlueBubbles and optional Relay clipboard.
- Central desktop and user Flatpak updates, status display and rollback records.
- Separate taskbar Search and Application Center. Search opens with Super+S.
  See the [search guide](vendor/HP-OSShell/docs/SEARCH.md) for supported providers.

Office, BlueBubbles, Relay and browser accounts remain the user's own. Office
local-file uploads and Relay require the enrollment documented above. Appearance
uses Los Angeles coordinates by default; maintain other coordinates through
`programs.goran-hp-os.appearanceSchedule.latitude` and `.longitude` in the profile.
The unaccepted experimental dock-overflow change is excluded.

## Reproducible source

The root output is `homeConfigurations.simon-daytona`. The lock file retains the
reviewed package versions. Pull `main` for reviewed updates; a general
`nix flake update` can advance dependencies beyond those reviewed together.

The required HP-OS and Codex packaging source is included under `vendor/`, so
there are no private flake inputs. Upstream applications and source archives
are downloaded from public URLs with fixed revisions and hashes. The original
wallpaper and assistant artwork are fetched from their public origins during
the build, retaining their appearance and their original terms.

Source baseline: desktop `d99a43054275852153058924062968ac94cbc984`,
HP-OS `83edb4a19eb36a51f06ea608746d93eaf91ec4b9`, Codex packaging
`e0bd2fb82fc5f6f6f24b962df729874d9486bcd0`.

Build without activation on ARM64:

```sh
bash goran/installer/update-desktop.sh --build-only
```

## Notices

HP-OS code retains its GNU GPLv3 license, original authorship and
[NOTICE](vendor/HP-OSShell/NOTICE). Third-party applications, icons and artwork retain
their own licenses and notices. This independent Linux desktop is not a Huawei product.

**HarmonyOS Sans is bundled unmodified.** Its font files, license and required
notice are retained in `goran/desktop/hp-os-theme/`. See
[LICENSE_Fonts](goran/desktop/hp-os-theme/LICENSE_Fonts).

**Ask IQ** expands local file searches with the small Qwen3.5-0.8B model on
the CPU. Search retains the original query alongside suggested keywords.
The service runs locally at login with a 2 GB memory limit and two CPU threads.
See [Ask IQ service](pkgs/hp-os-search-iq/README.md).

## Included wallpapers

The desktop profile installs 17 original HarmonyOS 7 emulator wallpapers in
`~/Pictures/Wallpapers/HP-OS`. Select that folder in the wallpaper picker.
`harmonyos7-default.png` is 3000 × 2000; the other 16 images are 2160 × 1440.
The update preserves your selected wallpaper. Original bytes and SHA-256
checksums are recorded in `goran/desktop/wallpapers/SOURCE.json`.

Get the collection with the usual update command:

```sh
cd ~/src/simon-hp-os
bash goran/installer/update-desktop.sh
```
