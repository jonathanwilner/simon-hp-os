#!/usr/bin/env python3
"""Advance CI-tested revisions through registered canaries and release promotion.

Run through nom-tmux on a trusted writer. Host commands are explicit argument
arrays in private local configuration. No SSH identities ship in the fleet.
"""
import argparse
import datetime
import hashlib
import fcntl
import json
import os
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
            with urllib.request.urlopen(url, timeout=15) as response:
                downloaded = response.read(len(payload.encode()) + 1)
            if downloaded != payload.encode():
                raise ValueError('Published evidence bytes do not match accepted canary evidence')
            return url
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            last_error = error
            if attempt < 2: time.sleep(2)
    raise ValueError(f'Canary evidence publication could not be verified: {last_error}')


def promotion(release, revision, now=None):
    now = time.time() if now is None else now
    marker = release / 'promotion-requested'
    if not marker.exists():
        record = {'revision': revision, 'requested_at': now, 'attempts': 1}
        # Persist intent first. If the client disconnects after dispatch, the next
        # cycle observes Actions instead of creating a duplicate request.
        marker.write_text(json.dumps(record) + '\n')
        run(['gh', 'workflow', 'run', 'fleet-promote.yml', '--repo', REPO, '--ref', 'main', '-f', f'revision={revision}'])
        return {'state': 'waiting-for-promotion', 'revision': revision}
    value = json.loads(marker.read_text())
    # Migrate the former timestamp marker without submitting another workflow.
    record = value if isinstance(value, dict) else {'revision': revision, 'requested_at': value, 'attempts': 1}
    if record['revision'] != revision:
        raise ValueError('Promotion request marker belongs to a different revision')
    if record.get('run_id'):
        workflow = api(f'actions/runs/{record["run_id"]}')
    else:
        runs = api('actions/workflows/fleet-promote.yml/runs?event=workflow_dispatch&per_page=100')['workflow_runs']
        matches = [item for item in runs if item.get('display_title') == f'Promote fleet {revision}'
                   and item.get('head_sha') == revision and item.get('event') == 'workflow_dispatch'
                   and datetime.datetime.fromisoformat(item['created_at'].replace('Z', '+00:00')).timestamp() >= record['requested_at'] - 5]
        if not matches:
            return {'state': 'promotion-unobserved' if now - record['requested_at'] > 600 else 'waiting-for-promotion',
                    'revision': revision, 'error': 'No matching workflow run observed; inspect Actions before retrying the dispatch.'}
        workflow = min(matches, key=lambda item: item['id'])
        record['run_id'] = workflow['id']
    if (workflow.get('head_sha') != revision or workflow.get('display_title') != f'Promote fleet {revision}'
            or workflow.get('event') != 'workflow_dispatch'):
        raise ValueError('Promotion workflow identity does not match the exact requested revision')
    attempt = workflow.get('run_attempt', 1)
    requested_attempt = record.get('requested_attempt', 1)
    result = {'state': 'waiting-for-promotion', 'revision': revision, 'run_id': workflow['id'], 'url': workflow.get('html_url')}
    if attempt < requested_attempt:
        # GitHub may briefly return the completed previous attempt after rerun.
        if now - record.get('retry_at', now) > 600:
            result.update(state='promotion-unobserved', error='Requested workflow rerun was not observed; inspect Actions before retrying.')
    elif workflow.get('status') == 'completed':
        if workflow.get('conclusion') == 'success':
            record.setdefault('success_seen_at', now)
            result.update(state='promotion-ref-missing' if now - record['success_seen_at'] > 600 else 'promotion-succeeded-awaiting-ref')
        elif record['attempts'] >= 3:
            result.update(state='promotion-failed', conclusion=workflow.get('conclusion'), attempts=record['attempts'])
        elif now - record.get('retry_at', record['requested_at']) < 60:
            result.update(state='promotion-retry-backoff', conclusion=workflow.get('conclusion'))
        else:
            # Rerunning the observed run retains its exact workflow inputs and SHA.
            record.update(attempts=record['attempts'] + 1, requested_attempt=attempt + 1, retry_at=now)
            marker.write_text(json.dumps(record) + '\n')
            run(['gh', 'run', 'rerun', str(workflow['id']), '--repo', REPO])
            result.update(state='promotion-retrying', attempts=record['attempts'])
    marker.write_text(json.dumps(record) + '\n')
    return result


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
        url = publish_evidence(host, evidence, revision, system)
        print(json.dumps(evidence), flush=True)
        api(f'statuses/{revision}', {'state': 'success', 'context': 'fleet/canary/' + system,
            'description': 'Activated revision and fresh launcher acceptance passed', 'target_url': url})
    remote = run(['git', 'ls-remote', 'https://github.com/' + REPO + '.git', 'refs/heads/fleet-stable'])
    stable = remote.split()[0] if remote else None
    if stable != revision:
        return dict(promotion(release, revision), stable=stable)
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
