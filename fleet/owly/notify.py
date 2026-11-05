#!/usr/bin/env python3
"""Translate Omdrop's notification argv to the active desktop notification bus."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main(argv):
    worker = bool(argv and argv[0] == '--worker')
    if worker:
        argv = argv[1:]
    timeout = '8000'
    if argv[:1] == ['-t']:
        if len(argv) < 2:
            raise ValueError('Missing notification timeout')
        timeout, argv = argv[1], argv[2:]
    if len(argv) < 2 or not timeout.isdigit():
        raise ValueError('Expected [-t milliseconds] title body [--image file] [--exec argv...]')
    title, body, *options = argv
    image = None
    action = []
    while options:
        option = options.pop(0)
        if option == '--image' and options:
            image = options.pop(0)
        elif option == '--exec' and options:
            action = options
            break
        else:
            raise ValueError('Unsupported notification argument')
    if action and not worker:
        # The upstream arrival handler must not block subsequent transfers.
        subprocess.Popen([sys.executable, __file__, '--worker', *argv_prefix(timeout, title, body, image, action)],
                         start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0
    env = os.environ.copy()
    state_path = Path(env.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'hp-os-omdrop/controller.json'
    try:
        state = json.loads(state_path.read_text())
        for source, target in [('notification_bus', 'DBUS_SESSION_BUS_ADDRESS'),
                               ('notification_display', 'DISPLAY'),
                               ('notification_wayland_display', 'WAYLAND_DISPLAY')]:
            if state.get(source):
                env[target] = state[source]
    except FileNotFoundError:
        pass
    command = ['@notifySend@', '--app-name=Omdrop', '--expire-time=' + timeout,
               '--hint=boolean:transient:false']
    if image:
        command += ['--icon', image]
    if action:
        command += ['--wait', '--action=default=Open file']
    command += ['--', title, body]
    try:
        result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=3600 if action else 10)
    except subprocess.TimeoutExpired:
        return 0
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    if action and result.stdout.strip() == 'default':
        subprocess.Popen(action, env=env, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def argv_prefix(timeout, title, body, image, action):
    return ['-t', timeout, title, body] + (['--image', image] if image else []) + ['--exec', *action]


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, OSError) as error:
        print(f'Omdrop notification: {error}', file=sys.stderr)
        sys.exit(1)
