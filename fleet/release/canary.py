#!/usr/bin/env python3
"""Read-only live Niri desktop release acceptance. Never starts media or changes windows."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import re
import socket
import struct
import subprocess


class ProbeError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ProbeError(message)


def store_root(path):
    match = re.match(r'^(/nix/store/[a-z0-9]{32}-[^/]+)/', str(path))
    require(match, f'Executable is outside the immutable Nix store: {path}')
    return match[1]


def installed_generation(record, active, revision):
    require(re.fullmatch(r'[0-9a-f]{40}', revision), 'Expected revision must be a full Git SHA')
    data = json.loads(Path(record).read_text())
    require(data.get('fleet_revision') == revision, 'Installed fleet revision differs from candidate')
    generation = Path(active).resolve(strict=True)
    require(generation == Path(data['generation']).resolve(strict=True), 'Active Home Manager generation differs from installation record')
    embedded = generation / 'home-files/.config/hp-os-fleet/revision'
    require(embedded.read_text().strip() == revision, 'Generation does not embed the expected fleet revision')
    return generation


def niri_windows(path):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(5)
        connection.connect(str(path))
        pid, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        require(uid == os.getuid(), 'Niri socket belongs to another user')
        connection.sendall(b'"Windows"\n')
        with connection.makefile('rb') as stream:
            reply = stream.readline(4 * 1024 * 1024)
    data = json.loads(reply)
    windows = data.get('Ok', {}).get('Windows')
    require(isinstance(windows, list), 'Niri did not return a window inventory')
    return windows, pid


def session_socket(explicit=None):
    if explicit:
        return str(explicit)
    inherited = os.environ.get('NIRI_SOCKET')
    if inherited:
        try:
            niri_windows(inherited)
            return inherited
        except (ProbeError, OSError, ValueError):
            pass
    live = []
    for candidate in Path(f'/run/user/{os.getuid()}').glob('niri.*.sock'):
        try:
            niri_windows(candidate)
            live.append(str(candidate))
        except (ProbeError, OSError, ValueError):
            continue
    require(len(live) == 1, 'Specify --niri-socket: expected exactly one live Niri session')
    return live[0]


def wayland_peer(ss_output, pid, display, compositor_pid):
    rows = [line.split() for line in ss_output.splitlines()]
    rows = [row for row in rows if len(row) >= 9]
    by_inode = {row[5]: row for row in rows}
    for row in rows:
        if row[1] != 'ESTAB' or not re.search(rf'\bpid={pid},', ' '.join(row[8:])):
            continue
        peer = by_inode.get(row[7], [])
        if (len(peer) >= 9 and peer[4] == display and peer[7] == row[5]
                and re.search(rf'\bpid={compositor_pid},', ' '.join(peer[8:]))):
            return {'display': display, 'client_inode': row[5], 'server_inode': peer[5], 'compositor_pid': compositor_pid}
    raise ProbeError(f'PID {pid} has no verified native Wayland socket connection to {display}')


def process_evidence(window, command, generation, compositor_pid, sockets):
    pid = window.get('pid')
    require(isinstance(pid, int) and pid > 0, 'Window has no process ID')
    proc = Path('/proc') / str(pid)
    require(proc.stat().st_uid == os.getuid(), 'Window process belongs to another user')
    executable = (proc / 'exe').resolve(strict=True)
    expected = (generation / 'home-path/bin' / command).resolve(strict=True)
    require(store_root(executable) == store_root(expected), f'{command} window runs a different package from the active generation')
    require(executable.name in (command, f'.{command}-wrapped'), f'Unexpected {command} executable name')
    environment = dict(item.split('=', 1) for item in (proc / 'environ').read_bytes().decode().split('\0') if '=' in item)
    display_name = environment.get('WAYLAND_DISPLAY', '')
    require(display_name, f'{command} has no Wayland display')
    display = display_name if display_name.startswith('/') else f'/run/user/{os.getuid()}/{display_name}'
    connection = wayland_peer(sockets, pid, display, compositor_pid)
    result = {'pid': pid, 'window_id': window['id'], 'app_id': window['app_id'], 'executable': str(executable),
              'generation_executable': str(expected), 'window_registered': True, 'wayland': connection}
    if command == 'ghostty':
        require(environment.get('GDK_BACKEND') == 'wayland', 'Ghostty does not explicitly select native Wayland')
        version_output = subprocess.run([str(expected), '--version'], text=True, capture_output=True, check=True, timeout=10).stdout
        match = re.search(r'Ghostty\s+(\d+)\.(\d+)\.(\d+)', version_output)
        require(match and tuple(map(int, match.groups())) >= (1, 4, 0), 'Ghostty version is older than 1.4.0 or unknown')
        result['version'] = '.'.join(match.groups())
        result['display_backend'] = 'wayland'
    require((proc / 'exe').resolve(strict=True) == executable, 'Process executable changed during probe')
    return result


def probe(args, required_windows=None):
    system = platform.machine() + '-linux'
    require(platform.system() == 'Linux' and system == args.system, f'Expected {args.system}, observed {system}')
    generation = installed_generation(args.installed_record, args.active_generation, args.revision)
    socket_path = session_socket(args.niri_socket)
    windows, compositor_pid = niri_windows(socket_path)
    sockets = subprocess.run(['ss', '-xnpH'], capture_output=True, text=True, check=True, timeout=10).stdout
    apps = {}
    for command, app_id in [('ghostty', 'com.mitchellh.ghostty'), ('moonlight', 'com.moonlight_stream.Moonlight')]:
        failures = []
        for window in windows:
            if window.get('app_id') != app_id:
                continue
            if required_windows is not None:
                expected_window = required_windows.get(command, {})
                if (window.get('id'), window.get('pid')) != (expected_window.get('id'), expected_window.get('pid')):
                    continue
            try:
                apps[command] = process_evidence(window, command, generation, compositor_pid, sockets)
                break
            except (ProbeError, OSError, ValueError, subprocess.SubprocessError) as error:
                failures.append(str(error))
        require(command in apps, f'No accepted {command} window: ' + ('; '.join(failures) or 'open the application from the launcher, then rerun'))
    # Recheck activation after collecting the UI evidence.
    require(installed_generation(args.installed_record, args.active_generation, args.revision) == generation,
            'Generation changed during probe')
    return {'passed': True, 'revision': args.revision, 'system': system, 'hostname': socket.gethostname(),
            'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'generation': str(generation),
            'niri_socket': str(socket_path), 'apps': apps,
            'scope': 'Live registered windows, active package executables and native Wayland connections; excludes visual rendering and media playback.'}


def main():
    state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--system', required=True, choices=['aarch64-linux', 'x86_64-linux'])
    parser.add_argument('--installed-record', type=Path, default=state / 'hp-os-fleet/installed.json')
    parser.add_argument('--active-generation', type=Path, default=state / 'nix/profiles/home-manager')
    parser.add_argument('--niri-socket')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = probe(args)
    except (ProbeError, OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        result = {'passed': False, 'revision': args.revision, 'system': args.system, 'hostname': socket.gethostname(), 'error': str(error)}
    payload = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(payload)
    print(payload, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
