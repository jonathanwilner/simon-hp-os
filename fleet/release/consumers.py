#!/usr/bin/env python3
"""Reconcile registered consumer lock files to the tested fleet release.

Run under nom-tmux. Configuration is local JSON; no host credentials ship here.
Each entry supplies checkout, branch, flakes, and validation argument arrays.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

URL = 'https://github.com/jonathanwilner/simon-hp-os.git'

def run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()

def reconcile(entry, revision):
    root = Path(entry['checkout']).resolve()
    def git(*args): return run(['git', '-C', str(root), *args])
    if git('status', '--porcelain'):
        raise ValueError(f'{root}: dirty checkout; preserve pending work')
    branch = entry['branch']
    if git('branch', '--show-current') != branch:
        raise ValueError(f'{root}: expected branch {branch}')
    git('fetch', 'origin', branch)
    git('merge', '--ff-only', f'origin/{branch}')
    if git('rev-parse', 'HEAD') != git('rev-parse', f'origin/{branch}'):
        raise ValueError(f'{root}: unpublished commits require explicit submission')
    paths = []
    for relative in entry['flakes']:
        flake = (root / relative).resolve()
        if not flake.is_relative_to(root):
            raise ValueError('Flake path must be inside its checkout')
        run(['nix', 'flake', 'lock', '--override-input', entry.get('input', 'desktop-fleet'),
             f'github:jonathanwilner/simon-hp-os/{revision}'], cwd=flake)
        paths.append(str((flake / 'flake.lock').relative_to(root)))
    changed = git('diff', '--name-only').splitlines()
    if not changed:
        return {'checkout': str(root), 'revision': revision, 'state': 'current'}
    if set(changed) - set(paths):
        raise ValueError('Unexpected changes outside registered lock files')
    checks = entry.get('checks', [])
    if not checks:
        raise ValueError('At least one consumer validation command is required')
    for command in checks:
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError('Checks must be nonempty argument arrays')
        run(command, cwd=root)
    git('add', '--', *paths)
    git('commit', '-m', f'Update tested desktop fleet to {revision[:12]}')
    git('push', 'origin', f'HEAD:refs/heads/{branch}')
    return {'checkout': str(root), 'revision': revision, 'state': 'pushed', 'commit': git('rev-parse', 'HEAD')}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('NOM_DASHBOARD_PROGRESS_FILE'):
        parser.error('Run through nom-tmux to track validation and publication')
    try:
        remote = run(['git', 'ls-remote', URL, 'refs/heads/fleet-stable'])
        revision = remote.split()[0] if remote else ''
        if not re.fullmatch('[0-9a-f]{40}', revision):
            raise ValueError('No tested fleet release is published')
        results = []
        for entry in json.loads(args.config.read_text())['consumers']:
            try:
                results.append(reconcile(entry, revision))
            except (ValueError, subprocess.CalledProcessError) as exc:
                results.append({'checkout': entry.get('checkout'), 'state': 'failed', 'error': str(exc)})
        print(json.dumps(results, indent=2))
        return int(any(r['state'] == 'failed' for r in results))
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
