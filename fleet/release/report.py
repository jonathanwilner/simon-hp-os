#!/usr/bin/env python3
"""Persist a bounded fleet drift report for periodic desktop dashboard tasks."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

import status


def refresh_remote(args, report):
    checks = report['checks']
    try:
        heads = status.git(args.checkout, 'ls-remote', '--heads', args.remote)
        remote_heads = dict(line.split()[::-1] for line in heads.splitlines() if line.strip())
        head = report['source_revision']
        if head in remote_heads.values():
            checks['publication'] = status.item('published', commits=0)
        else:
            branch = status.git(args.checkout, 'symbolic-ref', '--quiet', '--short', 'HEAD')
            tracking_remote = status.git(args.checkout, 'config', '--get', f'branch.{branch}.remote')
            tracking_ref = status.git(args.checkout, 'config', '--get', f'branch.{branch}.merge')
            if tracking_remote != args.remote or tracking_ref not in remote_heads:
                raise ValueError('No matching remote upstream branch to verify publication')
            # Fetch only the configured upstream, never every historical branch.
            status.git(args.checkout, 'fetch', '--no-tags', args.remote, tracking_ref)
            count = int(status.git(args.checkout, 'rev-list', '--count', 'HEAD', '--not', 'FETCH_HEAD'))
            checks['publication'] = status.item('unpushed' if count else 'published', commits=count,
                                                upstream=tracking_ref)
        checks['remote'] = status.item('current')
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        checks['remote'] = status.item('unknown', reason=str(error))
        checks['publication'] = status.item('unknown', reason=str(error))
    try:
        lines = status.git(args.checkout, 'ls-remote', '--exit-code', args.release_url or args.remote,
                           'refs/heads/fleet-stable').splitlines()
        stable = lines[0].split()[0]
        configured = report.get('configured_fleet_revision')
        report['release_revision'] = stable
        checks['release_pin'] = (status.item('current' if configured == stable else 'differs',
                                            configured=configured, release=stable) if configured
                                 else status.item('unknown', reason='Configured fleet revision unavailable'))
    except (RuntimeError, OSError, IndexError, subprocess.TimeoutExpired) as error:
        report['release_revision'] = None
        checks['release_pin'] = status.item('unknown', reason=str(error))


def generic_activation(args, report):
    """Support the fleet HM marker, which intentionally lacks consumer source SHA."""
    if args.consumer_lock or args.installed_record.is_dir():
        return
    try:
        record = json.loads(args.installed_record.read_text())
        if 'source_revision' in record:
            return
        active = str(args.active_generation.resolve(strict=True))
        recorded = str(Path(record['generation']).resolve(strict=True))
        installed = record['fleet_revision']
        configured = report.get('configured_fleet_revision')
        report['installed'] = record
        if active != recorded:
            check = status.item('unknown', reason='Active generation differs from activation record',
                                active=active, recorded=recorded)
        elif not configured or installed == 'unknown':
            check = status.item('unknown', reason='Fleet revision unavailable')
        else:
            check = status.item('current' if installed == configured else 'pending', installed=installed,
                                configured=configured, generation=active)
        report['checks']['activation'] = check
    except (OSError, ValueError, KeyError, TypeError):
        # collect() already records the reason for unusable installation evidence.
        pass


def collect(args):
    offline = args.offline
    # Reuse local inspection, while avoiding status.collect's all-branches fetch.
    local = argparse.Namespace(**vars(args))
    local.offline = True
    report = status.collect(local)
    generic_activation(args, report)
    if not offline and 'source_revision' in report:
        refresh_remote(args, report)
    status.finish(report)
    report['observed_at'] = datetime.now(timezone.utc).isoformat()
    report['machine'] = socket.gethostname()
    return report


def persist(report, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + output.name + '.', dir=output.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def announce(report, output):
    checks = report['checks']
    print(f"Fleet release: {report['status']} ({report['machine']}, {report['observed_at']})", flush=True)
    for name, check in checks.items():
        details = ', '.join(f'{key}={value}' for key, value in check.items() if key != 'status')
        print(f"  {name}: {check['status']}" + (f' ({details})' if details else ''), flush=True)
    print(f'Atomic status report: {output}', flush=True)
    progress = shutil.which('nom-dashboard-progress')
    if progress and os.environ.get('NOM_DASHBOARD_PROGRESS_FILE'):
        summary = ', '.join(f"{key}: {value['status']}" for key, value in checks.items())
        # This measures completed observations, never percentage deployment success.
        subprocess.run([progress, '--completed', str(len(checks)), '--total', str(len(checks)),
                        '--unit', 'checks', '--label', f"Fleet {report['status']}: {summary}"],
                       check=False, timeout=15)


def main():
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--consumer-lock', type=Path)
    parser.add_argument('--input', default='desktop-fleet')
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--release-url', default='https://github.com/jonathanwilner/simon-hp-os.git')
    parser.add_argument('--installed-record', type=Path, default=state / 'hp-os-fleet/installed.json')
    parser.add_argument('--active-generation', type=Path, default=state / 'nix/profiles/home-manager')
    parser.add_argument('--output', type=Path, default=state / 'hp-os-fleet/latest-report.json')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    report = collect(args)
    persist(report, args.output)
    announce(report, args.output)
    return {'current': 0, 'attention': 1, 'unknown': 2}[report['status']]


if __name__ == '__main__':
    sys.exit(main())
