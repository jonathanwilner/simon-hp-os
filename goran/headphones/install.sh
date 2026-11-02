#!/usr/bin/env bash
# Install only the headphone apps, without activating unrelated desktop changes.
set -euo pipefail
bundle=${1:?Usage: install.sh BUILT_BUNDLE}
bundle=$(readlink -f "$bundle")
test -x "$bundle/bin/openfreebuds_qt"
test -x "$bundle/bin/librepods"
root="$HOME/.local/share/goran-headphones"
mkdir -p "$root" "$HOME/.local/bin" "$HOME/.local/share/applications"
# This profile roots the closure against garbage collection.
nix-env --profile "$root/profile" --set "$bundle"
for app in openfreebuds_qt openfreebuds_cmd librepods librepods-ctl; do
  target="$HOME/.local/bin/$app"
  if [[ -e "$target" && ! -L "$target" ]]; then
    echo "Refusing to replace existing file: $target" >&2
    exit 1
  fi
  ln -sfn "$root/profile/bin/$app" "$target"
done
for entry in "$bundle"/share/applications/*.desktop; do
  name=$(basename "$entry")
  # Keep app metadata and icons, but make Exec independent of Fuzzel's PATH.
  sed -E -e "s|^Exec=(openfreebuds_qt\|librepods)(.*)|Exec=$root/profile/bin/\1\2|" -e "s|^(Exec=.*)/openfreebuds_qt$|\1/openfreebuds_qt --settings|" -e "s|^Icon=librepods$|Icon=$root/profile/share/icons/hicolor/scalable/apps/librepods.svg|" \
    -e "s|^Icon=pw.mmk.OpenFreebuds$|Icon=$root/profile/share/icons/hicolor/256x256/apps/pw.mmk.OpenFreebuds.png|" \
    "$entry" > "$HOME/.local/share/applications/$name"
done
if command -v update-desktop-database >/dev/null; then
  update-desktop-database "$HOME/.local/share/applications"
fi
