#!/usr/bin/env python3
"""Content-free local control for the HP-OS Relay tile."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from relay_setup import start_service

config = Path.home() / '.config/relay/linux.json'
paused = Path.home() / '.cache/relay/paused'
status_file = paused.parent / 'status.json'
env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/' + str(os.getuid()) + '/bus')
action = sys.argv[1] if len(sys.argv) > 1 else 'status'
if action == 'status':
    active = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'relay-clipboard'], env=env).returncode == 0
    try:
        health = json.loads(status_file.read_text())
    except (OSError, ValueError):
        health = {}
    print(json.dumps({'configured': config.exists(), 'active': active, 'paused': paused.exists(),
                     'healthy': active and health.get('ok', False) and time.time() - health.get('time', 0) < 20}))
elif action == 'session-start':
    # Existing enrollment is the only authority for automatic startup. Keep
    # pause state intact and never open enrollment UI during compositor startup.
    try:
        enrolled = json.loads(config.read_text())
    except (OSError, ValueError):
        raise SystemExit(0)
    if enrolled.get('enabled', False):
        start_service()
elif action == 'session-stop':
    # Another desktop may have taken ownership since this supervisor started.
    # Stop only if the service environment still names our Wayland display.
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
    try:
        values = (runtime / 'relay-clipboard.env').read_text().splitlines()
    except OSError:
        raise SystemExit(0)
    value = os.environ.get('WAYLAND_DISPLAY', '')
    escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
    if value and 'WAYLAND_DISPLAY="' + escaped + '"' in values:
        subprocess.run(['systemctl', '--user', 'stop', 'relay-clipboard.service'], env=env, check=True, timeout=20)
elif action == 'pause':
    paused.parent.mkdir(parents=True, exist_ok=True)
    paused.touch(mode=0o600)
elif action == 'resume':
    if not config.exists():
        raise SystemExit('Open Relay setup to connect this device first.')
    paused.unlink(missing_ok=True)
    start_service()
else:
    raise SystemExit('Expected status, pause, resume, session-start, or session-stop.')
