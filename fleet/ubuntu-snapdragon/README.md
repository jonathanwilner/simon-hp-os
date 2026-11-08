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
