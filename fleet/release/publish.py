#!/usr/bin/env python3
"""Submit clean shared changes and request a verified fleet release."""
import argparse
import json
import pathlib
import os
import platform
import time
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

def install_hook(root):
    origin = git(root, 'remote', 'get-url', 'origin')
    if origin not in (f'https://github.com/{REPO}.git', f'https://github.com/{REPO}', f'git@github.com:{REPO}.git'):
        raise ValueError('Automatic shared submission requires the public fleet origin')
    hook = pathlib.Path(git(root, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks/post-commit'))
    hook.parent.mkdir(parents=True, exist_ok=True)
    marker = '# hp-os-fleet-submit-v1'
    text = hook.read_text() if hook.exists() else '#!/bin/sh\n'
    if marker in text:
        print('Fleet submission hook already installed')
        return
    command = ' '.join(shlex.quote(v) for v in [sys.executable, str(pathlib.Path(__file__).resolve()), 'submit', '--checkout'])
    text += '\n' + marker + '\n' + '''
# Publish only completed commits on main. Feature branches remain explicit submissions.
if [ "$(git branch --show-current)" = main ]; then
  fleet_root=$(git rev-parse --show-toplevel)
  fleet_state="${XDG_STATE_HOME:-$HOME/.local/state}/hp-os-fleet"
  mkdir -p "$fleet_state"
  (unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE; nohup ''' + command + ''' "$fleet_root" >> "$fleet_state/submit.log" 2>&1 </dev/null &)
fi
'''
    hook.write_text(text)
    hook.chmod(hook.stat().st_mode | 0o111)
    print(f'Installed main-branch post-commit validation and publication hook: {hook}')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('submit', help='Push clean shared commits to main for mandatory CI')
    p.add_argument('--checkout', type=pathlib.Path, default=pathlib.Path.cwd())
    p = sub.add_parser('install-hook', help='Automatically validate and submit commits made on main')
    p.add_argument('--checkout', type=pathlib.Path, default=pathlib.Path.cwd())
    p = sub.add_parser('promote', help='Request gated release promotion after canary acceptance')
    p.add_argument('revision')
    args = parser.parse_args()
    try:
        if args.command == 'submit': submit(args.checkout)
        elif args.command == 'install-hook': install_hook(args.checkout)
        else: promote(args.revision)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f'fleet-publish: {exc}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
