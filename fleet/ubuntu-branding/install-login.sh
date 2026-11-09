#!/usr/bin/env bash
# Select HP-OS SDDM for the next boot without disturbing an active desktop.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
user=${1:?Usage: install-login.sh USER SESSION_ID [install|restore]}
session=${2:?Supply a desktop session ID without .desktop}
mode=${3:-install}
[[ $user =~ ^[a-z_][a-z0-9_-]*\$?$ && $session =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2
source /etc/os-release
[[ $ID == ubuntu ]] || { echo 'This installer supports Ubuntu.' >&2; exit 1; }
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
state=/var/lib/hp-os-ubuntu-branding/login
conf=/etc/sddm.conf.d/90-hp-os.conf
backup() {
    local path=$1 key=$2
    if [[ -e $path || -L $path ]]; then cp -a -- "$path" "$state/$key"; else touch "$state/$key.absent"; fi
}
restore() {
    local path=$1 key=$2
    if [[ -e $state/$key || -L $state/$key ]]; then rm -f -- "$path"; cp -a -- "$state/$key" "$path";
    elif [[ -f $state/$key.absent ]]; then rm -f -- "$path"; fi
}
if [[ $mode == restore ]]; then
    [[ -f $state/complete ]] || { echo 'No saved login-manager state.' >&2; exit 1; }
    restore /etc/X11/default-display-manager default-display-manager
    restore /etc/systemd/system/display-manager.service display-manager.service
    restore "$conf" hp-os.conf
    restore /var/lib/sddm/state.conf sddm-state.conf
    original=$(cat "$state/default-display-manager" 2>/dev/null || true)
    [[ -z $original ]] || printf 'sddm shared/default-x-display-manager select %s\n' "${original##*/}" | debconf-set-selections
    systemctl daemon-reload
    echo 'Original login manager restored for next boot; active session preserved.'
    exit 0
fi
[[ $mode == install ]] || exit 2
id "$user" >/dev/null
[[ -f /usr/share/wayland-sessions/$session.desktop ]] || { echo "Missing session: $session" >&2; exit 1; }
for binary in /usr/bin/sddm /usr/bin/sddm-greeter-qt6 /usr/bin/Xorg /usr/bin/xauth; do
    [[ -x $binary ]] || {
        echo 'Install dependencies through nom-tmux with service starts blocked: sddm qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtqml-workerscript xserver-xorg xauth fonts-dejavu-core' >&2
        exit 1
    }
done
mkdir -p "$state" /etc/sddm.conf.d /var/lib/sddm
chmod 700 "$state"
if [[ ! -f $state/complete ]]; then
    backup /etc/X11/default-display-manager default-display-manager
    backup /etc/systemd/system/display-manager.service display-manager.service
    backup "$conf" hp-os.conf
    backup /var/lib/sddm/state.conf sddm-state.conf
    touch "$state/complete"
fi
mkdir -p /usr/share/sddm/themes/hp-os
cp -a "$base/sddm/hp-os/." /usr/share/sddm/themes/hp-os/
# Proprietary HP font stays on the host; public source contains no font binary.
font_source=${HP_OS_FORMA_FONT:-/usr/local/share/fonts/hp/HPFormaDJROffice-Regular.ttf}
if [[ -f $font_source ]]; then
    install -Dm644 "$font_source" /usr/share/sddm/themes/hp-os/fonts/HPForma-Regular.ttf
fi
printf '[General]\npreferredSession=%s.desktop\n' "$session" > /usr/share/sddm/themes/hp-os/theme.conf
cat > "$conf" <<'EOF'
[General]
DisplayServer=x11
InputMethod=
GreeterEnvironment=QT_QUICK_BACKEND=software
[Theme]
Current=hp-os
EnableAvatars=false
[X11]
EnableHiDPI=true
ServerArguments=-nolisten tcp -keeptty
[Users]
RememberLastSession=true
RememberLastUser=true
EOF
# Detect a higher-precedence override before selecting the manager.
python3 - <<'PY'
import configparser, glob
c = configparser.ConfigParser(interpolation=None, strict=False)
c.read(sorted(glob.glob('/usr/lib/sddm/sddm.conf.d/*.conf')) + sorted(glob.glob('/etc/sddm.conf.d/*.conf')) + ['/etc/sddm.conf'])
for section, key, expected in [('General', 'DisplayServer', 'x11'), ('General', 'GreeterEnvironment', 'QT_QUICK_BACKEND=software'), ('Theme', 'Current', 'hp-os')]:
    if c.get(section, key, fallback='') != expected:
        raise SystemExit(f'Conflicting SDDM override: {section}.{key}; resolve before selecting SDDM')
PY
printf '[Last]\nSession=/usr/share/wayland-sessions/%s.desktop\nUser=%s\n' "$session" "$user" > /var/lib/sddm/state.conf
chown sddm:sddm /var/lib/sddm/state.conf
chmod 600 /var/lib/sddm/state.conf
printf 'sddm shared/default-x-display-manager select sddm\n' | debconf-set-selections
printf '/usr/bin/sddm\n' > /etc/X11/default-display-manager
unit=$(systemctl show sddm.service --property=FragmentPath --value)
[[ -f $unit ]] || { echo 'Missing SDDM service unit.' >&2; exit 1; }
ln -sfn "$unit" /etc/systemd/system/display-manager.service
systemctl daemon-reload
echo 'HP-OS SDDM selected for next boot; active session preserved.'
