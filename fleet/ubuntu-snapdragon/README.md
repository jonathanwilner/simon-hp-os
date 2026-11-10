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

## Install from a fresh Ubuntu account

Run `bootstrap.sh --source-revision FULL_COMMIT` as the installed desktop user.
Use the SHA-256-verified copy supplied by the OmniBook installer's first-login
launcher, or download the script from the same immutable public commit.
`--build-only` builds the generated profile without activating it.

The bootstrap generates account identity from the current login, builds the
public `homeModules.ubuntuSnapdragon` module, and installs additive Ubuntu login
entries with ordinary sudo prompts. It preserves GNOME, the active session,
the Ubuntu kernel and board firmware. Private SSH aliases and administrator
credentials are not required. It does not install passwordless sudo.

The build is tracked through `nom-tmux`. A failed activation attempts the prior
Home Manager generation. After successful setup, `hp-os-snapdragon-update`
reuses the pinned revision unless an explicit compatible revision is supplied.
Keep the working pin until a Snapdragon-compatible fleet-stable is validated.
