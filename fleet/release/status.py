#!/usr/bin/env python3
"""Read-only release drift report. Fetch updates refs, never the working tree."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def git(checkout, *args):
    result = subprocess.run(['git', '-C', str(checkout), *args], text=True,
                            capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'git command failed')
    return result.stdout.strip()


def item(status, **values):
    return {'status': status, **values}


def lock_revision(path, name):
    data = json.loads(Path(path).read_text())
    node = data['nodes'][data.get('root', 'root')]['inputs'][name]
    # Follow input aliases in standard flake.lock format.
    seen = set()
    while isinstance(node, list):
        key = tuple(node)
        if key in seen:
            raise ValueError('cyclic lock input alias')
        seen.add(key)
        target = data.get('root', 'root')
        for part in node:
            target = data['nodes'][target]['inputs'][part]
        node = target
    return data['nodes'][node]['locked']['rev']


def collect(args):
    result = {'schema_version': 1, 'checkout': str(args.checkout), 'checks': {}}
    checks = result['checks']
    try:
        head = git(args.checkout, 'rev-parse', 'HEAD')
        result['source_revision'] = head
        checks['working_tree'] = item('dirty' if git(args.checkout, 'status', '--porcelain') else 'clean')
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        checks['checkout'] = item('unknown', reason=str(error))
        return finish(result)
    fresh = False
    if not args.offline:
        try:
            git(args.checkout, 'fetch', '--prune', args.remote,
                '+refs/heads/*:refs/remotes/' + args.remote + '/*')
            fresh = True
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            checks['remote'] = item('unknown', reason=str(error))
    else:
        checks['remote'] = item('unknown', reason='Offline mode: remote refs may be stale')
    if fresh:
        checks['remote'] = item('current')
        unpublished = git(args.checkout, 'rev-list', '--count', 'HEAD', '--not', '--remotes=' + args.remote)
        checks['publication'] = item('unpushed' if int(unpublished) else 'published', commits=int(unpublished))
    else:
        checks['publication'] = item('unknown', reason='Remote refs were not refreshed')
    stable = None
    release_fresh = fresh
    release_ref = 'refs/remotes/' + args.remote + '/fleet-stable'
    if args.release_url:
        release_ref = 'refs/remotes/fleet-release/fleet-stable'
        release_fresh = False
        if not args.offline:
            try:
                git(args.checkout, 'fetch', args.release_url, '+refs/heads/fleet-stable:' + release_ref)
                release_fresh = True
            except (RuntimeError, OSError, subprocess.TimeoutExpired):
                pass
    try:
        stable = git(args.checkout, 'rev-parse', '--verify', release_ref + '^{commit}')
    except RuntimeError:
        pass
    result['release_revision'] = stable
    try:
        configured = lock_revision(args.consumer_lock, args.input) if args.consumer_lock else head
        result['configured_fleet_revision'] = configured
        if not release_fresh or not stable:
            checks['release_pin'] = item('unknown', reason='No fresh fleet-stable release available', configured=configured)
        else:
            checks['release_pin'] = item('current' if configured == stable else 'differs', configured=configured, release=stable)
    except (OSError, ValueError, KeyError, TypeError) as error:
        configured = None
        checks['release_pin'] = item('unknown', reason=str(error))
    try:
        record_path = args.installed_record
        if record_path.is_dir():
            source = (record_path / 'source-revision').read_text().strip()
            fleet_file = record_path / 'fleet-revision'
            if not fleet_file.exists():
                fleet_file = record_path / 'published-revision'
            fleet = fleet_file.read_text().strip() if fleet_file.exists() else source
            record = {'source_revision': source, 'fleet_revision': fleet,
                      'generation': str((record_path / 'candidate').resolve(strict=True))}
        else:
            record = json.loads(record_path.read_text())
        generation = str(Path(record['generation']).resolve(strict=True))
        active = str(args.active_generation.resolve(strict=True))
        installed = record['fleet_revision'] if args.consumer_lock else record['source_revision']
        result['installed'] = record
        if generation != active:
            checks['activation'] = item('unknown', reason='Active generation differs from activation record', recorded=generation, active=active)
        elif not configured:
            checks['activation'] = item('unknown', reason='Configured fleet revision unavailable', installed=installed)
        else:
            checks['activation'] = item('current' if installed == configured else 'pending', installed=installed, configured=configured, generation=active)
    except (OSError, ValueError, KeyError, TypeError) as error:
        checks['activation'] = item('unknown', reason=str(error))
    return finish(result)


def finish(result):
    states = [value['status'] for value in result['checks'].values()]
    result['status'] = ('attention' if any(s in {'dirty', 'unpushed', 'differs', 'pending'} for s in states)
                        else 'unknown' if 'unknown' in states else 'current')
    return result


def main():
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, default=Path.cwd())
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--release-url', default='https://github.com/jonathanwilner/simon-hp-os.git',
                        help='Fleet repository URL; empty string uses origin fleet-stable')
    parser.add_argument('--consumer-lock', type=Path)
    parser.add_argument('--input', default='desktop-fleet')
    parser.add_argument('--installed-record', type=Path, default=state / 'hp-os-fleet/installed.json')
    parser.add_argument('--active-generation', type=Path, default=state / 'nix/profiles/home-manager')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--check', action='store_true', help='Exit 1 for drift, 2 for unknown evidence')
    args = parser.parse_args()
    report = collect(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print('Fleet release status: ' + report['status'])
        for name, check in report['checks'].items():
            details = ', '.join(f'{key}={value}' for key, value in check.items() if key != 'status')
            print(f"  {name}: {check['status']}" + (f' ({details})' if details else ''))
    return {'current': 0, 'attention': 1, 'unknown': 2}[report['status']] if args.check else 0


if __name__ == '__main__':
    sys.exit(main())
