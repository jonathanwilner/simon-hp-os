# Official Huawei typography

HP-OS uses HarmonyOS Sans Fonts. Fonts remain under Huawei's included license, separately from shell source code. The installer keeps fonts unchanged and retains the original license and notice. Font files are not committed to this repository.

`official-source.json` pins the download linked by Huawei's current Chinese design resource page, dated 12 June 2026. It includes archive and individual font SHA-256 values, font-table measurements, coverage samples, and variable axes. The package date differs from the internal font version: primary Latin and SC fonts report Version 2.040. No `opsz` optical-size axis is present. Latin and SC already installed on Armstrong match the official bytes exactly.

Requirements: Python 3, fontTools, fontconfig. Use your distribution's `python-fonttools`, or `uv run --with fonttools python` before the script path.

```sh
python packaging/fonts/hpos-fonts.py --detect
python packaging/fonts/hpos-fonts.py --download-official --dry-run
python packaging/fonts/hpos-fonts.py --download-official --install
python packaging/fonts/hpos-fonts.py --source-dir /path/to/official/fonts --license /path/to/LICENSE-update.txt --install
```

Inspection is the default. Installation uses `$XDG_DATA_HOME/fonts/hp-os` and refuses to replace a different font. A local font's name alone does not prove provenance: `matches_official_20260612` reports exact byte equivalence, and is false for unverified local releases. Inspect those releases separately before treating them as official. `--detect` returns nonzero if Latin or Simplified Chinese resolves to a substitute. Optional TC is reported independently.

For fallback, install `64-hp-os.conf` as `$XDG_CONFIG_HOME/fontconfig/conf.d/64-hp-os.conf` or use the equivalent Home Manager fontconfig option. It only affects HarmonyOS families. Primary text uses HarmonyOS Sans or HarmonyOS Sans SC. Noto covers missing characters and emoji only. Rebuild the font cache after adding fonts, and restart an existing Qt process to update Qt's font database.

Rollback: remove only the dedicated `hp-os` font directory and the dedicated fontconfig snippet, then run `fc-cache -f`. Existing fonts outside that directory remain unchanged. Fonts supplied by Nix should be removed through that package configuration.
