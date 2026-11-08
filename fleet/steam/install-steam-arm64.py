#!/usr/bin/env python3
"""Install Valve's current native ARM64 beta, validating every archive hash."""
import hashlib
import json
import platform
from pathlib import Path
import re
import urllib.request
import zipfile

BASE = 'https://client-update.steamstatic.com/'
MANIFEST = 'steam_client_publicbeta_linuxarm64'
root = Path.home() / '.local/share/Steam'
cache = Path.home() / '.cache/steam-arm64-installer'
if platform.machine() not in ('aarch64', 'arm64'):
    raise SystemExit('This installer requires ARM64 Linux')
for process in Path('/proc').glob('[0-9]*/exe'):
    try:
        if process.resolve() == root / 'steamrtarm64/steam':
            raise SystemExit('Exit Steam before updating its files')
    except (OSError, RuntimeError):
        pass
root.mkdir(parents=True, exist_ok=True)
cache.mkdir(parents=True, exist_ok=True)
manifest = urllib.request.urlopen(BASE + MANIFEST, timeout=60).read()
version = re.search(rb'"version"\s+"(\d+)"', manifest).group(1).decode()
packages = re.findall(rb'"([^"\n]+)"\s*\{\s*"file"\s+"([^"\n]+)"\s*"size"\s+"(\d+)"\s*"sha2"\s+"([a-f0-9]+)"', manifest)
if not packages:
    raise RuntimeError('Valve manifest contained no verified packages')
extracted = set()
print(f'Installing native ARM64 Steam beta {version}: {len(packages)} verified archives', flush=True)
for name, filename, size, digest in packages:
    archive = cache / filename.decode()
    def valid():
        return archive.exists() and archive.stat().st_size == int(size) and hashlib.sha256(archive.read_bytes()).hexdigest() == digest.decode()
    if not valid():
        print(f'Downloading {name.decode()}: {int(size)/1000000:.1f} MB', flush=True)
        with urllib.request.urlopen(BASE + filename.decode(), timeout=120) as response, archive.open('wb') as out:
            while chunk := response.read(1024*1024):
                out.write(chunk)
    if not valid():
        raise RuntimeError(f'Invalid SHA256 or size: {archive}')
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            member.filename = member.filename.replace(chr(92), "/")
            destination = root / member.filename
            if not destination.resolve().is_relative_to(root.resolve()):
                raise RuntimeError(f'Invalid archive path: {member.filename}')
            bundle.extract(member, root)
            if not member.is_dir():
                extracted.add(destination)
            mode = member.external_attr >> 16
            if mode & 0o111:
                destination.chmod(destination.stat().st_mode | (mode & 0o111))
# Valve ZIP entries can omit Unix execute bits.
for path in extracted:
    if path.is_file():
        with path.open('rb') as stream:
            magic = stream.read(4)
        if magic == b'\x7fELF' or magic.startswith(b'#!'):
            path.chmod(path.stat().st_mode | 0o111)
(root / 'package').mkdir(exist_ok=True)
(root / 'package/beta').write_text('publicbeta')
(root / 'package' / MANIFEST).write_bytes(manifest)
(root / 'arm64-install.json').write_text(json.dumps({'version': version, 'manifest': BASE + MANIFEST, 'sha256': hashlib.sha256(manifest).hexdigest()}, indent=2)+'\n')
print(f'Installed Steam beta {version} at {root}', flush=True)
