# Artcraft fleet updates

`artcraft-catalog` reports the latest stable release for selected applications and
new official applications from the upstream launcher catalog. A daily user timer
saves the report in `~/.local/state/artcraft/catalog.txt` and notifies when it
changes. This checker downloads metadata only. Network or catalog errors keep the
previous report intact.

Fleet installations use checksummed release pins, native ARM64 or x86-64 tarballs,
and the machine's own graphics drivers. The updater already existed; it now keeps
selection in `versions.json` instead of a second hardcoded application list.

From a writable checkout:

```
python3 flakes/artcraft-suite/update.py --catalog
python3 flakes/artcraft-suite/update.py --report
python3 flakes/artcraft-suite/update.py --check
python3 flakes/artcraft-suite/update.py
python3 flakes/artcraft-suite/update.py --add figcraft --add wordcraft
```

The last command explicitly selects new apps. Discovery never adds applications.
An addition must supply the existing packaging contract: published SHA256SUMS,
native ARM64 and x86-64 tarballs, and a web ZIP. Missing assets stop the entire
update before pins are replaced. Review the diff, build both architectures,
publish the fleet commit, refresh consumer locks, then activate the selected hosts.
The checker does not bypass the fleet updater or install outside Nix.

The official catalog currently contains PhotoCraft, VectorCraft, FilmCraft,
LightCraft, PdfCraft, EffectCraft, DesignCraft, FigCraft, WordCraft, SoundCraft,
DeckCraft, CADCraft, GridCraft, TextureCraft, MaterialCraft and Craft Anything.
The launcher also lists community SolidCraft; community apps require a separate
packaging review and are excluded from automatic official discovery.

Sources: https://getartcraft.com/apps and
https://github.com/storytold/craft-launcher/blob/main/crates/core/src/catalog.rs
