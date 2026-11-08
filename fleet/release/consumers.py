#!/usr/bin/env python3
"""Validate consumer updates in isolated worktrees and retry published candidates.

Run under nom-tmux. Registered checkouts are read-only source repositories.
Pending validated commits are retained under a private Git ref until publication.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

URL = 'https://github.com/jonathanwilner/simon-hp-os.git'


def run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()


def reconcile(entry, revision):
    root = Path(entry['checkout']).resolve()
    def git(*args): return run(['git', '-C', str(root), *args])
    # Preserve the previous refusal of unfinished local work. No merge or lock
    # update ever runs in this checkout, including after failed validation.
    if git('status', '--porcelain'):
        raise ValueError(f'{root}: dirty checkout; preserve pending work')
    branch = entry['branch']
    git('check-ref-format', 'refs/heads/' + branch)
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('The fleet revision must be a full commit SHA')
    flakes = entry['flakes']
    checks = entry.get('checks', [])
    if not flakes or not isinstance(flakes, list):
        raise ValueError('At least one consumer flake is required')
    if not checks or any(not isinstance(c, list) or not c or not all(isinstance(x, str) for x in c) for c in checks):
        raise ValueError('At least one nonempty validation argument array is required')
    for relative in flakes:
        if not isinstance(relative, str) or not (root / relative).resolve().is_relative_to(root):
            raise ValueError('Flake paths must remain inside their checkout')
    origin = git('remote', 'get-url', 'origin')
    identity = json.dumps({'checkout': str(root), 'origin': origin, 'branch': branch}, sort_keys=True)
    key = hashlib.sha256(identity.encode()).hexdigest()
    state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hp-os-fleet/consumers'
    state.mkdir(parents=True, exist_ok=True)
    pending_file = state / (key + '.json')
    pending_ref = 'refs/hp-os-fleet/pending-consumers/' + key
    binding = hashlib.sha256(json.dumps({'identity': identity, 'flakes': flakes, 'checks': checks,
        'input': entry.get('input', 'desktop-fleet'), 'revision': revision}, sort_keys=True).encode()).hexdigest()
    with (state / (key + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        git('fetch', 'origin', 'refs/heads/' + branch)
        base = git('rev-parse', 'FETCH_HEAD')
        pending = json.loads(pending_file.read_text()) if pending_file.exists() else None
        def clear_pending():
            git('update-ref', '-d', pending_ref)
            pending_file.unlink(missing_ok=True)
        if pending and pending.get('candidate') == base:
            clear_pending()
            # A previous push succeeded but its client lost the response.
            if pending.get('binding') == binding:
                return {'checkout': str(root), 'revision': revision, 'state': 'current', 'commit': base}
            pending = None
        candidate = None
        if pending and pending.get('binding') == binding and pending.get('base') == base:
            retained = git('rev-parse', pending_ref)
            if (retained != pending.get('candidate') or git('rev-parse', retained + '^') != base
                    or git('rev-parse', retained + '^{tree}') != pending.get('tree')):
                raise ValueError('Pending validated commit no longer matches its retained ref and base')
            candidate = retained
        if candidate is None:
            with tempfile.TemporaryDirectory(prefix='fleet-consumer-') as directory:
                checkout = Path(directory) / 'checkout'
                git('worktree', 'add', '--detach', str(checkout), base)
                try:
                    def workgit(*args): return run(['git', '-C', str(checkout), *args])
                    paths = []
                    for relative in flakes:
                        flake = (checkout / relative).resolve()
                        if not flake.is_relative_to(checkout):
                            raise ValueError('Flake path escapes the isolated checkout')
                        run(['nix', 'flake', 'lock', '--override-input', entry.get('input', 'desktop-fleet'),
                             f'github:jonathanwilner/simon-hp-os/{revision}'], cwd=flake)
                        paths.append(str((flake / 'flake.lock').relative_to(checkout)))
                    changed = workgit('diff', '--name-only').splitlines()
                    if not changed:
                        clear_pending()
                        return {'checkout': str(root), 'revision': revision, 'state': 'current', 'commit': base}
                    if set(changed) - set(paths) or workgit('ls-files', '--others', '--exclude-standard'):
                        raise ValueError('Unexpected changes outside registered lock files')
                    workgit('add', '--', *paths)
                    validated_tree = workgit('write-tree')
                    for command in checks:
                        run(command, cwd=checkout)
                    # Test commands cannot silently modify what was validated.
                    if workgit('diff', '--name-only') or workgit('write-tree') != validated_tree or workgit('ls-files', '--others', '--exclude-standard'):
                        raise ValueError('Validation changed the candidate checkout')
                    workgit('commit', '-m', f'Update tested desktop fleet to {revision[:12]}')
                    candidate = workgit('rev-parse', 'HEAD')
                    if workgit('rev-parse', 'HEAD^{tree}') != validated_tree:
                        raise ValueError('Commit does not match the validated tree')
                    # Retain before removing the temporary worktree or pushing.
                    git('update-ref', pending_ref, candidate)
                    record = {'binding': binding, 'base': base, 'candidate': candidate,
                              'tree': validated_tree, 'revision': revision}
                    temporary = pending_file.with_suffix('.tmp')
                    temporary.write_text(json.dumps(record, sort_keys=True) + '\n')
                    temporary.replace(pending_file)
                finally:
                    git('worktree', 'remove', '--force', str(checkout))
        # Fast-forward only. If another machine advances the remote, the next
        # run regenerates and validates a candidate from that newer base.
        git('push', 'origin', f'{candidate}:refs/heads/{branch}')
        clear_pending()
        return {'checkout': str(root), 'revision': revision, 'state': 'pushed', 'commit': candidate}


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
            except (ValueError, OSError, subprocess.CalledProcessError) as exc:
                results.append({'checkout': entry.get('checkout'), 'state': 'failed', 'error': str(exc)})
        print(json.dumps(results, indent=2))
        return int(any(r['state'] == 'failed' for r in results))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
