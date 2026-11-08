#!/usr/bin/env python3
"""Promote only an exact, CI-tested and hardware-accepted main revision."""
import json, os, re, subprocess, sys

def gh(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))

def validate(revision, runs, statuses):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('A full commit SHA is required')
    matching = [r for r in runs if r['head_sha'] == revision and r['event'] == 'push' and r['head_branch'] == 'main']
    if not matching or max(matching, key=lambda r: r['id'])['conclusion'] != 'success':
        raise ValueError('Latest exact-revision Fleet validation push run must succeed')
    latest = {}
    for status in sorted(statuses, key=lambda s: s['id'], reverse=True):
        latest.setdefault(status['context'], status)
    for system in ('aarch64-linux', 'x86_64-linux'):
        status = latest.get('fleet/canary/' + system, {})
        if status.get('state') != 'success' or not status.get('target_url', '').startswith('https://'):
            raise ValueError('Missing successful canary acceptance with evidence: ' + system)

def main():
    revision = sys.argv[1]
    repo = os.environ['GITHUB_REPOSITORY']
    runs = gh(f'repos/{repo}/actions/workflows/fleet-validation.yml/runs?head_sha={revision}&event=push&per_page=100')['workflow_runs']
    # Combined status endpoint reports latest status for every context.
    statuses = gh(f'repos/{repo}/commits/{revision}/status')['statuses']
    validate(revision, runs, statuses)
    subprocess.run(['git', 'fetch', 'origin', 'main'], check=True)
    subprocess.run(['git', 'merge-base', '--is-ancestor', revision, 'origin/main'], check=True)
    stable = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/fleet-stable'], text=True).strip()
    if stable:
        subprocess.run(['git', 'fetch', 'origin', 'fleet-stable'], check=True)
        subprocess.run(['git', 'merge-base', '--is-ancestor', stable.split()[0], revision], check=True)
    tag = 'fleet-' + revision
    existing = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/tags/' + tag], text=True).strip()
    if existing and existing.split()[0] != revision:
        raise ValueError('Immutable release tag already points elsewhere')
    # Atomic publication prevents a release branch without its immutable tag.
    subprocess.run(['git', 'push', '--atomic', 'origin', f'{revision}:refs/tags/{tag}', f'{revision}:refs/heads/fleet-stable'], check=True)
    print(json.dumps({'revision': revision, 'tag': tag, 'channel': 'fleet-stable'}))

if __name__ == '__main__':
    main()
