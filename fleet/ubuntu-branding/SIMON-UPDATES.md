# Simon's boot and login updates

Use the existing **Update Applications** launcher or `simon-desktop-update --attach`.
The normal path fetches the tested `fleet-stable` branch, preserves local changes,
builds the locked Home Manager generation, and activates that generation. The
source includes the updater itself, the flake lock, applications, shared Plymouth
assets, and SDDM login theme.

New updaters re-execute the merged release's updater within the same tracked task
and retain its lock and provenance record. An older immutable updater receives the
branding integration through the new generation's Home Manager activation hook
on its first update. The updater requests sudo within that same update when needed.
No separate branding command or second update is part of the successful path.

The shared refresh selects the existing HP-OS Wayland session, retains active
sessions, and validates the rebuilt current-kernel initrd before replacing it.
Driver and firmware files and resume support must survive. Recovery images remain
unchanged. A custom boot entry without `splash`, absent dependencies, or missing
licensed fonts produces a pending result in Update Status and the tracked log.
Retry **Update Applications** after host provisioning resolves the reported gap.

HP Forma Regular and Medium are licensed host assets. Provision them in
`/usr/local/share/fonts/hp/HPFormaDJROffice-{Regular,Medium}.ttf` on the original
host image. Updates copy these fonts into the theme and can recover them from an
existing HP-OS theme. They never publish font binaries in the public repository
or silently substitute another font.

The source bootstrap `bash update-hp-os.sh --attach` uses the same tested channel.
`main` becomes available to the default updater only after the trusted controller
passes exact-revision ARM, x86-64, NVIDIA, and fresh-launch canary gates and atomically
publishes `fleet-stable` plus an immutable `fleet-<revision>` rollback tag.
