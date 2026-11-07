# Owly AirDrop

Owly is the current name of `t4t5/omdrop-owl`. The fleet pins its upstream
source in `flake.lock` and builds its Rust CLI and system daemon with each
consumer's Nixpkgs. ARM64 and x86-64 packages use the same source.

Home Manager imports `desktop-fleet.homeModules.fleetApps` as usual. It installs
`owly`, the Omdrop backend, and the Omdrop AirDrop graphical launcher.
Existing Receive with AirDrop and AirDrop Status shortcuts open the same panel.
Disable with `programs.hp-os-fleet.owly.enable = false`.

NixOS hosts also import `desktop-fleet.nixosModules.owly`. This enables the
upstream D-Bus activated radio service, NetworkManager exclusions, Bluetooth,
polkit and the receive port on `awdl0`. Host radio settings belong in
`services.owly.settings`. The module does not start a radio lease at login.

On Ubuntu, open **Set Up AirDrop** once or run:

```
sudo ~/.nix-profile/bin/hp-os-owly-install-system
```

The helper installs root-owned links to the Nix package and a GC root. It uses
Ubuntu's NetworkManager tools and does not replace the kernel or Wi-Fi driver.
Simon's installer profile includes the same setup entry. The desktop updater
refreshes an already installed service when passwordless sudo is available;
otherwise it reports the explicit setup action. It never restarts a radio lease.
Host settings can be placed in `/etc/owly/radio.toml`.

Open **Omdrop AirDrop**, or open the HP-OS control center and select the
**Omdrop · AirDrop** tile. The round icon starts a 10-minute receive window;
the rest of the tile opens device and transfer details. The details panel
shows visibility, destination folder, nearby devices and transfer status.
Select a nearby device to choose files. On the Apple device, enable AirDrop
Everyone for 10 minutes.

Automatic Wi-Fi switching is enabled by default. Starting a receive window
temporarily selects a compatible access point on the same saved network. The
controller checks gateway and Tailscale connectivity, arms rollback before
roaming, and restores the original connection on stop, expiry, or failure.
Opening the panel alone does not change Wi-Fi. Hosts can opt out with
`programs.hp-os-fleet.owly.automaticWifiSwitching = false`.

Radio compatibility depends on the Wi-Fi card and channel. `owly doctor`
reports support. Shared mode can retain Wi-Fi on supported channels; exclusive
mode disconnects Wi-Fi until the radio stops. Do not enable exclusive mode over
a sole Wi-Fi remote connection. A successful build or doctor output does not
prove an over-the-air file transfer.

## Graphical Omdrop

The **Omdrop AirDrop** launcher opens the native HP-OS Control Center sharing
card. Other desktops use the standalone Quickshell window. An unavailable
shell IPC command falls back to that window, including commands that print
an error while returning exit status zero. Existing Owly launcher IDs use
the same launcher.
The same panel is installed as the optional `omdrop` widget under
`DankMaterialShell/plugins`; it does not change an existing bar layout.

The window uses the pinned Omdrop backend for receive windows, audience,
folder selection, discovery and file selection. Its radar derives from
netmojo-systems/omdrop-plugin and retains the upstream MIT license. The Wi-Fi
status comes directly from `owly doctor --json`. A blocked radio remains
visible in the window, with its reason, and the receive action is disabled
until the radio requirements are met. Opening the window never changes Wi-Fi.

The native control-center layout follows Huawei Share's icon-toggle and
details-card pattern. It uses HP-OS theme colors and displays the real radio
state. Design references: [Huawei control center](https://consumer.huawei.com/cn/support/content/zh-cn16046674/)
and [Huawei Share visibility](https://consumer.huawei.com/cn/support/content/zh-cn16093654/).


## Regression checks

GitHub Actions runs `Omdrop fleet regression` on native x86-64 and ARM64
runners for every push and pull request. Run the same checks locally with:

```sh
nom-tmux test-omdrop-fleet -- nix build \
  .#checks.x86_64-linux.omdrop-fleet-contract \
  .#checks.x86_64-linux.omdrop-package-contract --no-link
```

Use `aarch64-linux` on ARM64. The checks cover:

- Actual Home Manager default and explicit opt-out wiring on both architectures,
  plus the standalone GUI package's enabled controller.
- Rendered controller readiness, rollback before network changes, connection
  failures, expiry, restoration and bounded NetworkManager waits.
- The real launcher's integrated-shell success and fallback when IPC reports
  failure with either zero or nonzero exit status.
- The installed Omdrop wrapper removing an inherited Nix `SHELL`, preserving
  arguments and refusing upstream's mutable installer commands.

The tests use simulated radio responses and never change a runner's Wi-Fi.
Hardware validation remains separate: verify the receive window, original
connection restoration, visible Control Center contents and an actual file
transfer on each supported device. A passing automated check does not prove
radio performance or a successful Apple-device transfer.

## OM Drop user authorization and automatic receiving

The Ubuntu system installer adds the configured Home Manager user to `omdrop` and installs a root-owned Polkit rule. This group can invoke only `org.omarchy.omdrop.radio` and `io.github.t4t5.Owly.acquire` without authentication, including calls from user services without an active desktop seat. The existing action binds the radio helper to its immutable Nix store path. Other privilege requests retain their system policies.

Run `sudo ~/.nix-profile/bin/hp-os-owly-install-system` once on Ubuntu. Both the desktop updater and Goran's Home Manager deploy refresh installed system integration. NixOS uses `desktop-fleet.nixosModules.owly` and `services.omdrop.authorizedUsers = [ "your-user" ];`.

Set `programs.hp-os-fleet.owly.autostartReceiving = true;` in the host's Home Manager configuration for automatic receiving. The shared default is false. The managed `hp-os-omdrop-auto.service` starts with the user manager, starts an unlimited receive window, and retries failures every 60 seconds. It checks authorization without interaction before invoking the radio helper. The receiver still confirms incoming transfers through the existing application flow.

Explicit **Stop receiving** pauses automatic startup until a restart of this service. Manual enable resumes it. Stopping the user service stops receiving and restores a temporary Wi-Fi selection. Compatible same-network Wi-Fi selection and startup rollback remain managed by the controller; permanent saved network preferences are preserved.

Acceptance commands as the ordinary user:

```sh
pkcheck --action-id org.omarchy.omdrop.radio --process $$
pkcheck --action-id io.github.t4t5.Owly.acquire --process $$
systemctl --user is-active hp-os-omdrop-auto.service
omdrop doctor --json
omdrop status --json
omdrop peers --json
```

A successful service and peer scan establish radio startup and discovery. A file transfer requires a nearby sender and separate acceptance evidence. Flake check `omdrop-fleet-contract` tests authorization scope, both CPU architectures' configuration, lifecycle recovery, and explicit-stop behavior.

### Preferred Wi-Fi channels

Set `programs.hp-os-fleet.owly.preferredChannels = [ 149 ];` when a host receives Apple discovery traffic more reliably on channel 149. The default `[]` preserves the current compatible access point. With `automaticWifiSwitching` enabled, preferences are tried in order among access points on the same saved network with matching security. The strongest access point on the preferred channel wins; an already connected access point on that channel stays connected. Failed access points remain on cooldown. If preferred channels are unavailable, the controller retains a compatible current connection or selects the strongest compatible alternative. Stopping receiving restores the original connection. This option does not change router channels or use exclusive radio mode.
