#!/usr/bin/env python3
"""Deliver a background notification to each live fleet compositor session."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
for path in runtime.glob('hp-os-fleet-notify-*.json'):
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            continue
        env = json.loads(path.read_text())
        socket = Path(env['NIRI_SOCKET'])
        if not socket.is_socket() or socket.stat().st_uid != os.getuid():
            continue
        # Never source shell content or import this private bus into systemd.
        if not env['DBUS_SESSION_BUS_ADDRESS'].startswith('unix:'):
            continue
        scoped = os.environ.copy()
        scoped.update({k: env[k] for k in ('DBUS_SESSION_BUS_ADDRESS', 'WAYLAND_DISPLAY')})
        subprocess.run(sys.argv[1:], env=scoped, timeout=10, check=False)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        continue
