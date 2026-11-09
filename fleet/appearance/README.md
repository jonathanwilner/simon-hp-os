# Portable appearance

Import `fleet/appearance/home.nix`, enable
`programs.hp-os-fleet.appearance.enable`, and optionally supply `dmsPackage`.
The module supplies the same HarmonyOS Sans, Fira Mono, HP-OS theme assets,
terminal palettes, and Wallhaven plugin used by Simon and Goran. Noto CJK and
emoji fonts provide fallbacks. New terminal configs include copy/paste keys.
New accounts receive DMS typography, theme and battery notifications, plus
COSMIC Files and Celluloid file associations. Existing writable configuration
is preserved byte-for-byte. These defaults do not enable automatic suspend.

The module does not restart DMS or change an active desktop. Wallhaven launchers
require a running DMS session; HP-OS has its own wallpaper controls. Existing
DMS users can select the supplied HP-OS theme in Settings. Terminal users can
select the supplied `hp-os-light` or `hp-os-dark` palettes without losing edits.

Deliberate host boundaries:

- Goran's HDR calibration, NVIDIA paths, output names and touch quirks stay in
  its hardware modules.
- Goran's palette watcher is tied to `goran-niri.target`; it is not imported into
  HP-OS's private D-Bus session. Both shells keep their own appearance controls.
- Headphone applications already come from `fleet/launcher-packages.nix`.
  Goran's second imperative app profile is unnecessary; Bluetooth pairing and
  device credentials remain local.
- No forced GTK/Qt style, browser default, shell/editor preference, account,
  wallpaper download, or paired-device state is copied from another user.
