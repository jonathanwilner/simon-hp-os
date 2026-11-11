"""Patch the pinned trash crate without changing any unrelated vendor contents."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

vendor, patch, helper = map(Path, sys.argv[1:])
candidates = [path for path in vendor.rglob("freedesktop.rs")
              if path.parent.name == "src" and path.parent.parent.name.startswith("trash-")]
if len(candidates) != 1:
    raise SystemExit(f"Expected one trash crate, found {len(candidates)}")
crate = candidates[0].parent.parent
# cp -rs may leave directories containing symlinked files or a directory symlink.
copy = crate.with_name(crate.name + "-hp-os-copy")
shutil.copytree(crate, copy, symlinks=False)
for path in [copy, *copy.rglob("*")]:
    path.chmod(path.stat().st_mode | 0o200)
if crate.is_symlink():
    crate.unlink()
else:
    shutil.rmtree(crate)
copy.rename(crate)
subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch.resolve())], cwd=crate, check=True)
shutil.copyfile(helper, crate / "src/hpos_remote_trash.rs")
checksum = crate / ".cargo-checksum.json"
data = json.loads(checksum.read_text())
for name in ["src/freedesktop.rs", "src/hpos_remote_trash.rs"]:
    data["files"][name] = hashlib.sha256((crate / name).read_bytes()).hexdigest()
checksum.write_text(json.dumps(data, sort_keys=True) + "\n")
