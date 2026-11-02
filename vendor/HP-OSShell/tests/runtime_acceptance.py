#!/usr/bin/env python3
"""Run non-hardware acceptance against an explicitly isolated HP-OS.

Inherit its private DBUS_SESSION_BUS_ADDRESS and WAYLAND_DISPLAY. Pass the
Quickshell executable, staged runtime, config JSON, shell PID and shell log.
This test never changes host audio/network/power and never captures screenshots.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time


def command(argv):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError(f'{argv[0]} exit {result.returncode}: {result.stderr[-1200:]}')
    return result.stdout.strip()


def wait_for(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.2)
    raise AssertionError('condition did not become true before timeout')


def proc_sample(pid):
    stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return {'ticks': int(stat[11]) + int(stat[12]),
            'rss_bytes': int(stat[21]) * os.sysconf('SC_PAGE_SIZE'),
            'start_ticks': int(stat[19])}


def measure_idle(pid, seconds):
    before = proc_sample(pid)
    samples = [before['rss_bytes']]
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        time.sleep(max(0, min(1, seconds - (time.monotonic() - start))))
        samples.append(proc_sample(pid)['rss_bytes'])
    after = proc_sample(pid)
    elapsed = time.monotonic() - start
    if before['start_ticks'] != after['start_ticks']:
        raise AssertionError('process identity changed during measurement')
    cpu_seconds = (after['ticks'] - before['ticks']) / os.sysconf('SC_CLK_TCK')
    return {'elapsed_seconds': round(elapsed, 3), 'cpu_seconds': round(cpu_seconds, 3),
            'cpu_percent_one_core': round(100 * cpu_seconds / elapsed, 3),
            'rss_start_bytes': samples[0], 'rss_end_bytes': samples[-1],
            'rss_min_bytes': min(samples), 'rss_max_bytes': max(samples),
            'scope': 'Quickshell process only; excludes compositor and helpers',
            'environment': 'nested compositor; not a native-session performance acceptance'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('qs','runtime','config','log','output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--pid', required=True, type=int)
    parser.add_argument('--idle-seconds', type=float, default=20)
    parser.add_argument('--expect-appearance', choices=['light','dark'])
    parser.add_argument('--expect-locale')
    args = parser.parse_args()
    if os.environ.get('INIR_SAFE_PREVIEW') != '1':
        parser.error('INIR_SAFE_PREVIEW=1 required for this harness')
    if not os.environ.get('DBUS_SESSION_BUS_ADDRESS') or not os.environ.get('WAYLAND_DISPLAY'):
        parser.error('inherit the isolated session bus and Wayland environment')
    if not 1 <= args.idle_seconds <= 55:
        parser.error('idle interval must be 1..55 seconds')
    config = Path(args.config)
    baseline = json.loads(config.read_text())
    saved = baseline.get('hpos', {}).copy()
    defaults = {'appearance':'auto','quality':'balanced','locale':'auto','reducedMotion':False,'reducedTransparency':False}
    checks = []
    result = {'scope':'isolated nested runtime', 'checks':checks, 'hardware':'UNVERIFIED',
              'visual_fidelity':'UNVERIFIED', 'restart_persistence':'UNVERIFIED'}
    log_start = Path(args.log).stat().st_size

    def ipc(target, method, *values):
        return command([args.qs, '-p', args.runtime, 'ipc', 'call', target, method, *values])

    def status():
        output = ipc('hpos','status')
        for line in reversed(output.splitlines()):
            try:
                value = json.loads(line)
                if isinstance(value, dict): return value
            except json.JSONDecodeError: pass
        raise AssertionError('HP-OS status did not return JSON: ' + output[-500:])

    def check(name, run):
        try:
            details = run()
            checks.append({'name':name,'status':'PASS','details':details})
        except Exception as error:
            checks.append({'name':name,'status':'FAIL','error':str(error)})

    def notification_roundtrip():
        owner = command(['gdbus','call','--session','--dest','org.freedesktop.DBus',
            '--object-path','/org/freedesktop/DBus','--method','org.freedesktop.DBus.GetConnectionUnixProcessID',
            'org.freedesktop.Notifications'])
        owner_match = re.search(r'uint32 (\d+)', owner)
        if not owner_match or int(owner_match.group(1)) != args.pid:
            raise AssertionError('notification service PID differs from isolated shell; refusing mutations')
        count = status()['notificationCount']
        output = command(['gdbus','call','--session','--dest','org.freedesktop.Notifications',
            '--object-path','/org/freedesktop/Notifications','--method','org.freedesktop.Notifications.Notify',
            'HP-OS acceptance','0','','HP-OS acceptance test','Real private-bus notification',
            '[]','{}','0'])
        match = re.search(r'uint32 (\d+)', output)
        if not match: raise AssertionError('Notification ID missing: ' + output)
        notification_id = match.group(1)
        wait_for(lambda: status()['notificationCount'] > count)
        # This is a dedicated test session. ClearAll tests actual shell dismissal/history.
        ipc('notifications','clearAll')
        wait_for(lambda: status()['notificationCount'] == 0)
        return {'dbus_notification_id':int(notification_id),'delivery':'observed in shell list','dismissal':'shell clearAll confirmed empty'}

    def preference(key, value, status_key=None):
        response = ipc('hpos','set',key,json.dumps(value))
        if 'false' in response.lower(): raise AssertionError('setter rejected value')
        wait_for(lambda: json.loads(config.read_text()).get('hpos',{}).get(key) == value)
        current = status()
        if status_key is not None and current.get(status_key) != value:
            raise AssertionError(f'live state differs: {current.get(status_key)}')
        return {'persisted':value,'live_status':current if status_key else ('locale persisted; glyph rendering requires visual evidence' if key == 'locale' else 'preference persisted; no separate live-status field')}

    def restart_state():
        current = status()
        expected = {'appearance': args.expect_appearance, 'locale': args.expect_locale}
        for key, value in expected.items():
            if value is None: continue
            if saved.get(key) != value: raise AssertionError(f'saved {key} differs from pre-restart expectation')
            live = ('dark' if current['dark'] else 'light') if key == 'appearance' else current.get('locale')
            if live != value: raise AssertionError(f'live {key} differs from pre-restart expectation')
        result['restart_persistence'] = 'PASS'
        return {'expected':expected,'live':current,'pid':args.pid}

    try:
        check('ipc-status',status)
        if args.expect_appearance or args.expect_locale:
            check('post-restart-saved-state',restart_state)
        check('real-dbus-notification-deliver-dismiss',notification_roundtrip)
        check('light-preference-persistence',lambda: preference('appearance','light'))
        check('light-live-state',lambda: (_ for _ in ()).throw(AssertionError('dark remained true')) if status()['dark'] else {'dark':False})
        check('dark-preference-persistence',lambda: preference('appearance','dark'))
        check('dark-live-state',lambda: {'dark':True} if status()['dark'] else (_ for _ in ()).throw(AssertionError('dark remained false')))
        check('reduced-motion',lambda: preference('reducedMotion',True,'reducedMotion'))
        check('reduced-transparency',lambda: preference('reducedTransparency',True,'reducedTransparency'))
        check('chinese-preference-persistence',lambda: preference('locale','zh_CN'))
    finally:
        for key, default in defaults.items():
            check('restore-'+key,lambda key=key, default=default: preference(key,saved.get(key,default)))
    check('idle-process-measurement',lambda: measure_idle(args.pid,args.idle_seconds))
    full_log = Path(args.log).read_bytes().decode(errors='replace')
    allocation_errors = [line for line in full_log.splitlines() if re.search(r'QImage.*(?:allocation|limit)|allocation.*(?:reject|limit)|exceeds.*256',line,re.I)]
    checks.append({'name':'full-log-image-allocation','status':'FAIL' if allocation_errors else 'PASS','errors':allocation_errors[:100]})
    result['startup_error_observations'] = [line for line in full_log.splitlines() if re.search(r'TypeError|ReferenceError|SyntaxError|Error loading|Failed to load',line)][:100]
    new_log = Path(args.log).read_bytes()[log_start:].decode(errors='replace')
    errors = [line for line in new_log.splitlines() if re.search(r'TypeError|ReferenceError|SyntaxError|Error loading|Failed to load',line)]
    checks.append({'name':'new-runtime-errors','status':'FAIL' if errors else 'PASS','errors':errors[:100]})
    result['status'] = 'FAIL' if any(c['status']=='FAIL' for c in checks) else 'PASS'
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 1 if result['status']=='FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
