#!/usr/bin/env python3
"""Launch and close only tagged test windows through the installed Fuzzel helper."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import uuid

import canary

APPS = {'ghostty': 'com.mitchellh.ghostty', 'moonlight': 'com.moonlight_stream.Moonlight'}
TOKEN_NAME = 'HP_OS_FLEET_LAUNCH_TEST'


def process_ids():
    return {int(path.name) for path in Path('/proc').iterdir() if path.name.isdecimal()}


def token_matches(pid, token):
    try:
        proc = Path('/proc') / str(pid)
        if proc.stat().st_uid != os.getuid():
            return False
        return f'{TOKEN_NAME}={token}'.encode() in (proc / 'environ').read_bytes().split(b'\0')
    except (OSError, ValueError):
        return False


def owned_windows(windows, baseline_ids, baseline_pids, token):
    return [window for window in windows
            if window.get('id') not in baseline_ids and window.get('pid') not in baseline_pids
            and window.get('app_id') in APPS.values()
            and isinstance(window.get('pid'), int) and token_matches(window['pid'], token)]


def action(socket_path, *arguments):
    environment = dict(os.environ, NIRI_SOCKET=str(socket_path))
    subprocess.run(['niri', 'msg', 'action', *arguments], env=environment,
                   check=True, text=True, capture_output=True, timeout=10)


def close_owned(socket_path, baseline_ids, baseline_pids, token, known):
    """Revalidate ownership immediately before closing; never close an old window."""
    errors = []
    try:
        windows, _ = canary.niri_windows(socket_path)
        for window in owned_windows(windows, baseline_ids, baseline_pids, token):
            known[window['id']] = window['pid']
        for identifier, pid in list(known.items()):
            current, _ = canary.niri_windows(socket_path)
            owned = owned_windows(current, baseline_ids, baseline_pids, token)
            if any(w['id'] == identifier and w['pid'] == pid for w in owned):
                try:
                    action(socket_path, 'close-window', '--id', str(identifier))
                except (OSError, subprocess.SubprocessError) as error:
                    errors.append(f'Window {identifier}: {error}')
    except (canary.ProbeError, OSError, ValueError) as error:
        errors.append(str(error))
    deadline = time.monotonic() + 3
    while known and time.monotonic() < deadline:
        try:
            remaining, _ = canary.niri_windows(socket_path)
            live = [w for w in owned_windows(remaining, baseline_ids, baseline_pids, token)
                    if known.get(w['id']) == w['pid']]
            if not live:
                break
        except (canary.ProbeError, OSError, ValueError) as error:
            errors.append(str(error))
            break
        time.sleep(0.1)
    else:
        if known:
            errors.append('Tagged test windows remain after close requests')
    return errors


def launch_test(args):
    generation = canary.installed_generation(args.installed_record, args.active_generation, args.revision)
    socket_path = canary.session_socket(args.niri_socket)
    args.niri_socket = str(socket_path)
    launcher = Path.home() / '.local/bin/fuzzel-launch'
    expected = generation / 'home-files/.local/bin/fuzzel-launch'
    canary.require(launcher.resolve(strict=True) == expected.resolve(strict=True),
                   'Installed launcher does not belong to active generation')
    launcher_bytes = launcher.read_bytes()
    launcher_hash = hashlib.sha256(launcher_bytes).hexdigest()
    canary.require(os.access(launcher, os.X_OK), 'Installed launcher is not executable')
    initial, _ = canary.niri_windows(socket_path)
    baseline_ids = {window['id'] for window in initial}
    baseline_pids = process_ids()
    token = uuid.uuid4().hex
    known = {}
    result = None
    cleanup_errors = []
    try:
        environment_command = shutil.which('env')
        sleep_command = shutil.which('sleep')
        canary.require(environment_command and sleep_command, 'env and sleep commands are required')
        for command in APPS:
            executable = generation / 'home-path/bin' / command
            argv = [str(launcher), environment_command, f'{TOKEN_NAME}={token}', str(executable)]
            if command == 'ghostty':
                argv += ['--gtk-single-instance=false', '--confirm-close-surface=false', '--title=Fleet release check', '-e', sleep_command, '60']
            # Moonlight receives no host or stream arguments: open its home screen only.
            action(socket_path, 'spawn', '--', *argv)
        deadline = time.monotonic() + args.timeout
        selected = {}
        while time.monotonic() < deadline:
            windows, compositor_pid = canary.niri_windows(socket_path)
            owned = owned_windows(windows, baseline_ids, baseline_pids, token)
            for window in owned:
                known[window['id']] = window['pid']
                for command, app_id in APPS.items():
                    if window['app_id'] == app_id:
                        selected[command] = window
            if len(selected) == len(APPS):
                break
            time.sleep(0.25)
        canary.require(len(selected) == len(APPS),
                       'Fresh tagged windows were not created for both applications; existing windows cannot pass')
        # Validate only this test's fresh windows; preserve all existing applications.
        result = canary.probe(args, required_windows=selected)
        result['fresh_launch'] = True
        result['launcher'] = {'path': str(launcher), 'source_sha256': launcher_hash,
                              'generation_source': str(expected.resolve(strict=True))}
        result['scope'] = ('Fresh tagged windows launched through the installed Fuzzel helper; active package '
                           'executables and native Wayland connections. No media playback or visual rendering test.')
        canary.require(hashlib.sha256(launcher.read_bytes()).hexdigest() == launcher_hash,
                       'Launcher changed during acceptance')
    finally:
        cleanup_errors = close_owned(socket_path, baseline_ids, baseline_pids, token, known)
        canary.require(not cleanup_errors, 'Test window cleanup failed: ' + '; '.join(cleanup_errors))
    result['cleanup'] = {'closed_window_ids': sorted(known), 'errors': []}
    return result


def main():
    state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--system', required=True, choices=['aarch64-linux', 'x86_64-linux'])
    parser.add_argument('--installed-record', type=Path, default=state / 'hp-os-fleet/installed.json')
    parser.add_argument('--active-generation', type=Path, default=state / 'nix/profiles/home-manager')
    parser.add_argument('--niri-socket')
    parser.add_argument('--timeout', type=float, default=20)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        canary.require(0 < args.timeout <= 30, 'Timeout must be between 0 and 30 seconds')
        result = launch_test(args)
    except (canary.ProbeError, OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        result = {'passed': False, 'fresh_launch': False, 'revision': args.revision,
                  'system': args.system, 'hostname': socket.gethostname(), 'error': str(error)}
    payload = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(payload)
    print(payload, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
