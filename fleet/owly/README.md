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

The **Omdrop AirDrop** launcher opens a standalone Quickshell window in HP-OS
and other Linux desktops. Existing Owly launcher IDs open the same window.
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
