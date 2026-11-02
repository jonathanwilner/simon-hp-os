#!/usr/bin/env python3
"""Replace only the Files dock pin, retaining the user's other HP-OS settings."""
import json
import os
from pathlib import Path
import tempfile
import sys


def update(path):
    if not path.exists():
        return False
    config = json.loads(path.read_text())
    dock = config.setdefault('dock', {})
    old = dock.get('pinnedApps', [])
    files = 'com.system76.CosmicFiles'
    pins = []
    for app in old:
        app = files if app in ('org.kde.dolphin', 'org.kde.dolphin.desktop') else app
        if app not in pins:
            pins.append(app)
    if files not in pins:
        pins.insert(0, files)
    if pins == old:
        return False
    dock['pinnedApps'] = pins
    fd, temporary = tempfile.mkstemp(prefix='.cosmic-files-', dir=path.parent)
    try:
        os.fchmod(fd, path.stat().st_mode & 0o777)
        with os.fdopen(fd, 'w') as stream:
            json.dump(config, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


if __name__ == '__main__':
    update(Path(sys.argv[1]))
