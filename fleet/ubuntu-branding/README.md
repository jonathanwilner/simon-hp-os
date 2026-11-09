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

## Motion and typography

The boot and login sequence reveals the original circular HP logo, carries its
circle into the actual HP Forma O of HP-OS once. The login screen holds this
wordmark while the user signs in. Only successful authentication starts the
transition into the modern four-slash logo and starfield. Blue-white glow connects the phases. HP Forma Medium shapes the
wordmark and headings; Regular keeps controls clear. Eased position, opacity,
glow and star velocity preserve continuity. Login animation never controls
authentication or adds a fixed delay before the desktop starts. The native
sequence keeps the O in place while it fades into the final slash logo after
authentication. The concept video shows password entry and sign-in with a
clearly labelled simulated authentication sequence.

HP Forma is supplied privately from
`/usr/local/share/fonts/hp/HPFormaDJROffice-Regular.ttf`, or an explicit
`HP_OS_FORMA_FONT` path passed to the installer. The matching Medium face is
loaded alongside Regular when available. Public source includes the
approved rendered HP logo, without redistributing the font binary.

The shared `hp-os-motion-design` skill is installed under `.codex/skills` and
`.agents/skills`; DeepSeek Harness discovers the latter through its filesystem
skill provider. Its source and asset-generation prompt live in
`skills/hp-os-motion-design`. Agent session data remains separate.

Set `reducedMotion=true` in
`/usr/share/sddm/themes/hp-os/theme.conf` to show the login form immediately
without movement. Theme installation currently resets this setting to false.
The normal entrance is bounded and the star redraw timer stops at idle.

A historical alternative made with Open Design's motion-design skill is in
`concepts/open-design-arrival`. Its browser controls simulate login. The native
SDDM theme retains real authentication and system controls.
