#!/usr/bin/env python3
"""Preserve desktop state while adopting HP-OS paths and command names."""
import json
import os
from pathlib import Path

def migrate(home=None):
    home = Path(home or Path.home())
    roots = [Path(os.environ.get(key, home / default)) for key, default in
             [('XDG_CONFIG_HOME', '.config'), ('XDG_STATE_HOME', '.local/state'), ('XDG_CACHE_HOME', '.cache')]]
    for root in roots:
        old, new = root / 'harmonyshell', root / 'hp-os'
        if old.is_dir() and not old.is_symlink() and not new.exists():
            old.rename(new)
            old.symlink_to('hp-os', target_is_directory=True)
        elif old.is_dir() and not old.is_symlink() and new.is_dir():
            for child in old.iterdir():
                destination = new / child.name
                if not destination.exists() and not destination.is_symlink():
                    child.rename(destination)
            if not any(old.iterdir()):
                old.rmdir()
                old.symlink_to('hp-os', target_is_directory=True)
    config = roots[0] / 'hp-os'
    path = config / 'config.json'
    if path.exists():
        data = json.loads(path.read_text())
        original = json.dumps(data, sort_keys=True)
        appearance = data.get('appearance', {})
        if appearance.get('iconTheme') == 'HarmonyOS':
            appearance['iconTheme'] = 'HP-OS'
        # Exact legacy keys remain here solely for existing installations.
        if data.get('panelFamily') == 'harmony':
            data['panelFamily'] = 'hpos'
        if 'harmony' in data:
            previous = data.pop('harmony')
            current = data.setdefault('hpos', {})
            if isinstance(previous, dict) and isinstance(current, dict):
                for key, value in previous.items():
                    current.setdefault(key, value)
        if json.dumps(data, sort_keys=True) != original:
            temporary = path.with_suffix('.json.hp-os-new')
            temporary.write_text(json.dumps(data, indent=2) + '\n')
            temporary.chmod(path.stat().st_mode & 0o777)
            temporary.replace(path)
    for path in (config / 'niri').rglob('*.kdl') if (config / 'niri').is_dir() else []:
        text = path.read_text()
        updated = text.replace('"harmonyshell"', '"hp-os"').replace('// HarmonyShell', '// HP-OS').replace('\"harmony\"', '\"hpos\"').replace('^(harmony|', '^(hpos|')
        if updated != text:
            path.write_text(updated)

if __name__ == '__main__':
    migrate()
