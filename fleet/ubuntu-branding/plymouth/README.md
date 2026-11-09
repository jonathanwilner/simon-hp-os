# HP-OS Ubuntu animated boot splash

The native Plymouth script reveals an HP Forma HP-OS wordmark and starts a
cyan-white starflight against near-black. Seventy-two sprites use precomputed
rotations and sizes. Animation never holds boot completion, imposes a minimum
duration, or invents a completion percentage. Password/question input pauses
motion. Plymouth messages and real system-update progress retain callbacks.

The committed wordmark is a raster asset rendered from the available licensed
HP Forma Bold font. The font binary is not distributed here. Regenerate with:

```sh
magick -background none -fill '#f5fbff' -font /path/to/hp-forma-bold.ttf \
  -pointsize 94 label:HP-OS -bordercolor none -border 8 watermark.png
```

Script APIs were checked against upstream Plymouth's native example and
`src/plugins/splash/script` implementation at commit
`b79b178641e41682204052036da6591896097473`:
https://gitlab.freedesktop.org/plymouth/plymouth/-/tree/main/src/plugins/splash/script

Run `install-boot.sh install` as root through `nom-tmux`. Ubuntu's alternatives
and explicit `Theme=hp-os` select the splash. `restore` restores the first saved
configuration and theme. Backups live in `/var/lib/hp-os-branding/boot`. The
helper never starts Plymouth on the running desktop or reboots the host.

Custom initrds require their original build workflow. The helper refuses to
rebuild an initrd whose suffix is not an installed kernel. Use `--no-rebuild`
only when the caller will rebuild both ordinary and custom initrds. The
OmniBook USB-retention initrd needs its exact temporary module override and
`dracut --nostrip`; a normal rebuild loses that fix. Use the private installer's
`kernel-fixes/rebuild-branded-initrds.sh` to preserve archives and refresh both
baseline and artifact manifests coherently.

Native preview passed on Ubuntu ARM64 Plymouth 24.004 using its X11 renderer
inside isolated mount/network/PID namespaces and Xvfb. The running desktop and
installed theme were untouched. A wordmark reveal/starflight recording and
password prompt were published to the private debug gallery. A physical boot
is still required to verify firmware-to-splash handoff and display rendering.
