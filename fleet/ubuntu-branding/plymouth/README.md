# HP-OS Ubuntu boot splash

The theme uses Ubuntu's installed `two-step` Plymouth plugin and spinner assets.
Its password dialog, update progress and keyboard layout controls remain provided
by Plymouth. The HP-OS wordmark replaces the Ubuntu watermark, and firmware
background display is disabled. Colors match the HP-OS wallpaper palette in
`vendor/HP-OSShell/overlay/assets/hpos-wallpaper.svg`.

The committed wordmark is deterministic typography, generated with:

```sh
magick -background none -fill '#f9fcff' -font DejaVu-Sans -pointsize 64 \
  label:HP-OS -bordercolor none -border 12 watermark.png
```

Run `install-boot.sh install` as root through `nom-tmux`. Install `plymouth` and
`plymouth-theme-spinner` first. Ubuntu's `update-alternatives` and an explicit
`Theme=hp-os` in `plymouthd.conf` select the splash. `restore` restores the first
saved configuration and theme. Backups live in `/var/lib/hp-os-branding/boot`.
The helper never starts Plymouth on the running desktop or reboots the host.

Custom initrds require their original build workflow. The helper refuses to
rebuild an initrd whose suffix is not an installed kernel. Use `--no-rebuild`
only when the caller will rebuild both ordinary and custom initrds. In
particular, the OmniBook USB-retention initrd needs its exact temporary module
override and `dracut --nostrip`; a normal rebuild loses that fix. Preserve the
original rollback records, then refresh the experiment's baseline and artifact
hashes after the coordinated rebuild. The generic branding helper intentionally
does not modify experiment records.

Verify the selected theme and its watermark are embedded in each initrd with
`lsinitrd`. A physical boot is still required to verify display rendering.
