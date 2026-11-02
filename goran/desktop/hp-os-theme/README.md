# HP-OS DMS + Niri theme

> **Font notice:** This theme software uses and bundles unmodified HarmonyOS Sans Fonts. The fonts are governed by the bundled [`LICENSE_Fonts`](./LICENSE_Fonts), are not open-source software, and must not be redistributed as a standalone font package.

This flake packages a HP-OS desktop theme for DankMaterialShell (DMS) on Niri. It contains:

- a dual light/dark DMS palette derived from OpenHarmony 7 system-resource tokens;
- unmodified HarmonyOS Sans variable fonts, verified against their upstream SHA-256 hashes at build time;
- a NixOS module that installs the combined theme/font package and makes HarmonyOS Sans the preferred sans-serif family;
- a Home Manager module that installs the DMS theme, applies HP-OS typography/spacing/radii, and creates a one-time settings backup;
- host integration that follows DMS light/dark changes in GTK 3/4, Fuzzel, SwayNC, Alacritty, Ghostty, and Emacs PGTK without forcing `GTK_THEME`;
- `hp-os-theme-apply` and `hp-os-theme-restore` commands for reversible runtime changes.

The visual language uses the desktop/tablet-appropriate HP-OS conventions: a 16 px dialog/window radius, a 2/4/8/12/16/24 spacing scale, 12/14/16/20 core UI type sizes, restrained neutral surfaces, and blue focus/brand accents. It is an interoperability theme, not a Huawei product or an assertion of pixel-for-pixel identity.

HarmonyOS Sans is used for proportional interface text. Fixed-width DMS
surfaces and terminal emulators use Fira Mono, with Noto Sans Mono as the
generic fallback. Ghostty selects dedicated HP-OS light/dark palettes;
Alacritty imports a mode-specific palette selected by the DMS theme-sync
service and reloads it without recreating the terminal window.

## Use from another flake

```nix
inputs.hp-os-dms-theme = {
  url = "path:./flakes/hp-os-dms-theme";
  inputs.nixpkgs.follows = "nixpkgs";
};

# In the target NixOS module list:
hp-os-dms-theme.nixosModules.default

# In the host configuration:
jw.hposDmsTheme = {
  enable = true;
  user = "simon";
};
```

The NixOS module imports and enables the matching Home Manager module for the selected user. It expects the system to have Home Manager's NixOS module available.

## Apply and restore

Home Manager activation applies the theme after the existing `dmsSettingsInit` activation step. Before the first change it saves:

```text
~/.local/state/nixos-intc/hp-os-dms-theme/settings.pre-hp-os.json
~/.local/state/nixos-intc/hp-os-dms-theme/fontconfig.pre-hp-os.conf
```

Manual commands:

```bash
hp-os-theme-apply
hp-os-theme-restore
```

The restore command saves the current settings with a timestamp before restoring the original snapshot. It also restores the previous generic-font rule and Niri geometry. It does not restart DMS, so it is safe to run while the desktop is locked or while a remote session is fragile. Restart the DMS user service from an unlocked session to make the restored palette and in-process shell typography take effect immediately.

The host's DMS theme-sync service owns the writable runtime integrations. It
uses the active DMS font/palette for GTK 3/4 settings and generated CSS, a
high-contrast Fuzzel selection/focus treatment, and a generated Emacs Lisp
theme. Restoring the pre-HP-OS DMS settings and rerunning theme sync therefore
returns these integrations to the restored DMS font and colors as well.

NixOS generations remain the system-level fallback. A normal boot-generation rollback removes the font preference/package, while `hp-os-theme-restore` restores the pre-theme writable DMS settings.

## Source and licensing

The fonts and font agreement come unmodified from:

```text
OpenHarmony 7.0 release
base/global/system_resources
commit a6056518ce24773ef06aa5d16113f3bd3d8d966b
```

The agreement's SHA-256 is `327e0147d4a3ca2d89e81abce45b210576b0f9fe2b29d900f64b58039f12a102`. The package is marked `unfreeRedistributable`; see [`LICENSE_Fonts`](./LICENSE_Fonts) for the controlling terms. Font hashes are in [`font-hashes.sha256`](./font-hashes.sha256).

The palette and token documentation are adaptations of Apache-2.0 OpenHarmony system resources. No OpenHarmony source code is copied into the theme JSON. Noto Color Emoji and DMS's Material Symbols are retained instead of bundling the separately marked HMOS emoji/symbol assets.
