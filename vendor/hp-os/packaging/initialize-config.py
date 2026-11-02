#!/usr/bin/env python3
"""Seed a usable HP-OS desktop; retain user configuration and desktop arrangements."""
import configparser
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


def write_json(path, document, *, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(fd, 'w') as stream:
            json.dump(document, stream, indent=2)
            stream.write('\n')
        return True
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(document, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def installed_apps():
    home = Path.home()
    roots = [Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))]
    roots.extend(Path(p) for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p)
    # Nix desktop entries are available here even before a login manager exports XDG_DATA_DIRS.
    roots.extend([home / '.nix-profile/share', Path('/etc/profiles/per-user') / home.name / 'share', Path('/run/current-system/sw/share')])
    found = {}
    seen = set()
    for root in roots:
        apps = root / 'applications'
        if not apps.is_dir():
            continue
        for path in sorted(apps.rglob('*.desktop')):
            app_id = str(path.relative_to(apps)).replace('/', '-')[:-8]
            if app_id in seen:
                continue
            seen.add(app_id)
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding='utf-8')
                entry = parser['Desktop Entry']
                if entry.get('Type') != 'Application' or entry.get('Hidden', 'false').lower() == 'true' or entry.get('NoDisplay', 'false').lower() == 'true':
                    continue
                if not entry.get('Exec') and entry.get('DBusActivatable', 'false').lower() != 'true':
                    continue
                executable = entry.get('TryExec')
                if executable and not shutil.which(executable):
                    continue
                found[app_id] = {'label': entry.get('Name', app_id), 'icon': entry.get('Icon', ''), 'target': app_id, 'kind': 'application'}
            except (OSError, UnicodeError, configparser.Error, KeyError):
                continue
    return found


def defaults_for_installed_apps(apps):
    groups = [
        ['org.kde.dolphin', 'org.gnome.Nautilus', 'thunar', 'pcmanfm'],
        ['hp-os-trash'],
        ['org.kde.gwenview', 'org.gnome.Loupe', 'org.gnome.eog'],
        ['hp-os-settings'],
    ]
    return [next(app for app in group if app in apps) for group in groups if any(app in apps for app in group)]


def initialize(source, destination, wallpaper):
    destination = Path(destination)
    config = json.loads(Path(source).read_text())
    config['background']['wallpaperPath'] = wallpaper
    apps = installed_apps()
    pins = defaults_for_installed_apps(apps)
    config.setdefault('dock', {})['pinnedApps'] = pins
    created = write_json(destination, config, exclusive=True)
    state = Path(os.environ.get('INIR_STATE_DIR', str(Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hp-os'))) / 'user'
    marker = state / 'hp-os-desktop-defaults-v2.json'
    if not created and not marker.exists():
        try:
            existing = json.loads(destination.read_text())
        except (OSError, ValueError):
            return
        if existing.get('panelFamily') != 'harmony':
            return
        changed = False
        iris = existing.get('iris', {})
        for key, previous, replacement in [('bar', {'height': 40, 'margin': 12}, {'height': 40, 'margin': 20}), ('dock', {'iconSize': 44}, {'iconSize': 48})]:
            values = iris.get(key, {})
            if all(values.get(k) == v for k, v in previous.items()):
                values.update(replacement)
                changed = True
        background = existing.setdefault('background', {})
        old_wallpaper = background.get('wallpaperPath', '')
        # Qt persisted this bundled fallback after the former SVG failed to load.
        # Match only our Nix runtime asset, not a user's image with the same name.
        old_path = Path(old_wallpaper)
        shipped_fallback = (
            old_path.name == 'qs-niri.jpg'
            and old_wallpaper.endswith('/share/quickshell/inir/assets/wallpapers/qs-niri.jpg')
            and old_wallpaper.startswith('/nix/store/')
            and len(old_path.parts) > 3
            and '-hp-os-runtime-' in old_path.parts[3]
        )
        if old_wallpaper == '__HARMONY_WALLPAPER__' or old_wallpaper.endswith('/assets/harmony-wallpaper.svg') or shipped_fallback:
            background['wallpaperPath'] = wallpaper
            changed = True
        appearance = existing.setdefault('appearance', {})
        if appearance.get('iconTheme', 'WhiteSur-dark') == 'WhiteSur-dark':
            appearance['iconTheme'] = 'HP-OS'
            changed = True
        if 'surround' not in iris:
            iris['surround'] = {'enable': False}
            changed = True
        dock = existing.setdefault('dock', {})
        if 'pinnedApps' not in dock or dock['pinnedApps'] == ['org.gnome.Nautilus', 'firefox', 'kitty']:
            dock['pinnedApps'] = pins
            changed = True
        if changed:
            write_json(destination, existing)
    # Migrate former shipped themes even when desktop defaults were seeded earlier.
    icon_marker = state / 'hp-os-original-icons-v1.json'
    if not icon_marker.exists():
        try:
            current = json.loads(destination.read_text())
        except (OSError, ValueError):
            return
        if current.get('panelFamily') == 'harmony':
            appearance = current.get('appearance', {})
            if appearance.get('iconTheme') in ('WhiteSur-dark', 'Papirus'):
                appearance['iconTheme'] = 'HP-OS'
                write_json(destination, current)
            write_json(icon_marker, {'version': 1})
    # Upgrade only the exact pin list recorded by our previous desktop seed.
    # This marker is independent of desktop seeding so existing layouts stay intact.
    dock_marker = state / 'hp-os-dock-defaults-v3.json'
    if not dock_marker.exists():
        try:
            current = json.loads(destination.read_text())
        except (OSError, ValueError):
            return
        if current.get('panelFamily') != 'harmony':
            return
        try:
            seeded = json.loads(marker.read_text()).get('seededPins')
        except (OSError, ValueError, AttributeError):
            seeded = None
        current_pins = current.get('dock', {}).get('pinnedApps')
        if (not created and isinstance(seeded, list) and seeded
                and all(isinstance(app, str) for app in seeded)
                and current_pins == seeded and current_pins != pins):
            current['dock']['pinnedApps'] = pins
            write_json(destination, current)
        write_json(dock_marker, {'version': 3, 'seededPins': pins}, exclusive=True)
    # Seed an uninitialized empty desktop once. Later empty desktops belong to the user.
    items = {}
    folders = [(Path.home(), 'Home', 'user-home'), (Path.home() / 'Documents', 'Documents', 'folder-documents'), (Path.home() / 'Downloads', 'Downloads', 'folder-download')]
    records = [{'kind': 'folder', 'target': str(path), 'label': label, 'icon': icon} for path, label, icon in folders if path.is_dir()]
    records.extend(apps[app] for app in pins[:4])
    for index, record in enumerate(records):
        items[f'hp-os-initial-{index}'] = dict(record, customLabel=False, output='', x=24 + (index // 6) * 104, y=24 + (index % 6) * 104, locked=False, layer=0, trusted=True)
    if not marker.exists():
        desktop = state / 'desktop-items.json'
        if not write_json(desktop, {'version': 1, 'items': items}, exclusive=True):
            try:
                previous = json.loads(desktop.read_text())
            except (OSError, ValueError):
                previous = None
            if isinstance(previous, dict) and previous.get('version') == 1 and previous.get('items') == {}:
                write_json(desktop, dict(previous, items=items))
        write_json(marker, {'version': 2, 'seededPins': pins}, exclusive=True)


if __name__ == '__main__':
    initialize(*sys.argv[1:])
