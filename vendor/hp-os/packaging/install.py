#!/usr/bin/env python3
"""Install a staged runtime in an isolated prefix; replacement retains rollback copy."""
import argparse
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def install(runtime, prefix, dry_run=False):
    runtime, prefix = pathlib.Path(runtime).resolve(), pathlib.Path(prefix).resolve()
    if not (runtime / "shell.qml").is_file() or not (runtime / "modules/harmony/HarmonyPanels.qml").is_file():
        raise ValueError("Provide a staged HP-OS runtime containing shell.qml and modules/harmony/HarmonyPanels.qml")
    if prefix == pathlib.Path.home() or prefix == pathlib.Path("/"):
        raise ValueError("Use a dedicated HP-OS prefix")
    plan = {"runtime": str(runtime), "prefix": str(prefix), "action": "install", "dry_run": dry_run, "existing_prefix_preserved": prefix.exists()}
    if dry_run:
        return plan
    prefix.parent.mkdir(parents=True, exist_ok=True)
    temp = pathlib.Path(tempfile.mkdtemp(prefix=".hp-os-", dir=prefix.parent))
    backup = None
    try:
        target_runtime = temp / "share/quickshell/inir"
        shutil.copytree(runtime, target_runtime)
        shutil.copytree(HERE, temp / "share/hp-os/packaging")
        (temp / "bin").mkdir()
        runner = (HERE / "hp-os").read_text().replace("@runtime@", str(prefix / "share/quickshell/inir")).replace("@packaging@", str(prefix / "share/hp-os/packaging"))
        (temp / "bin/hp-os").write_text(runner)
        (temp / "bin/hp-os").chmod(0o755)
        sessions = temp / "share/wayland-sessions"
        sessions.mkdir(parents=True)
        (sessions / "hp-os.desktop").write_text((HERE / "hp-os.desktop").read_text().replace("@exec@", str(prefix / "bin/hp-os")))
        applications = temp / "share/applications"
        applications.mkdir(parents=True)
        (applications / "hp-os-settings.desktop").write_text((HERE / "hp-os-settings.desktop").read_text().replace("@exec@", str(prefix / "bin/hp-os")))
        if prefix.exists():
            backup = prefix.with_name(prefix.name + ".backup-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
            prefix.rename(backup)
        temp.rename(prefix)
    except Exception:
        if backup and not prefix.exists():
            backup.rename(prefix)
        raise
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    plan["backup"] = str(backup) if backup else None
    return plan

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime")
    parser.add_argument("--prefix", default=str(pathlib.Path.home() / ".local/opt/hp-os"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.runtime, args.prefix, args.dry_run), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
