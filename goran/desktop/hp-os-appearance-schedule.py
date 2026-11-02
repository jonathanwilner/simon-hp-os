#!/usr/bin/env python3
"""Apply the local sunrise/sunset mode to the running HP-OS session only."""
import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(command, **kwargs):
    return subprocess.run(command, text=True, capture_output=True, timeout=15, **kwargs)


def coordinates(latitude, longitude):
    return [f'{abs(latitude)}{"N" if latitude >= 0 else "S"}',
            f'{abs(longitude)}{"E" if longitude >= 0 else "W"}']


def solar_status(sunwait, latitude, longitude):
    coords = coordinates(latitude, longitude)
    result = run([sunwait, 'poll', 'daylight', *coords])
    if result.returncode not in (2, 3):
        raise RuntimeError('sunwait failed: ' + result.stderr)
    now = datetime.now().astimezone()
    events = []
    for offset in (0, 1):
        day = now.date() + timedelta(days=offset)
        result_list = run([sunwait, 'list', '1', 'daylight', 'd', str(day.day),
                           'm', str(day.month), 'y', str(day.year % 100), *coords], check=True)
        for name, value in zip(('sunrise', 'sunset'), result_list.stdout.strip().split(',')):
            try:
                hour, minute = map(int, value.strip().split(':'))
                # Resolve the host timezone separately for each date, including DST.
                at = datetime(day.year, day.month, day.day, hour, minute).astimezone()
            except ValueError:
                continue  # Polar day/night has no transition on this date.
            events.append({'event': name, 'at': at.isoformat()})
    future = [event for event in events if datetime.fromisoformat(event['at']) > now]
    return {'mode': 'light' if result.returncode == 2 else 'dark',
            'location': {'latitude': latitude, 'longitude': longitude},
            'checked_at': now.isoformat(), 'events': events,
            'next_transition': min(future, key=lambda item: item['at']) if future else None}


def session_identity(path):
    # /proc stat comm may contain spaces or parentheses; field 22 is starttime.
    return path.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]


def find_session(proc=Path('/proc')):
    found = []
    for path in proc.iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid != os.getuid():
                continue
            args = path.joinpath('cmdline').read_bytes().decode().split('\0')
            if not args or Path(args[0]).name not in ('qs', 'quickshell') or '-p' not in args:
                continue
            runtime = args[args.index('-p') + 1]
            if '-hp-os-runtime-' not in runtime or not runtime.endswith('/share/quickshell/inir'):
                continue
            env = dict(item.split('=', 1) for item in path.joinpath('environ').read_bytes().decode().split('\0') if '=' in item)
            if env.get('INIR_SAFE_PREVIEW') == '1' or env.get('INIR_STANDALONE_WINDOW') == '1':
                continue
            if not env.get('DBUS_SESSION_BUS_ADDRESS') or not env.get('WAYLAND_DISPLAY'):
                continue
            found.append({'pid': int(path.name), 'start': session_identity(path),
                          'executable': args[0], 'env': env, 'proc': path})
        except (OSError, ValueError, IndexError):
            continue
    if len(found) > 1:
        raise RuntimeError('Multiple HP-OS shells found; refusing an ambiguous target')
    return found[0] if found else None


def check_session(session):
    if session_identity(session['proc']) != session['start']:
        raise RuntimeError('HP-OS session changed; retry on the next timer tick')


def write_state(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as output:
        output.write(text)
        temporary = output.name
    os.replace(temporary, path)


def apply(session, status, appearance, state):
    check_session(session)
    env = dict(os.environ)
    for name in ('DBUS_SESSION_BUS_ADDRESS', 'WAYLAND_DISPLAY', 'DISPLAY', 'XDG_RUNTIME_DIR',
                 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'XDG_CURRENT_DESKTOP'):
        if name in session['env']:
            env[name] = session['env'][name]
    ipc = [session['executable'], 'ipc', '--pid', str(session['pid']), 'call', 'colorMode']
    current = json.loads(run([*ipc, 'get'], env=env, check=True).stdout)
    identity = {'pid': session['pid'], 'start': session['start'], 'mode': status['mode'],
                'publisher': str(Path(appearance).resolve())}
    try:
        previous = json.loads(state.read_text()).get('applied')
    except (OSError, ValueError):
        previous = None
    if current['mode'] != status['mode'] or previous != identity:
        check_session(session)
        if current['mode'] != status['mode']:
            run([*ipc, 'set', status['mode']], env=env, check=True)
        # Use the tested publisher on the live private bus and the user bus.
        run([appearance, status['mode']], env=env, check=True)
        check_session(session)
        owner = Path(env.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'hp-os/appearance-owner'
        # The publisher's parent is this short-lived timer, so retain shell ownership.
        write_state(owner, str(session['pid']) + '\n')
    status['applied'] = identity
    write_state(state, json.dumps(status, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latitude', type=float, required=True)
    parser.add_argument('--longitude', type=float, required=True)
    parser.add_argument('--sunwait', required=True)
    parser.add_argument('--appearance', required=True)
    parser.add_argument('--status', action='store_true', help='Report solar times and session without changes')
    args = parser.parse_args()
    status = solar_status(args.sunwait, args.latitude, args.longitude)
    session = find_session()
    status['session_pid'] = session['pid'] if session else None
    status['active'] = session is not None
    if session and not args.status:
        state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'hp-os/appearance-schedule.json'
        apply(session, status, args.appearance, state)
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    main()
