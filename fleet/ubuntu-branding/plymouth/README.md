# HP-OS Ubuntu animated boot splash

The native Plymouth script reveals the approved HP electric-blue keyline logo
against near-black. Seventy-two cyan-white star sprites use precomputed
rotations and twelve size steps, with eased opacity and hidden depth resets.
Animation never holds boot completion, imposes a minimum duration, or invents
a completion percentage. Password/question input pauses motion. Plymouth
messages and real system-update progress retain callbacks.

`watermark.png` is an unchanged copy of the authorized brand-kit asset
`logo_HP_Electric_Blue_keyline.png`. Its aspect ratio, color and keyline stay
intact; the native script scales it once at startup to fit the display.
The same source is `sddm/hp-os/images/hp-logo.png`. Do not replace the logo with
typed letters or regenerate a logo from a font. HP authorized distribution of the unmodified HP Forma faces in the shared `fonts/` directory.

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
installed theme were untouched. The previous wordmark reveal/starflight recording and
password prompt were published to the private debug gallery. The revised logo theme needs its own native preview; a physical boot
is still required to verify firmware-to-splash handoff and display rendering.
