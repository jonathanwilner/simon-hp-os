#!/usr/bin/env bash
# Ubuntu host integration. Invoke through nom-tmux when rebuilding initramfs.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 ]] || { echo 'Run as root' >&2; exit 2; }
mode=${1:-install}
rebuild=yes
[[ ${2:-} != --no-rebuild ]] || rebuild=no
[[ $mode == install || $mode == restore ]] || { echo 'Usage: install-boot.sh install|restore [--no-rebuild]' >&2; exit 2; }
[[ $# -le 2 && ( $# -lt 2 || $2 == --no-rebuild ) ]] || exit 2
source_dir=$(cd -- "$(dirname -- "$0")" && pwd)
state=/var/lib/hp-os-branding/boot
base=/usr/share/plymouth/themes
theme=$base/hp-os
conf=/etc/plymouth/plymouthd.conf
command -v plymouth >/dev/null
# A custom initrd may contain a module absent from the root filesystem. Rebuilding
# it generically loses that module. Require its owning workflow to rebuild it.
if [[ $rebuild == yes ]]; then
  for image in /boot/initrd.img-*; do
    [[ -e $image && ! -L $image ]] || continue
    kernel=${image#/boot/initrd.img-}
    [[ -d /lib/modules/$kernel ]] || {
      echo "Custom initrd requires its owning rebuild workflow: $image. Use --no-rebuild only with that workflow." >&2
      exit 2
    }
  done
  command -v dracut >/dev/null || command -v update-initramfs >/dev/null
fi
[[ $mode != restore || -e $state/saved ]] || { echo "No saved boot branding state" >&2; exit 2; }
mkdir -p "$state"
if [[ ! -e $state/saved ]]; then
  if [[ -e $conf ]]; then cp -a "$conf" "$state/plymouthd.conf"; else touch "$state/no-conf"; fi
  readlink -f "$base/default.plymouth" > "$state/default-theme"
  touch "$state/saved"
fi
if [[ $mode == install ]]; then
  [[ -f $base/spinner/spinner.plymouth && -f $base/spinner/entry.png ]] || {
    echo 'Install the Ubuntu plymouth and plymouth-theme-spinner packages first.' >&2; exit 2;
  }
  # Use distribution-owned animation and password-dialog assets. The custom
  # watermark replaces Ubuntu branding; no GPU driver changes are needed.
  mkdir -p "$theme"
  cp -a "$base/spinner/"*.png "$theme/"
  install -m0644 "$source_dir/plymouth/hp-os.plymouth" "$theme/hp-os.plymouth"
  install -m0644 "$source_dir/plymouth/watermark.png" "$theme/watermark.png"
  update-alternatives --install "$base/default.plymouth" default.plymouth "$theme/hp-os.plymouth" 110
  update-alternatives --set default.plymouth "$theme/hp-os.plymouth"
  # Explicit dracut selection also works when plymouth-set-default-theme is
  # absent (Ubuntu Plymouth 24.004). Preserve unrelated administrator settings.
  python3 - "$conf" <<'PY'
import configparser, pathlib, sys
p=pathlib.Path(sys.argv[1]); c=configparser.ConfigParser(interpolation=None)
c.optionxform=str
if p.exists(): c.read(p)
if not c.has_section('Daemon'): c.add_section('Daemon')
c['Daemon']['Theme']='hp-os'
p.parent.mkdir(parents=True, exist_ok=True)
with p.open('w') as f: c.write(f)
PY
else
  if [[ -e $state/no-conf ]]; then rm -f "$conf"; else cp -a "$state/plymouthd.conf" "$conf"; fi
  previous=$(cat "$state/default-theme")
  [[ -f $previous ]] && update-alternatives --set default.plymouth "$previous"
fi
if [[ $rebuild == yes ]]; then
  if command -v dracut >/dev/null; then
    for image in /boot/initrd.img-*; do
      [[ -f $image && ! -L $image ]] || continue
      kernel=${image#/boot/initrd.img-}
      [[ -e $state/$(basename "$image") ]] || cp -a "$image" "$state/"
      temporary="$image.hp-os-new"
      trap 'rm -f "${temporary:-}"' EXIT
      dracut --force "$temporary" "$kernel"
      chmod --reference="$image" "$temporary"
      mv -f "$temporary" "$image"
      sync -f "$image"
      trap - EXIT
    done
  else
    for image in /boot/initrd.img-*; do
      [[ -f $image && ! -L $image ]] || continue
      [[ -e $state/$(basename "$image") ]] || cp -a "$image" "$state/"
    done
    update-initramfs -u -k all
  fi
else
  echo 'Theme configured. Owning workflow must rebuild all boot initrds before reboot.'
fi
