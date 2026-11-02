#!/usr/bin/env python3
"""Input acceptance for an isolated X11-hosted Niri test session.

Supply coordinates measured from the current actual screenshot. The DND point
must be the quick-action button, and volume point must be the slider rail.
The default checks only private-bus notifications. --test-host-volume explicitly
allows a small real PipeWire change and restores the original level and mute.
"""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import time
from runtime_acceptance import command, wait_for


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('qs', 'runtime', 'xdotool', 'display', 'window', 'output'):
        p.add_argument('--' + key, required=True)
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--dnd-point', nargs=2, type=int, required=True)
    p.add_argument('--volume-point', nargs=2, type=int)
    p.add_argument('--test-host-volume', action='store_true')
    args = p.parse_args()
    if os.environ.get('INIR_SAFE_PREVIEW') != '1':
        p.error('INIR_SAFE_PREVIEW=1 and the isolated session environment required')
    if args.test_host_volume and not args.volume_point:
        p.error('--volume-point required with --test-host-volume')
    results = {'scope': 'explicit isolated graphical input', 'checks': []}
    def ipc(target, method, *values):
        return command([args.qs, 'ipc', '-p', args.runtime, 'call', target, method, *values])
    def status():
        return json.loads(ipc('hpos', 'status'))
    def input_command(*values):
        subprocess.run([args.xdotool, *map(str, values)],
                       env=dict(os.environ, DISPLAY=args.display), check=True, timeout=10)
    def click(point, button=1):
        input_command('mousemove', *point)
        time.sleep(.6)
        input_command('click', button)
    def check(name, run):
        try:
            details = run()
            results['checks'].append({'name': name, 'status': 'PASS', 'details': details})
        except Exception as error:
            results['checks'].append({'name': name, 'status': 'FAIL', 'error': str(error)})
    original_dnd = status()['doNotDisturb']
    # Verify this private bus is owned by this shell before notification mutation.
    owner = command(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus',
        '--object-path', '/org/freedesktop/DBus', '--method',
        'org.freedesktop.DBus.GetConnectionUnixProcessID', 'org.freedesktop.Notifications'])
    match = re.search(r'uint32 (\d+)', owner)
    if not match or int(match.group(1)) != args.pid:
        raise RuntimeError('Notification owner does not match the isolated shell PID')
    results['notification_owner'] = owner
    if not status()['controlCenterOpen']:
        ipc('hpos', 'controlCenter')
    time.sleep(1)
    input_command('windowfocus', args.window)
    def dnd():
        if not status()['doNotDisturb']:
            click(args.dnd_point)
            wait_for(lambda: status()['doNotDisturb'])
        count = status()['notificationCount']
        command(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.Notifications',
            '--object-path', '/org/freedesktop/Notifications', '--method',
            'org.freedesktop.Notifications.Notify', 'HP-OS QA', '0', '',
            'Control Center acceptance', 'Private test notification', '[]', '{}', '5000'])
        wait_for(lambda: status()['notificationCount'] == count + 1)
        assert status()['notificationPopups'] == 0
        return 'Real notification retained in history with no popup'
    def volume():
        def read():
            line = command(['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'])
            return float(line.split()[1]), '[MUTED]' in line
        initial, muted = read()
        if initial < .06:
            raise RuntimeError('Need nonzero initial volume to test a downward wheel step')
        try:
            click(args.volume_point, 5)
            wait_for(lambda: abs(read()[0] - initial) >= .01)
            return {'before': initial, 'after': read()[0], 'input': 'wheel down'}
        finally:
            # Allow queued UI writes to drain before restoration.
            time.sleep(2)
            command(['wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@', str(initial)])
            command(['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', '1' if muted else '0'])
            wait_for(lambda: read() == (initial, muted))
            time.sleep(1)
            assert read() == (initial, muted), 'Audio restoration did not remain stable'
    try:
        check('DND-history-and-popup-suppression', dnd)
        if args.test_host_volume:
            check('volume-wheel-and-restoration', volume)
    finally:
        if status()['doNotDisturb'] != original_dnd:
            click(args.dnd_point)
            wait_for(lambda: status()['doNotDisturb'] == original_dnd)
        Path(args.output).write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
    return int(any(c['status'] != 'PASS' for c in results['checks']))


if __name__ == '__main__':
    raise SystemExit(main())
