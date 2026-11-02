"""Apply shared HP-OS notification and volume defaults, preserving other settings."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


def enable(path):
    path = Path(path).resolve()
    if not path.is_file():
        return
    data = json.loads(path.read_text())
    bar = data.setdefault("iris", {}).setdefault("bar", {})
    pieces = bar.get("pieces", ["sound"])
    if not isinstance(pieces, list):
        raise ValueError(f"Expected iris.bar.pieces array in {path}")
    before = json.dumps(data, sort_keys=True)
    bar["pieces"] = pieces + [piece for piece in ("battery", "notifications") if piece not in pieces]
    protection = data.setdefault("audio", {}).setdefault("protection", {})
    if protection.get("maxAllowedIncrease", 10) == 10:
        protection["maxAllowedIncrease"] = 11
    if json.dumps(data, sort_keys=True) == before:
        return
    fd, temporary = tempfile.mkstemp(prefix=".battery-", dir=path.parent)
    try:
        os.fchmod(fd, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    for filename in sys.argv[1:]:
        enable(filename)
