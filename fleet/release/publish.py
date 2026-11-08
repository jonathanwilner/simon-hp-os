#!/usr/bin/env python3
"""Submit clean shared changes and request a verified fleet release."""
import argparse
import fcntl
import hashlib
import json
import pathlib
import os
import platform
import time
import tempfile
import shlex
import re
import subprocess
import sys

REPO = 'jonathanwilner/simon-hp-os'

def run(*args, cwd=None, capture=True):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout

def git(root, *args):
    return run('git', '-C', str(root), *args).strip()

def validate(root):
    system = {'aarch64': 'aarch64-linux', 'x86_64': 'x86_64-linux'}.get(platform.machine())
    if not system:
        raise ValueError('Fleet validation requires a supported Linux build host')
    if not (root / 'tests/release/validate.sh').is_file():
        raise ValueError('The shared release validation script is missing')
    session = 'fleet-submit'
    state = pathlib.Path(os.environ.get('NOM_DASHBOARD_STATE_DIR',
        str(pathlib.Path.home() / '.local/state/nixos-intc/nom-tmux')))
    status = state / (session + '.status')
    # Refuse an existing job before removing a previous result.
    if subprocess.run(['tmux', 'has-session', '-t', '=' + session],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        raise ValueError('A fleet submission validation is already running')
    status.unlink(missing_ok=True)
    run('nom-tmux', session, '--', 'bash', 'tests/release/validate.sh', system, cwd=root, capture=False)
    while not status.exists():
        time.sleep(15)
        if subprocess.run(['tmux', 'has-session', '-t', '=' + session],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode and not status.exists():
            raise ValueError('Validation stopped without a result; inspect the tracked log')
    if status.read_text().strip() != '0':
        raise ValueError('Validation failed; inspect the fleet-submit dashboard log')

def submit(root):
    if git(root, 'status', '--porcelain'):
        raise ValueError('Commit the intended files first. The checkout must be clean.')
    origin = git(root, 'remote', 'get-url', 'origin')
    if origin not in (f'https://github.com/{REPO}.git', f'https://github.com/{REPO}',
                      f'git@github.com:{REPO}.git'):
        raise ValueError('Submit shared changes from the public fleet repository.')
    git(root, 'fetch', 'origin', 'main')
    git(root, 'merge-base', '--is-ancestor', 'origin/main', 'HEAD')
    revision = git(root, 'rev-parse', 'HEAD')
    validate(root)
    if git(root, 'rev-parse', 'HEAD') != revision or git(root, 'status', '--porcelain'):
        raise ValueError('Source changed during validation; submit again')
    # A fast-forward push cannot silently discard another machine's commits.
    git(root, 'push', 'origin', 'HEAD:refs/heads/main')
    print(json.dumps({'revision': revision, 'state': 'submitted',
                      'checks': f'https://github.com/{REPO}/actions'}))
    return revision

def promote(revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Use the full tested commit SHA.')
    run('gh', 'workflow', 'run', 'fleet-promote.yml', '--repo', REPO,
        '--ref', 'main', '-f', f'revision={revision}')
    print('Promotion requested. The workflow checks CI and both canary results before publishing.')

def drain(root):
    """Queue HEAD before waiting; retry only a new revision after a failed build."""
    root = root.resolve()
    key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    state = pathlib.Path(os.environ.get('XDG_STATE_HOME', str(pathlib.Path.home() / '.local/state'))) / 'hp-os-fleet' / key
    state.mkdir(parents=True, exist_ok=True)
    request = state / 'requested-revision'
    result_file = state / 'last-attempt.json'
    with tempfile.NamedTemporaryFile(mode='w', dir=state, delete=False) as stream:
        stream.write(git(root, 'rev-parse', 'HEAD') + '\n')
        temporary = pathlib.Path(stream.name)
    temporary.replace(request)
    with (state / 'worker.lock').open('a') as lock:
        # Blocking rather than dropping an invocation closes the race between a
        # worker's final queue read and another commit arriving before unlock.
        fcntl.flock(lock, fcntl.LOCK_EX)
        while True:
            if git(root, 'branch', '--show-current') != 'main':
                print('Queued automatic submission waits for main; feature branches require explicit submit.')
                return False
            revision = git(root, 'rev-parse', 'HEAD')
            if result_file.exists():
                previous = json.loads(result_file.read_text())
                if previous.get('revision') == revision:
                    print(f'Automatic submission already attempted {revision}: {previous["state"]}. Use submit to retry explicitly.')
                    return previous['state'] == 'submitted'
            try:
                submitted = submit(root)
                result = {'revision': revision, 'state': 'submitted', 'submitted_revision': submitted}
            except (ValueError, subprocess.CalledProcessError, OSError) as error:
                result = {'revision': revision, 'state': 'failed', 'error': str(error)}
            with tempfile.NamedTemporaryFile(mode='w', dir=state, delete=False) as stream:
                stream.write(json.dumps(result) + '\n')
                result_temporary = pathlib.Path(stream.name)
            result_temporary.replace(result_file)
            print(json.dumps(result))
            # A commit arriving during validation must get its own validation.
            # An unchanged failed source is retained for status, never busy-retried.
            if git(root, 'rev-parse', 'HEAD') == revision:
                return result['state'] == 'submitted'


def install_hook(root):
    allowed = (f'https://github.com/{REPO}.git', f'https://github.com/{REPO}', f'git@github.com:{REPO}.git')
    origin = git(root, 'remote', 'get-url', 'origin')
    if origin not in allowed:
        raise ValueError('Automatic shared submission requires the public fleet origin')
    hook = pathlib.Path(git(root, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks')) / 'post-commit'
    hook.parent.mkdir(parents=True, exist_ok=True)
    marker = b'#!/bin/sh\n# hp-os-fleet-submit-v2\n'
    backup = hook.with_name('post-commit.hp-os-fleet-original')
    previous = backup
    temporary = hook.with_name('post-commit.hp-os-fleet-new')
    if temporary.exists() or temporary.is_symlink():
        raise ValueError(f'Incomplete hook installation requires review: {temporary}')
    existing = hook.read_bytes() if hook.exists() else b''
    managed = existing.startswith(marker)
    if not managed and (hook.exists() or hook.is_symlink()):
        if backup.exists() or backup.is_symlink():
            raise ValueError(f'Preserve or reconcile the existing hook backup before installing: {backup}')
        # Rename preserves arbitrary executable bytes, mode and symlink identity.
        hook.rename(backup)
        legacy_marker = b'\n# hp-os-fleet-submit-v1\n'
        if legacy_marker in existing:
            # The old installer appended its own shell block. Keep the complete
            # backup, but execute only its preceding user hook to avoid submitting twice.
            previous = hook.with_name('post-commit.hp-os-fleet-legacy-user')
            if previous.exists() or previous.is_symlink():
                backup.rename(hook)
                raise ValueError(f'Existing legacy hook recovery file requires review: {previous}')
            previous.write_bytes(existing.rsplit(legacy_marker, 1)[0] + b'\n')
            previous.chmod(backup.stat().st_mode)
    elif managed:
        legacy = hook.with_name('post-commit.hp-os-fleet-legacy-user')
        if legacy.exists():
            previous = legacy
    command = ' '.join(shlex.quote(v) for v in [sys.executable, str(pathlib.Path(__file__).resolve()), 'drain', '--checkout'])
    allowed_shell = '|'.join(shlex.quote(value) for value in allowed)
    text = marker.decode() + f'''# The original hook runs in its own process, so its exit cannot bypass submission.
fleet_previous_status=0
if [ -x {shlex.quote(str(previous))} ]; then
  {shlex.quote(str(previous))} "$@" || fleet_previous_status=$?
fi
# Recheck origin on every commit; hooks can be shared by Git worktrees.
case "$(git remote get-url origin 2>/dev/null)" in
  {allowed_shell})
    if [ "$(git branch --show-current)" = main ]; then
      fleet_root=$(git rev-parse --show-toplevel) || exit 1
      fleet_state="${{XDG_STATE_HOME:-$HOME/.local/state}}/hp-os-fleet"
      mkdir -p "$fleet_state" || exit 1
      (unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE; nohup {command} "$fleet_root" >> "$fleet_state/submit.log" 2>&1 </dev/null &)
    fi
    ;;
esac
exit "$fleet_previous_status"
'''
    # Atomic replacement keeps concurrent commits from observing a partial hook.
    try:
        with temporary.open('x') as stream:
            stream.write(text)
        temporary.chmod(0o755)
        temporary.replace(hook)
    except BaseException:
        if not managed and backup.exists() and not hook.exists():
            backup.rename(hook)
        raise
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Installed main-branch post-commit validation and publication hook: {hook}')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('submit', help='Push clean shared commits to main for mandatory CI')
    p.add_argument('--checkout', type=pathlib.Path, default=pathlib.Path.cwd())
    p = sub.add_parser('drain', help='Process queued main-branch commits without dropping concurrent changes')
    p.add_argument('--checkout', type=pathlib.Path, default=pathlib.Path.cwd())
    p = sub.add_parser('install-hook', help='Automatically validate and submit commits made on main')
    p.add_argument('--checkout', type=pathlib.Path, default=pathlib.Path.cwd())
    p = sub.add_parser('promote', help='Request gated release promotion after canary acceptance')
    p.add_argument('revision')
    args = parser.parse_args()
    try:
        if args.command == 'submit': submit(args.checkout)
        elif args.command == 'drain':
            if not drain(args.checkout): return 1
        elif args.command == 'install-hook': install_hook(args.checkout)
        else: promote(args.revision)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f'fleet-publish: {exc}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
