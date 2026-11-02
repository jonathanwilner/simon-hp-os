#!/usr/bin/env python3
"""Report observable dependencies without changing the desktop."""
import argparse
import json
import os
import re
import shutil
import subprocess

REQUIRED = ["niri", "qs", "dbus-run-session", "gdbus", "wpctl", "nmcli", "bluetoothctl", "wl-copy", "cliphist", "python3", "fc-match"]
OPTIONAL = ["brightnessctl", "ddcutil", "grim", "slurp", "wf-recorder", "playerctl", "foot", "xdg-open", "polkit-gnome-authentication-agent-1"]

def run(command):
    try:
        return subprocess.run(command, text=True, capture_output=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def report():
    checks = [{"id": f"dependency:{name}", "status": "PASS" if shutil.which(name) else "FAIL", "path": shutil.which(name)} for name in REQUIRED]
    checks += [{"id": f"optional:{name}", "status": "PASS" if shutil.which(name) else "UNAVAILABLE", "path": shutil.which(name)} for name in OPTIONAL]
    version = run(["niri", "--version"])
    match = re.search(r"\b(\d+)\.(\d+)", version)
    valid = bool(match and tuple(map(int, match.groups())) >= (26, 4) and "unstable" not in version)
    checks.append({"id": "niri:26.04", "status": "PASS" if valid else "UNVERIFIED", "version": version})
    qs_version = run(["qs", "--version"])
    qs_match = re.search(r"\b(\d+)\.(\d+)\.(\d+)", qs_version)
    checks.append({"id": "quickshell:0.3.2", "status": "PASS" if qs_match and tuple(map(int, qs_match.groups())) >= (0, 3, 2) else "FAIL", "version": qs_version})
    fonts = run(["fc-list", ":family=HarmonyOS Sans", "family"]).splitlines()
    checks.append({"id": "font:harmonyos-sans", "status": "PASS" if any("HarmonyOS Sans" in x for x in fonts) else "FAIL", "families": fonts})
    owner = run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.NameHasOwner", "org.freedesktop.Notifications"])
    checks.append({"id": "notifications:existing-owner", "status": "INFO", "value": owner})
    for name in ["dock-launch-focus", "notifications", "audio", "network", "bluetooth", "brightness", "wallpaper", "settings-persistence", "lock-unlock", "monitor-hotplug", "sleep-wake", "logout", "visual-1080p", "visual-1440p", "visual-hidpi", "visual-chinese"]:
        checks.append({"id": f"acceptance:{name}", "status": "UNVERIFIED", "reason": "Requires an observed running HP-OS session; dependency presence is insufficient."})
    return {"schemaVersion": 1, "checks": checks, "quickshell": run(["qs", "--version"]), "waylandDisplay": os.environ.get("WAYLAND_DISPLAY", "")}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = report()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for check in result["checks"]:
            print(f'{check["status"]:12} {check["id"]}')
