#!/usr/bin/env python3
"""Upgrade the original HP-OS input default, preserving customized blocks."""
from pathlib import Path
import sys

OLD = '    touchpad { tap; natural-scroll; }\n'
NEW = '''    touchpad {
        tap
        tap-button-map "left-middle-right"
        click-method "clickfinger"
        middle-emulation
        natural-scroll
    }
    mouse { middle-emulation; }
'''


def migrate(path):
    text = path.read_text()
    if text.count(OLD) != 1 or 'mouse {' in text:
        return
    backup = path.with_name(path.name + '.before-clickfinger')
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(OLD, NEW, 1))


if __name__ == '__main__':
    migrate(Path(sys.argv[1]))
