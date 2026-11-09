#!/usr/bin/env python3
"""Pin the latest stable GitHub release and published SHA-256 for each app."""
import argparse
import base64
import json
import os
import re
from pathlib import Path
import urllib.request

CATALOG_URL = 'https://raw.githubusercontent.com/storytold/craft-launcher/main/crates/core/src/catalog.rs'

def discover():
    # Read data only: never execute downloaded Rust. Restrict installation to the
    # official publisher. Community applications require a separate review.
    source = fetch(CATALOG_URL).decode().split('pub const SUITE:', 1)[1].split('];', 1)[0]
    names = sorted(set(re.findall(r'"storytold/([a-z][a-z0-9-]+)"', source)))
    if not names:
        raise ValueError('Official catalog format changed; refusing an empty catalog')
    return names


def fetch(url):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'artcraft-nix-update'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
        return response.read()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='report changes without writing')
    parser.add_argument('--catalog', action='store_true', help='discover official apps without changing selected apps')
    parser.add_argument('--add', action='append', default=[], metavar='APP', help='explicitly select a newly discovered app (repeatable)')
    parser.add_argument('--versions', type=Path, default=Path(__file__).with_name('versions.json'))
    parser.add_argument('--report', action='store_true', help='report versions and new apps; do not download binaries or change pins')
    args = parser.parse_args()
    target = args.versions
    selected = json.loads(target.read_text())
    catalog = discover() if args.catalog or args.add or args.report else []
    if args.add and (args.check or args.report or args.catalog):
        parser.error('--add cannot be combined with read-only modes')
    for name in args.add:
        if name not in catalog:
            parser.error('Not in the official catalog: ' + name)
    if args.catalog or args.report:
        print('New apps available to choose: ' + (', '.join(n for n in catalog if n not in selected) or 'none'))
        if args.catalog:
            print('Selected apps: ' + ', '.join(sorted(selected)))
            return
    result = {}
    for name in sorted(set(selected) | set(args.add)):
        release = json.loads(fetch(f'https://api.github.com/repos/storytold/{name}/releases/latest'))
        if args.report:
            latest = release['tag_name'].removeprefix('v')
            print(f"{name}: selected {selected[name]['version']}; latest {latest}")
            continue
        assets = {a['name']: a for a in release['assets']}
        sums = {}
        for line in fetch(assets['SHA256SUMS.txt']['browser_download_url']).decode().splitlines():
            digest, filename = line.split(maxsplit=1)
            sums[filename.lstrip('*')] = digest
        version = release['tag_name'].removeprefix('v')
        entry = {'version': version, 'tag': release['tag_name'], 'release': release['html_url'], 'assets': {}}
        for key, filename in [('web', f'{name}-web-{version}.zip')] + [
            (system, f'{name}-{version}-linux-{arch}.tar.gz')
            for system, arch in [('x86_64-linux', 'x86_64'), ('aarch64-linux', 'aarch64')]
        ]:
            asset = assets[filename]
            digest = sums[filename]
            if len(digest) != 64:
                raise ValueError('Invalid SHA-256 for ' + filename)
            entry['assets'][key] = {'url': asset['browser_download_url'], 'hash': 'sha256-' + base64.b64encode(bytes.fromhex(digest)).decode()}
        result[name] = entry
        print(f'{name}: {version}')
    if args.report:
        return
    rendered = json.dumps(result, indent=2) + '\n'
    if args.check:
        if not target.exists() or target.read_text() != rendered:
            raise SystemExit('Updates available: run update.py and rebuild before deployment.')
        print('All pins match the latest stable releases.')
    else:
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(rendered)
        temporary.replace(target)

if __name__ == '__main__':
    main()
