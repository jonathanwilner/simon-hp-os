# HP-OS branding on Ubuntu

The shared fleet provides `hp-os-install-branding`. It installs the HP-OS
Plymouth splash and SDDM greeter on Ubuntu ARM64 and x86-64. It does not install
GPU drivers or change desktop sessions or PAM authentication. Home Manager
only provides the command; an explicit root invocation selects the branding.

Install SDDM, Qt 6 QML, Xorg, fonts, Plymouth and the spinner theme using the
host package workflow. Preserve the current display manager during package
installation by preselecting it in debconf and temporarily blocking package
service starts. Run long package/image operations through `nom-tmux`.

```sh
sudo ~/.nix-profile/bin/hp-os-install-branding jonathan hp-os-snapdragon install
```

Arguments are user, existing Wayland session ID, `install` or `restore`, and an
optional `--login-only`, `--boot-only`, or `--no-rebuild`. Login selection takes
effect at the next boot and preserves the active desktop. GNOME and DMS remain
available. The greeter uses software Qt Quick rendering under Xorg, independently
of the desktop GPU. Initial login-manager state is saved under
`/var/lib/hp-os-ubuntu-branding/login`; boot state under
`/var/lib/hp-os-branding/boot`.

For custom initrds, use the host's coordinated rebuild workflow. `--no-rebuild`
only stages boot theme files and requires rebuilding every boot image before
reboot. The OmniBook USB-retention candidate requires its exact clock module;
a normal initramfs rebuild cannot preserve that experiment. See
[boot details](plymouth/README.md). Host installers may refresh the login theme
with `--login-only` while their dedicated boot workflow maintains initrds.

Test mode validates theme rendering only. Actual splash rendering and password
login require a physical boot/login test. Never restart the display manager
from an active desktop merely to preview the theme.
