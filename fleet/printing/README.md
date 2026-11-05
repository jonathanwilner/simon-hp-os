# Wi-Fi Aware printing

The shared fleet installs `hp-os-aware-print` and the **Wi-Fi Aware Printing**
native panel. Open **Control Center → Nearby printing** to discover a printer,
choose a document, and print within HP-OS. The card uses the control center’s
theme and spacing. Connection settings stay collapsed until needed.
The app launcher and the AirDrop panel’s **Printers** button open the same
control-center page when HP-OS is running, with a standalone panel as fallback.
Simon receives both through **Update Applications**, which merges
published `main` and activates `homeConfigurations.simon-daytona`.

The client discovers the `_ipp._tcp` service through Wi-Fi Aware Generic Service
Protocol (GSP), establishes a NAN data path, submits an IPP print job, and polls
that job's state. A printer must implement this service profile. Ordinary
Wi-Fi Direct and AirPrint printers do not automatically implement Wi-Fi Aware.

## Radio setup

Use a dedicated spare adapter with kernel, firmware and driver support for NAN
and NAN data interfaces. The setup refuses a radio with an associated interface,
IP addresses, or routes.
It does not replace NetworkManager's supplicant or change the host uplink.
The separate pinned hostap build includes NAN, NAN USD and PASN support.

On Ubuntu, including Simon and Goran:

```sh
sudo hp-os-aware-install-system wlan1  # replace wlan1 with the spare adapter
# Log out and back in for the aware-print group membership.
sudo systemctl start hp-os-aware-print-radio
hp-os-aware-print doctor
hp-os-aware-print discover
```

On NixOS, import `desktop-fleet.nixosModules.aware-printing` and configure:

```nix
services.hp-os-aware-print = {
  enable = true;
  interface = "wlan1"; # dedicated spare adapter
  users = [ "your-user" ];
};
```

Activate the host using its documented deployment path. The radio service stays
off until explicitly started. Stop it with
`sudo systemctl stop hp-os-aware-print-radio`.

The service owns `hposnan0` and `hposndi0`. Its control sockets are under
`/run/hp-os-aware-print/wpa`. Do not run it against the primary Wi-Fi adapter.
Firmware and kernel upgrades remain host-specific changes.

## Print

Use the peer address reported by discovery:

```sh
hp-os-aware-print print --peer 02:11:22:33:44:55 --file document.pdf \
  --passphrase-file "$HOME/.config/printer-passphrase"
```

Keep the passphrase file private. The printer and client must use the same
passphrase. Open sessions require the explicit `--allow-open` option. The
client terminates the data path and discovery subscription after the attempt.
It checks printer format support before submission and returns the printer's
job state. Check the physical output separately.

## Verification boundary

Automated tests cover GSP parsing, endpoint scope, control-socket events, IPP
submission and job-state polling against a local test server, and cleanup on
failures. They do not prove wireless interoperability or physical printed
output. The launcher reports the installed radio's actual availability.
A capable printer and adapter are required for the physical acceptance test.

The updater refreshes an existing Ubuntu radio service's package reference.
It does not start or restart a radio session. A running service uses its current
binary until the user stops and starts it.

## Sources

- [Pinned upstream hostap source](https://git.w1.fi/hostap.git/commit/?id=2ea78bb9af5f27250f97eda04d429d87bd88705f)
- [Espressif Wi-Fi Aware component and GSP profile](https://github.com/espressif/esp-wifi-apps/tree/master/components/wifi_aware)
