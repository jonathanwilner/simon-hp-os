# Ubuntu Snapdragon desktop

`homeModules.ubuntuSnapdragon` provides native ARM64 HP-OS and Niri with Dank
Material Shell (DMS), using the same fleet application module. Ubuntu retains
its kernel, device tree, firmware, NetworkManager, PipeWire and login manager.
Home Manager supplies Mesa userspace through `targets.genericLinux.gpu`.
The terminal uses the pinned upstream Ghostty without Goran's N1X frame-import
workaround. Host keys and credentials stay in each host configuration.

Set `home.username`, `home.homeDirectory`, and `home.stateVersion` in the consumer.
`programs.hp-os-snapdragon.device` defaults to `generic`; the HP profile identifies
`hp-omnibook-ultra-14-kg0xxx`. Board firmware belongs in the Ubuntu support package,
so the generic profile does not install HP firmware on another Snapdragon model.

After Home Manager activation, run `non-nixos-gpu-setup` with sudo and install
login entries pointing to the user's `hp-os-session` and `snapdragon-dms-session`.
Keep Ubuntu's GNOME session available. Choose either new session at the next login.
A working Ubuntu DRM render node and board-specific kernel support are required.

Ubuntu login integration must also install `/etc/pam.d/hp-os-snapdragon` and
`/etc/pam.d/dankshell`. HP-OS selects the former through `HP_OS_PAM_SERVICE`;
DMS discovers the latter. Use `pam_unix.so` for password authentication and
`pam_exec.so` to run the packaged `hp-os-ubuntu-account-check` from a root-owned
path. That helper expects `/etc/pam.d/hp-os-snapdragon-account` to contain
`account include common-account`, preserving Ubuntu's account policy through
its native PAM library. Nix PAM cannot parse Ubuntu's `@include` syntax directly.
Keep `/run/wrappers/bin/unix_chkpwd` linked to Ubuntu's privileged
`/usr/sbin/unix_chkpwd` through a tmpfiles rule. Keep Ubuntu's existing login
PAM stack intact. The consumer's root integration owns these system files.

## Shared desktop parity

Both sessions consume `fleet/niri` and `fleet/session`. HP-OS keeps its own
lock, search and control-center actions. DMS keeps its launcher and lock actions.
Home Manager synchronizes bindings with validation and preserves intentional
user changes. The previous Snapdragon-only launcher include is migrated.

| Shortcut | Action |
| --- | --- |
| Super+D, Alt+D | Focused application launcher |
| Super+Return, Super+T | Terminal |
| Print, Super+Shift+4 | Select screenshot area, save PNG and copy |
| Ctrl+Print | Capture screen, save PNG and copy |
| Alt+Print | Capture focused window, save PNG and copy |
| Super+Alt+V | Clipboard history selection |
| Super+Shift+/ | Show shortcut overlay |
| Super+1 through 9 | Select workspace |
| Super+Ctrl+1 through 9 | Move column to workspace |
| Super+Alt+L | Lock the active shell |

The session supervisor starts clipboard persistence/history and a graphical
policy authorization agent inside the compositor's environment. HP-OS's private
D-Bus stays private. DMS enables monitoring, VPN, calendar, dynamic theme and
clipboard paste. Fcitx/Rime belongs to DMS; HP-OS retains its touch-keyboard seat.
The CPU-only Ask IQ search service listens on localhost with bounded resources.
Portable HP-OS fonts, palettes and Wallhaven assets are available; existing
terminal, MIME and DMS preferences are preserved.

The full comparison and host-specific exclusions are recorded in
[`../session/PARITY-AUDIT.md`](../session/PARITY-AUDIT.md). NVIDIA environment,
Goran panel calibration, pairing credentials and suspend policy stay host-owned.

## Small online installer and updater

The Ubuntu ISO needs only a launcher for `bootstrap.sh`. After booting the
installed system, run it from the new user's terminal:

```sh
bash bootstrap.sh --source-revision FULL_PUBLIC_COMMIT
```

The installer launcher pins that commit and downloads the script over HTTPS.
The bootstrap installs native prerequisites and official multi-user Nix when
needed, then fetches that same public revision. It generates a small private
Home Manager consumer containing the actual user, home directory and detected
board. There is no private repository, host key, or personal account dependency.
Desktop packages download on the installed system; they are not added to the ISO.

The build runs through `nom-tmux` with two jobs and two cores. Home Manager backs
up colliding configuration files, retains the previous generation and attempts
rollback on activation failure. Native integration adds HP-OS and DMS sessions,
Ubuntu-compatible lock authentication, GPU setup and Chrome sandbox support.
The current desktop and GNOME session remain available. System integration
backups live in `/var/lib/hp-os-snapdragon/`. A failure leaves the setup incomplete
and rerunning is supported. Setup requires Internet, free disk space and sudo.

Use **Update HP-OS Desktop** or `hp-os-snapdragon-update` after installation.
Updates default to the installed pinned revision. Select a newer reviewed commit
with `--source-revision COMMIT`, or use `--channel fleet-stable` after that channel
contains Snapdragon support. An incompatible channel fails without activating;
there is no automatic fallback to development `main`. `--build-only` builds the
candidate and skips Home Manager activation and native integration, but may
install build prerequisites. Bootstrap refuses a Casper live session and root.

The bootstrap installs the shared HP-OS Plymouth boot theme and rebuilds boot
initrds through tracked native integration. Existing boot images are backed up by
the shared branding installer. A custom initrd without matching installed kernel
modules is preserved and boot branding is explicitly deferred to that image's
owning rebuild workflow. GDM and its login screen stay selected. Changing to the
HP-OS SDDM login screen, enrolling accounts and installing optional hardware
services remain explicit actions. Already-selected HP-OS login branding refreshes
through the existing native integration.
