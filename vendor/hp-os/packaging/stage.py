#!/usr/bin/env python3
"""Build a private runtime from the pinned upstream checkout without installation."""
import argparse
import pathlib
import shutil
import subprocess
import sys

PIN = "48cdcecb0f6089cfbb7019054602eab28e154b3b"
ROOT = pathlib.Path(__file__).resolve().parent.parent


def stage(upstream, destination):
    upstream, destination = pathlib.Path(upstream).resolve(), pathlib.Path(destination).resolve()
    if destination.exists():
        raise ValueError(f"Refusing to replace existing runtime: {destination}")
    revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if revision != PIN:
        raise ValueError(f"Expected iNiR {PIN}, got {revision}")
    patch = ROOT / "patches/inir-harmony.patch"
    if not patch.is_file():
        raise ValueError(f"Missing integration patch: {patch}")
    subprocess.run([sys.executable, str(upstream / "sdata/lib/runtime-payload.py"), "copy", "--root", str(upstream), "--target", str(destination)], check=True)
    for patch in (patch, ROOT / "patches/harmony-style.patch", ROOT / "patches/harmony-wallpaper-startup.patch", ROOT / "patches/harmony-desktop-labels.patch"):
        subprocess.run(["patch", "-p1", "--batch", "-i", str(patch)], cwd=destination, check=True)
    shutil.copytree(ROOT / "overlay", destination, dirs_exist_ok=True)
    # Upstream helpers target /usr/bin. Resolve helpers from the caller's PATH on Nix.
    for tree in ("modules", "services", "defaults", "scripts"):
        for path in (destination / tree).rglob("*"):
            if path.suffix in (".qml", ".js", ".sh", ".py") and path.is_file():
                lines = path.read_text().splitlines(keepends=True)
                path.write_text("".join(lines[:1]) + "".join(lines[1:]).replace("/usr/bin/", ""))
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream")
    parser.add_argument("destination")
    args = parser.parse_args()
    try:
        stage(args.upstream, args.destination)
    except (ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")
