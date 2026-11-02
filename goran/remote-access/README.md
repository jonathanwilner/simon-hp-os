# Simon remote access

Simon uses the same **AlkaidLab Foundation Sunshine 2026.903.160345** host as the live Goran machine verified on 2 Nov 2026. The source is pinned to `8d1c7ece8394ba4d95e0f9fa6a7ac6524526f39e` with the same seven Linux patches and ARM64 NVIDIA library paths. This follows the requested Goran baseline. Upstream now has newer releases, primarily for Windows; this package does not claim to be the latest upstream release.

Upstream: https://github.com/AlkaidLab/foundation-sunshine

The desktop includes Sunshine, Moonlight Qt, OpenSSH client, FreeRDP, Mosh, Waypipe and Tailscale. Foundation Sunshine is the host. Moonlight is a client. No Goran pairing, password, SSH key, Tailscale identity or account data is included.

## Enable the Ubuntu services

1. Run the normal HP-OS desktop update and activate the new generation.
2. Open **Set Up Remote Access**. Enter Simon's sudo password in the tracked terminal. Alternatively run `hp-os-remote-access-setup` from a terminal.
3. Log out and back in if the setup added device groups. Open `https://localhost:47990`, create Simon's own Sunshine credentials, and pair the Moonlight client.

The setup installs and enables Ubuntu's OpenSSH server, installs the capability-enabled Sunshine executable outside the immutable Nix store, enables GPU/input access, and starts Sunshine. It enables a Tailscale daemon but never logs in, joins a tailnet, or supplies an auth key. A fresh machine remains unenrolled. Existing Tailscale installations and connection state are preserved.

The setup preserves existing SSH configuration and host keys, Sunshine configuration and pairing, and Tailscale state. Missing Sunshine defaults are created once. Running setup after future desktop updates refreshes the executable and its garbage-collection root. It does not change the NVIDIA driver, create passwords, change firewall rules, or open router ports. If a firewall is enabled, allow only the access you intend: SSH TCP 22 and the Sunshine ports documented by upstream. Tailscale enrollment remains a separate user decision.

Check with `systemctl status ssh tailscaled`, `systemctl --user status sunshine`, `tailscale status`, and `/usr/local/libexec/hp-os-sunshine --version`. Sunshine service readiness does not establish successful video encoding or Moonlight pairing. Verify those on Simon's physical machine.

The required root changes are separate from Home Manager because Simon runs Ubuntu. The public repository is a desktop updater, not a replacement boot image. Building this profile on Goran does not activate Simon or change Goran's running Sunshine.
