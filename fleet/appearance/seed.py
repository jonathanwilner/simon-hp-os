"""Seed portable defaults without replacing existing user choices."""
import json
import os
from pathlib import Path
import sys
import tempfile


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".fleet-appearance-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def seed(root, terminal_defaults, dms_defaults):
    for relative, text in terminal_defaults.items():
        path = root / relative
        if not path.exists():
            atomic_write(path, text)
    path = root / "DankMaterialShell/settings.json"
    # Existing DMS settings belong to its runtime. Never race its writes or
    # replace a malformed file. Only new accounts receive appearance defaults.
    if not path.exists():
        atomic_write(path, json.dumps(dms_defaults, indent=2) + "\n")
    path = root / "mimeapps.list"
    # Preserve existing associations, comments and formatting byte-for-byte.
    if not path.exists():
        content = "[Default Applications]\n"
        content += "inode/directory=com.system76.CosmicFiles.desktop;\n"
        for mime in ("video/mp4", "video/x-matroska", "video/webm", "video/quicktime"):
            content += f"{mime}=io.github.celluloid_player.Celluloid.desktop;\n"
        atomic_write(path, content)


if __name__ == "__main__":
    seed(Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()),
         json.loads(Path(sys.argv[3]).read_text()))
