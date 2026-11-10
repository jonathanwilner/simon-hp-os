"""One-time, atomic migration of portable HP-OS controls; retain user settings."""
import json
import os
from pathlib import Path
import sys
import tempfile


def migrate_apps(config_path, marker_path):
    path, marker = Path(config_path), Path(marker_path)
    if marker.exists() or not path.is_file():
        return
    path = path.resolve()
    data = json.loads(path.read_text())
    apps = data.setdefault('apps', {})
    replacements = {
        'network': ('kitty -1 fish -c nmtui', 'nm-connection-editor'),
        'networkEthernet': ('kcmshell6 kcm_networkmanagement', 'nm-connection-editor'),
        'browser': ('firefox', 'google-chrome-stable'),
        'terminal': ('kitty', 'ghostty'),
    }
    changed = False
    for key, (previous, replacement) in replacements.items():
        if key not in apps or apps[key] == previous:
            apps[key] = replacement
            changed = True
    if changed:
        fd, temporary = tempfile.mkstemp(prefix='.fleet-apps-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(data, stream, indent=2)
                stream.write('\n')
            os.chmod(temporary, path.stat().st_mode & 0o777)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('1\n')


def migrate(config_path, marker_path, power_supply=Path('/sys/class/power_supply')):
    path, marker = Path(config_path), Path(marker_path)
    migrate_apps(path, marker.with_name('desktop-app-commands-v1'))
    if marker.exists() or not path.is_file():
        return
    # Resolve writable external configurations without replacing their symlink.
    path = path.resolve()
    data = json.loads(path.read_text())
    bar = data.setdefault('iris', {}).setdefault('bar', {})
    pieces = bar.setdefault('pieces', [])
    if not isinstance(pieces, list):
        raise ValueError('iris.bar.pieces must be a list')
    battery = any(p.read_text().strip() == 'Battery'
                  for p in Path(power_supply).glob('*/type'))
    for name in (['battery'] if battery else []) + ['notifications']:
        if name not in pieces:
            pieces.append(name)
    # Replace the inherited Dolphin pin only. Preserve deliberately unpinned
    # file managers, other applications, their order, and custom dock settings.
    dock = data.get('dock', {})
    pins = dock.get('pinnedApps')
    if isinstance(pins, list):
        result = []
        for pin in pins:
            replacement = ('com.system76.CosmicFiles' if pin in
                           ('org.kde.dolphin', 'org.kde.dolphin.desktop') else pin)
            if replacement not in result:
                result.append(replacement)
        dock['pinnedApps'] = result
    fd, temporary = tempfile.mkstemp(prefix='.fleet-controls-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('1\n')


if __name__ == '__main__':
    migrate(*sys.argv[1:])
