#!/usr/bin/env bash
# Refresh an existing Ubuntu fleet desktop without restarting its display manager.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 2; }
user=${1:?Supply the desktop user}
base=$(cd -- "$(dirname -- "$0")" && pwd)
source /etc/os-release
[[ $ID == ubuntu ]] || exit 2
# Fonts are licensed host assets, never fetched from an unauthenticated public
# source. Reuse the supplied host fonts or recover an earlier installed copy.
for weight in Regular Medium; do
  target="/usr/local/share/fonts/hp/HPFormaDJROffice-$weight.ttf"
  if [[ ! -f $target ]]; then
    source_font="/usr/share/sddm/themes/hp-os/fonts/HPForma-$weight.ttf"
    if [[ -f $source_font ]]; then install -Dm644 "$source_font" "$target"; else
      echo "Licensed HP Forma $weight font is missing from the host provisioning; branding remains pending." >&2
      exit 2
    fi
  fi
done
# Preserve the installed HP-OS session. Never guess between unrelated desktops.
session=$(python3 - <<'PY'
import configparser,pathlib
sessions=[]
for p in pathlib.Path('/usr/share/wayland-sessions').glob('*.desktop'):
 c=configparser.ConfigParser(interpolation=None,strict=False); c.read(p)
 if c.get('Desktop Entry','Name',fallback='').startswith('HP-OS'): sessions.append(p.stem)
assert len(sessions)==1, 'Expected one installed HP-OS Wayland session before branding setup'
print(sessions[0])
PY
)
# A custom initrd must retain its complete driver/firmware set. Only replace the
# running kernel image after validation; recovery boot images remain unchanged.
release=$(uname -r)
image=/boot/initrd.img-$release
[[ -f $image && -d /lib/modules/$release ]] || { echo 'Current kernel/initrd missing; use owning boot workflow.' >&2; exit 2; }
command -v dracut >/dev/null
command -v lsinitrd >/dev/null
state=/var/lib/hp-os-branding/managed
install -d -m700 "$state"
bash "$base/install.sh" "$user" "$session" install --no-rebuild
hash=$(find /usr/share/plymouth/themes/hp-os -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
key="$release $hash"
if [[ $(cat "$state/current" 2>/dev/null || true) != "$key" ]]; then
 backup="$state/$(date -u +%Y%m%dT%H%M%SZ)"
 mkdir "$backup"
 cp -a "$image" "$backup/initrd.original"
 lsinitrd "$image" > "$backup/before.list"
 lsinitrd -m "$image" > "$backup/modules.before"
 resume=()
 if grep -qx resume "$backup/modules.before"; then resume=(--add resume); fi
 candidate=/boot/.hp-os-initrd-$release
 dracut --force "${resume[@]}" "$candidate" "$release"
 lsinitrd "$candidate" > "$backup/after.list"
 lsinitrd -m "$candidate" > "$backup/modules.after"
 python3 - "$backup" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); before=(p/'before.list').read_text(); after=(p/'after.list').read_text()
paths=lambda t:{l.split()[-1] for l in t.splitlines() if len(l.split())>5 and ('/modules/' in l or '/firmware/' in l)}
assert not paths(before)-paths(after), 'Rebuilt initrd lost drivers or firmware; original retained'
if '\nresume\n' in (p/'modules.before').read_text(): assert '\nresume\n' in (p/'modules.after').read_text()
for f in pathlib.Path('/usr/share/plymouth/themes/hp-os').iterdir():
 if f.is_file(): assert 'usr/share/plymouth/themes/hp-os/'+f.name in after, f.name
assert 'plymouth/script.so' in after
PY
 mv "$candidate" "$image"
 printf '%s\n' "$key" > "$state/current"
fi
if ! grep -qw splash /proc/cmdline; then
 echo 'Boot theme installed. Selected boot entry still needs splash; retain its host-specific boot workflow.' >&2
 exit 3
fi
echo 'Shared boot/login theme refreshed; running desktop and recovery images preserved.'
