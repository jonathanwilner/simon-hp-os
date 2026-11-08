#!/usr/bin/env python3
"""Advance CI-tested revisions through registered canaries and release promotion.

Run through nom-tmux on a trusted writer. Host commands are explicit argument
arrays in private local configuration. No SSH identities ship in the fleet.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import consumers

REPO = 'jonathanwilner/simon-hp-os'
SYSTEMS = ('aarch64-linux', 'x86_64-linux')

def run(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, stdout=subprocess.PIPE, **kwargs).stdout.strip()

def api(path, payload=None):
    command = ['gh', 'api', f'repos/{REPO}/{path}']
    if payload is not None:
        command += ['--method', 'POST', '--input', '-']
    return json.loads(run(command, input=json.dumps(payload) if payload else None) or '{}')

def tested_head():
    revision = api('git/ref/heads/main')['object']['sha']
    runs = api(f'actions/workflows/fleet-validation.yml/runs?head_sha={revision}&event=push&per_page=100')['workflow_runs']
    matching = [r for r in runs if r['head_sha'] == revision and r['head_branch'] == 'main' and r['event'] == 'push']
    latest = max(matching, key=lambda r: r['id']) if matching else {}
    if latest.get('conclusion') != 'success':
        return revision, None
    return revision, latest

def expand(argv, revision):
    if not isinstance(argv, list) or not argv or not all(isinstance(s, str) for s in argv):
        raise ValueError('Host commands must be nonempty argument arrays')
    return [s.replace('{revision}', revision) for s in argv]

def accept(evidence, revision, system):
    if evidence.get('revision') != revision or evidence.get('system') != system:
        raise ValueError('Canary evidence is for a different revision or architecture')
    if evidence.get('passed') is not True or evidence.get('fresh_launch') is not True:
        raise ValueError('Canary acceptance failed')

def cycle(config, state):
    revision, ci = tested_head()
    if ci is None:
        return {'state': 'waiting-for-ci', 'revision': revision}
    if set(config['canaries']) != set(SYSTEMS):
        raise ValueError('Register one canary for each supported architecture')
    release = state / revision
    release.mkdir(parents=True, exist_ok=True)
    for system in SYSTEMS:
        host = config['canaries'][system]
        evidence_file = release / (system + '.json')
        if evidence_file.exists():
            evidence = json.loads(evidence_file.read_text())
            accept(evidence, revision, system)
        else:
            marker = release / (system + '.failed')
            if marker.exists():
                raise ValueError(f'{system}: previous attempt failed; inspect {marker} and clear it to retry')
            try:
                consumers.reconcile(host['consumer'], revision)
                env = dict(os.environ, FLEET_REVISION=revision)
                # Commands must return only after the host deployment/launch test finishes.
                # The whole controller is already tracked in nom-tmux.
                run(expand(host['deploy'], revision), env=env)
                evidence = json.loads(run(expand(host['probe'], revision), env=env))
                accept(evidence, revision, system)
                evidence_file.write_text(json.dumps(evidence, indent=2) + '\n')
            except Exception as error:
                marker.write_text(str(error) + '\n')
                if host.get('rollback'):
                    run(expand(host['rollback'], revision))
                raise
        url = host['evidence_url'].replace('{revision}', revision)
        if not url.startswith('https://'):
            raise ValueError('Canary evidence needs an authenticated or public HTTPS review URL')
        print(json.dumps(evidence), flush=True)
        api(f'statuses/{revision}', {'state': 'success', 'context': 'fleet/canary/' + system,
            'description': 'Activated revision and fresh launcher acceptance passed', 'target_url': url})
    marker = release / 'promotion-requested'
    if not marker.exists():
        run(['gh', 'workflow', 'run', 'fleet-promote.yml', '--repo', REPO, '--ref', 'main', '-f', f'revision={revision}'])
        marker.write_text(str(int(time.time())) + '\n')
    remote = run(['git', 'ls-remote', 'https://github.com/' + REPO + '.git', 'refs/heads/fleet-stable'])
    stable = remote.split()[0] if remote else None
    if stable != revision:
        return {'state': 'waiting-for-promotion', 'revision': revision, 'stable': stable}
    results = [consumers.reconcile(entry, revision) for entry in config.get('consumers', [])]
    return {'state': 'published', 'revision': revision, 'consumers': results}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state', type=Path, default=Path.home() / '.local/state/hp-os-fleet/controller')
    args = parser.parse_args()
    if not os.environ.get('NOM_DASHBOARD_PROGRESS_FILE'):
        parser.error('Run through nom-tmux')
    args.state.mkdir(parents=True, exist_ok=True)
    with (args.state / 'controller.lock').open('w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return 0
        try:
            result = cycle(json.loads(args.config.read_text()), args.state)
            (args.state / 'latest.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
            return 0
        except Exception as error:
            print(f'fleet-controller: {error}', file=sys.stderr)
            return 1

if __name__ == '__main__': sys.exit(main())
