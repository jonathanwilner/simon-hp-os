#!/usr/bin/env python3
"""Reconcile disabled Actions and named fleet rulesets; --apply writes and verifies."""
import argparse
import json
from pathlib import Path
import subprocess


def api(path, method='GET', body=None):
    args = ['gh', 'api', '-H', 'X-GitHub-Api-Version: 2026-03-10', '-X', method, path]
    if body is not None:
        args += ['--input', '-']
    response = subprocess.check_output(args, input=None if body is None else json.dumps(body).encode())
    # Updating repository Actions permissions succeeds with HTTP 204.
    return json.loads(response) if response.strip() else {}


def normalized(value):
    # GitHub adds null integration IDs for contexts supplied by a personal token.
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return sorted((normalized(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def matches(actual, desired):
    return normalized({key: actual.get(key) for key in desired}) == normalized(desired)


def reconcile_actions(repo, apply=False):
    policy = Path(__file__).resolve().parents[1] / '.github/actions-policy.json'
    desired = json.loads(policy.read_text())
    if desired != {'enabled': False}:
        raise ValueError('Fleet Actions policy must explicitly disable all workflows')
    endpoint = f'repos/{repo}/actions/permissions'
    actual = api(endpoint)
    if actual.get('enabled') is not False:
        if not apply:
            print('DRIFT actions-disabled')
            return True
        api(endpoint, 'PUT', desired)
        actual = api(endpoint)
        if actual.get('enabled') is not False:
            raise RuntimeError('Read-back differs: Actions must remain disabled')
    print(f'OK actions-disabled: https://github.com/{repo}/settings/actions')
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='jonathanwilner/simon-hp-os')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    drift = reconcile_actions(args.repo, args.apply)
    endpoint = f'repos/{args.repo}/rulesets'
    existing = []
    page = 1
    while True:
        batch = api(f'{endpoint}?includes_parents=false&per_page=100&page={page}')
        existing.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    for path in sorted((Path(__file__).resolve().parents[1] / '.github/rulesets').glob('fleet-*.json')):
        desired = json.loads(path.read_text())
        found = [item for item in existing if item['name'] == desired['name']]
        if len(found) > 1:
            raise RuntimeError(f'Duplicate managed ruleset name: {desired["name"]}')
        url = f'{endpoint}/{found[0]["id"]}' if found else endpoint
        actual = api(url) if found else {}
        if not matches(actual, desired):
            if not args.apply:
                print(f'DRIFT {desired["name"]}')
                drift = True
                continue
            updated = api(url, 'PUT' if found else 'POST', desired)
            actual = api(f'{endpoint}/{updated["id"]}')
            if not matches(actual, desired):
                raise RuntimeError(f'Read-back differs: {desired["name"]}')
        print(f'OK {desired["name"]}: https://github.com/{args.repo}/rules/{actual["id"]}')
    return 1 if drift else 0


if __name__ == '__main__':
    raise SystemExit(main())
