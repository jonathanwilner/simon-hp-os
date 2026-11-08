#!/usr/bin/env python3
"""Validate revisions on owned builders, accept hardware canaries, and promote locally.

Run through nom-tmux on a trusted writer. Host commands are explicit argument
arrays in private local configuration. No SSH identities ship in the fleet.
"""
import argparse
import hashlib
import fcntl
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
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

VALIDATIONS = ('aarch64-linux', 'x86_64-linux', 'nvidia')

def head():
    return api('git/ref/heads/main')['object']['sha']

def full_revision(revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('A full commit SHA is required')

def accept_validation(evidence, revision, lane, host):
    expected_system = 'aarch64-linux' if lane == 'nvidia' else lane
    if evidence.get('revision') != revision or evidence.get('system') != expected_system:
        raise ValueError('Validation evidence is for a different revision or architecture')
    if evidence.get('source_clean') is not True:
        raise ValueError('Validation requires a clean exact-revision source checkout')
    if evidence.get('host') != host:
        raise ValueError('Validation evidence is from a different host')
    if lane == 'aarch64-linux' and host != 'dropshot':
        raise ValueError('Ordinary ARM validation must run on Dropshot')
    if lane == 'nvidia':
        if host != 'goran' or evidence.get('capability') != 'nvidia' or evidence.get('passed') is not True:
            raise ValueError('NVIDIA acceptance must pass on Goran')
    elif any(evidence.get(key) != 'passed' for key in ('evaluation', 'launcher', 'build')):
        raise ValueError('Local validation did not pass all gates')

def validate_config(config):
    if set(config.get('validation', {})) != set(VALIDATIONS):
        raise ValueError('Register ARM, x86-64 and Goran NVIDIA validation lanes')
    if config['validation']['aarch64-linux'].get('host') != 'dropshot':
        raise ValueError('Ordinary ARM validation must run on Dropshot')
    if config['validation']['nvidia'].get('host') != 'goran':
        raise ValueError('NVIDIA validation must run on Goran')
    if set(config.get('canaries', {})) != set(SYSTEMS):
        raise ValueError('Register one canary for each supported architecture')
    if config['canaries']['aarch64-linux'].get('host') != 'goran':
        raise ValueError('ARM NVIDIA desktop canary must run on Goran')
    if not config.get('checkout'):
        raise ValueError('Register the trusted promotion checkout')


def expand(argv, revision):
    if not isinstance(argv, list) or not argv or not all(isinstance(s, str) for s in argv):
        raise ValueError('Host commands must be nonempty argument arrays')
    return [s.replace('{revision}', revision) for s in argv]

def accept(evidence, revision, system):
    if evidence.get('revision') != revision or evidence.get('system') != system:
        raise ValueError('Canary evidence is for a different revision or architecture')
    if evidence.get('passed') is not True or evidence.get('fresh_launch') is not True:
        raise ValueError('Canary acceptance failed')

def publish_evidence(host, evidence, revision, system):
    payload = json.dumps(evidence, indent=2, sort_keys=True) + '\n'
    digest = hashlib.sha256(payload.encode()).hexdigest()
    session = f'fleet-canary-{revision}-{system}-{digest}'
    template = host['evidence_url']
    if '{session}' not in template:
        raise ValueError('evidence_url must contain {session} for immutable per-revision evidence')
    url = template.replace('{revision}', revision).replace('{system}', system).replace('{session}', session)
    if not url.startswith('https://'):
        raise ValueError('Canary evidence needs an HTTPS review URL')
    state = Path(os.environ.get('NOM_DASHBOARD_STATE_DIR', str(Path.home() / '.local/state/nixos-intc/nom-tmux')))
    state.mkdir(parents=True, exist_ok=True)
    log = state / (session + '.log')
    try:
        with log.open('x') as output: output.write(payload)
    except FileExistsError:
        if log.read_text() != payload:
            raise ValueError('Immutable evidence log differs from the current evidence')
    status = state / (session + '.status')
    status.write_text('0\n')
    run(['nom-dashboard-record.py', '--metadata-file', str(state / (session + '.json')),
         '--events-file', str(state / (session + '.events.jsonl')), '--session', session,
         '--safe-session', session, '--phase', 'finished', '--cwd', str(Path.cwd()),
         '--command', f'Accepted live canary {system} at {revision}', '--log-file', str(log),
         '--status-file', str(status), '--exit-code', '0'])
    command = ['nom-dashboard-sync']
    if os.environ.get('NOM_DASHBOARD_REMOTE'):
        command.append(os.environ['NOM_DASHBOARD_REMOTE'])
    last_error = None
    for attempt in range(3):
        try:
            run(command)
            request = urllib.request.Request(url, headers={'User-Agent': 'hp-os-fleet/1'})
            with urllib.request.urlopen(request, timeout=15) as response:
                downloaded = response.read(len(payload.encode()) + 1)
            if downloaded != payload.encode():
                raise ValueError('Published evidence bytes do not match accepted canary evidence')
            return url
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            last_error = error
            if attempt < 2: time.sleep(2)
    raise ValueError(f'Canary evidence publication could not be verified: {last_error}')


def promotion(config, release, revision):
    """Publish idempotently from retained exact-revision evidence, never Actions."""
    full_revision(revision)
    validate_config(config)
    for lane in VALIDATIONS:
        evidence = json.loads((release / ('validation-' + lane + '.json')).read_text())
        accept_validation(evidence, revision, lane, config['validation'][lane]['host'])
    for system in SYSTEMS:
        accept(json.loads((release / (system + '.json')).read_text()), revision, system)
    checkout = str(Path(config['checkout']).expanduser().resolve())
    git = ['git', '-C', checkout]
    run(git + ['fetch', 'origin', 'main'])
    if run(git + ['rev-parse', 'origin/main']) != revision:
        raise ValueError('Promotion requires the exact current main revision')
    stable = run(git + ['ls-remote', 'origin', 'refs/heads/fleet-stable'])
    if stable:
        run(git + ['fetch', 'origin', 'fleet-stable'])
        run(git + ['merge-base', '--is-ancestor', stable.split()[0], revision])
    tag = 'fleet-' + revision
    existing = run(git + ['ls-remote', 'origin', 'refs/tags/' + tag])
    if existing and existing.split()[0] != revision:
        raise ValueError('Immutable release tag already points elsewhere')
    # A lost client connection is safe to retry: identical refs are up to date.
    run(git + ['push', '--atomic', 'origin', f'{revision}:refs/tags/{tag}',
               f'{revision}:refs/heads/fleet-stable'])
    observed = run(git + ['ls-remote', 'origin', 'refs/heads/fleet-stable', 'refs/tags/' + tag])
    refs = {line.split()[1]: line.split()[0] for line in observed.splitlines()}
    if refs.get('refs/heads/fleet-stable') != revision or refs.get('refs/tags/' + tag) != revision:
        raise ValueError('Published release references could not be verified')
    result = {'state': 'promoted', 'revision': revision, 'tag': tag}
    (release / 'promotion.json').write_text(json.dumps(result) + '\n')
    return result


def cycle(config, state, revision=None, promote_only=False):
    validate_config(config)
    revision = revision or head()
    full_revision(revision)
    release = state / revision
    release.mkdir(parents=True, exist_ok=True)
    if promote_only:
        return promotion(config, release, revision)
    for lane in VALIDATIONS:
        host = config['validation'][lane]
        evidence_file = release / ('validation-' + lane + '.json')
        marker = release / ('validation-' + lane + '.failed')
        if evidence_file.exists():
            evidence = json.loads(evidence_file.read_text())
            accept_validation(evidence, revision, lane, host['host'])
        else:
            if marker.exists():
                raise ValueError(f'{lane}: previous validation failed; inspect {marker} and clear it to retry')
            try:
                evidence = json.loads(run(expand(host['command'], revision), env=dict(os.environ, FLEET_REVISION=revision)))
                accept_validation(evidence, revision, lane, host['host'])
                evidence_file.write_text(json.dumps(evidence, indent=2) + '\n')
            except Exception as error:
                marker.write_text(str(error) + '\n')
                raise
        url = publish_evidence(host, evidence, revision, 'validation-' + lane)
        api(f'statuses/{revision}', {'state': 'success', 'context': 'fleet/validation/' + lane,
            'description': 'Owned-host exact-revision validation passed', 'target_url': url})
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
                run(expand(host['deploy'], revision), env=env)
                evidence = json.loads(run(expand(host['probe'], revision), env=env))
                accept(evidence, revision, system)
                evidence_file.write_text(json.dumps(evidence, indent=2) + '\n')
            except Exception as error:
                marker.write_text(str(error) + '\n')
                if host.get('rollback'):
                    run(expand(host['rollback'], revision))
                raise
        url = publish_evidence(host, evidence, revision, system)
        print(json.dumps(evidence), flush=True)
        api(f'statuses/{revision}', {'state': 'success', 'context': 'fleet/canary/' + system,
            'description': 'Activated revision and fresh launcher acceptance passed', 'target_url': url})
    promotion(config, release, revision)
    results = [consumers.reconcile(entry, revision) for entry in config.get('consumers', [])]
    return {'state': 'published', 'revision': revision, 'consumers': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state', type=Path, default=Path.home() / '.local/state/hp-os-fleet/controller')
    parser.add_argument('--revision', help='Exact full main revision; defaults to current main')
    parser.add_argument('--promote-only', action='store_true', help='Promote only from retained successful local evidence')
    args = parser.parse_args()
    if not os.environ.get('NOM_DASHBOARD_PROGRESS_FILE'):
        parser.error('Run through nom-tmux')
    args.state.mkdir(parents=True, exist_ok=True)
    with (args.state / 'controller.lock').open('w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return 0
        try:
            result = cycle(json.loads(args.config.read_text()), args.state, args.revision, args.promote_only)
            (args.state / 'latest.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
            return 0
        except Exception as error:
            print(f'fleet-controller: {error}', file=sys.stderr)
            return 1

if __name__ == '__main__': sys.exit(main())
