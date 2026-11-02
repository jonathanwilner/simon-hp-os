#!/usr/bin/env python3
"""Pin the latest stable GitHub release and published SHA-256 for each app."""
import argparse
import base64
import json
import os
from pathlib import Path
import urllib.request

NAMES = ['photocraft', 'vectorcraft', 'filmcraft', 'lightcraft', 'pdfcraft', 'effectcraft', 'designcraft']

def fetch(url):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'artcraft-nix-update'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
        return response.read()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='report changes without writing')
    args = parser.parse_args()
    result = {}
    for name in NAMES:
        release = json.loads(fetch(f'https://api.github.com/repos/storytold/{name}/releases/latest'))
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
    target = Path(__file__).with_name('versions.json')
    rendered = json.dumps(result, indent=2) + '\n'
    if args.check:
        if not target.exists() or target.read_text() != rendered:
            raise SystemExit('Updates available: run update.py and rebuild before deployment.')
        print('All pins match the latest stable releases.')
    else:
        target.write_text(rendered)

if __name__ == '__main__':
    main()
