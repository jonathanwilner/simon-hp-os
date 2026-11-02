#!/usr/bin/env python3
"""Install Goran's declarative keyboard fragment without replacing HP-OS settings."""
import os
from pathlib import Path
import sys
import tempfile

config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
root = Path(os.environ.get("INIR_NIRI_CONFIG_DIR", str(Path(os.environ.get("INIR_CONFIG_DIR", str(config / "hp-os"))) / "niri")))
fragment = root / "config.d/62-goran-keyboard.kdl"
fragment.parent.mkdir(parents=True, exist_ok=True)


def write(path, content):
    if path.exists() and path.read_text() == content:
        return
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


write(fragment, Path(sys.argv[1]).read_text())
main = root / "config.kdl"
if main.exists():
    content = main.read_text()
    include = 'include "config.d/62-goran-keyboard.kdl"'
    if include not in (line.strip() for line in content.splitlines()):
        write(main, content.rstrip() + "\n" + include + "\n")
