# Owly AirDrop

Owly is the current name of `t4t5/omdrop-owl`. The fleet pins its upstream
source in `flake.lock` and builds its Rust CLI and system daemon with each
consumer's Nixpkgs. ARM64 and x86-64 packages use the same source.

Home Manager imports `desktop-fleet.homeModules.fleetApps` as usual. It installs
`owly` and AirDrop Radio, Receive with AirDrop, and AirDrop Status desktop entries.
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

Start **AirDrop Radio**, then **Receive with AirDrop**. Received files go to
Downloads. The radio lease ends when its terminal closes. To send, run
`owly browse`, then `owly send --to "Device Name" /path/to/file` in another
terminal. On the Apple device, enable AirDrop Everyone for 10 minutes.

Radio compatibility depends on the Wi-Fi card and channel. `owly doctor`
reports support. Shared mode can retain Wi-Fi on supported channels; exclusive
mode disconnects Wi-Fi until the radio stops. Do not enable exclusive mode over
a sole Wi-Fi remote connection. A successful build or doctor output does not
prove an over-the-air file transfer.
