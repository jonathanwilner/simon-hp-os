# Native Chrome channels

The shared overlay `overlays.chromeChannels` pins Google's native DEBs for
x86_64 Linux and ARM64 Linux. `google-chrome` and `google-chrome-stable` select
Stable; `google-chrome-beta`, `google-chrome-dev` (alias `google-chrome-unstable`)
and `google-chrome-canary` expose isolated launchers. The flake exports each
channel package for both architectures.

Import `homeModules.chromeChannels` (also included in `fleetApps`), apply the
overlay to the consuming package set and enable
`programs.hp-os-fleet.chromeChannels.enable = true`. The module installs the
three prerelease channels and `~/.local/bin/google-chrome-{beta,dev,canary}`.
Their desktop entries have no default-browser MIME registrations.
Stable keeps its existing profile, host overrides and automation launchers.
Ubuntu hosts can set `programs.hp-os-fleet.chromeChannels.extraArgs` to
`[ "--disable-setuid-sandbox" ]` when required by their sandbox integration.

Prerelease profiles live under `$XDG_CONFIG_HOME/google-chrome-{beta,dev,canary}`
(or `~/.config`). Their launchers reject profile-path overrides and remote
debugging switches, clear inherited automation variables, and accept
`--profile-directory` within the channel's profile. Stable owns automation.
The exposed packages omit vendor desktop entries that could bypass these rules.

Run `nix run .#update-chrome-channels` from this checkout to refresh all eight
pinned artifacts from Google's official `Packages.gz` indexes. Review the diff,
build the channel packages through the host's monitored build workflow and
publish before updating consumer locks. The updater changes only `sources.json`.

Validation:

```sh
python3 fleet/chrome-channels/test_channels.py
nix eval --impure --json --file fleet/chrome-channels/test-module.nix
```

Channel availability and package integrity follow Google's official Linux APT
repository at `https://dl.google.com/linux/chrome/deb/`.
