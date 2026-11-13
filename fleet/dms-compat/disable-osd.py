#!/usr/bin/env python3
"""Disable DMS hotkey surfaces while retaining its lock screen and services."""
import pathlib
import re
import sys


def patch(directory):
    path = pathlib.Path(directory) / "DMSShell.qml"
    source = path.read_text()
    pattern = r'(\bid: osdSurfacesLoader\s+active:) root\.osdSurfacesLoaded\b'
    updated, count = re.subn(pattern, r'\1 false /* HP-OS owns hotkey feedback */', source)
    if count != 1:
        raise RuntimeError(f"Expected one DMS OSD loader, found {count}")
    path.write_text(updated)


if __name__ == "__main__":
    patch(sys.argv[1])
