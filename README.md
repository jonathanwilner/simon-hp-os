# Simon HP-OS desktop

A reproducible HP-OS desktop for Simon's Ubuntu 26.04 ARM64 N1X machine.
Ubuntu manages the kernel, NVIDIA driver and system services. Home Manager
manages the desktop and applications under `/home/simon`.

Based on iNiR by snowarch (https://github.com/snowarch/inir).
This is a modified downstream integration, with its own HP-OS configuration.

## Install the desktop update

Use the existing Simon Ubuntu installation with NVIDIA driver **615.78.08**,
Nix, Git, Python and tmux. Run these commands as `simon`, without sudo:

```sh
mkdir -p ~/src
git clone https://github.com/jonathanwilner/simon-hp-os.git ~/src/simon-hp-os
cd ~/src/simon-hp-os
bash goran/installer/update-desktop.sh
```

No private GitHub membership, SSH deploy key or Tailscale connection is needed
to fetch this configuration. Subsequent updates use **Update Applications**
in the launcher or `simon-desktop-update`. Save work and log out after activation
to load the new compositor. The updater retains the preceding generation.

[Update and rollback guide](goran/installer/DESKTOP-UPDATE.md) ·
[Office and Relay enrollment](goran/installer/SIMON-APPS.md)

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
  See the [search guide](vendor/hp-os/docs/SEARCH.md) for supported providers.

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
[NOTICE](vendor/hp-os/NOTICE). Third-party applications, icons and artwork retain
their own licenses and notices. This independent Linux desktop is not a Huawei product.

**HarmonyOS Sans is bundled unmodified.** Its font files, license and required
notice are retained in `goran/desktop/harmonyos-theme/`. See
[LICENSE_Fonts](goran/desktop/harmonyos-theme/LICENSE_Fonts).
