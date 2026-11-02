#!/usr/bin/env python3
"""Seed installed Office apps into HP-OS once, preserving the user's layout."""
import configparser
import json
import os
from pathlib import Path

home = Path.home()
state = home / ".local/state/harmonyshell/user"
path = state / "desktop-items.json"
marker = state / "microsoft365-desktop-v1.json"
if marker.exists():
    raise SystemExit(0)
# Let HP-OS initialize its normal desktop before adding apps.
if not path.exists():
    raise SystemExit(0)
document = json.loads(path.read_text())
if document.get("version") != 1 or not isinstance(document.get("items"), dict):
    raise SystemExit("Unsupported HP-OS desktop state; preserved unchanged")
items = document["items"]
existing = {item.get("target") for item in items.values()}
occupied = [(item.get("x", 0), item.get("y", 0)) for item in items.values()]
added = []
for entry in sorted((home / ".local/share/applications").glob("microsoft365-*.desktop")):
    target = entry.stem
    if target in existing:
        continue
    desktop = configparser.ConfigParser(interpolation=None)
    desktop.read(entry)
    app = desktop["Desktop Entry"]
    # Match HP-OS's 104px grid and keep existing icons in their positions.
    positions = ((24 + col * 104, 24 + row * 104) for col in range(16) for row in range(8))
    position = next(((x, y) for x, y in positions if all(abs(x-a) >= 100 or abs(y-b) >= 100 for a, b in occupied)), None)
    if position is None:
        raise SystemExit("No desktop space; preserved unchanged")
    x, y = position
    occupied.append(position)
    items[target] = dict(kind="application", target=target, label=app["Name"].removeprefix("Microsoft "), icon=app["Icon"], customLabel=True, output="", x=x, y=y, locked=False, layer=0, trusted=True)
    added.append(target)
if len(added) + sum(target.startswith("microsoft365-") for target in existing if isinstance(target, str)) < 25:
    raise SystemExit("Office catalogue incomplete; preserved unchanged")
# Atomic replacement is observed by DesktopItems without restarting the shell.
temporary = path.with_suffix(".office-tmp")
temporary.write_text(json.dumps(document, indent=2) + "\n")
os.replace(temporary, path)
marker.write_text(json.dumps({"version": 1, "added": added}, indent=2) + "\n")
