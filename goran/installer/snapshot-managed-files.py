#!/usr/bin/env python3
"""Archive live destinations before Home Manager replaces even force=true files."""
import json
import os
from pathlib import Path
import stat
import sys
import tarfile

MAX_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 10000

def snapshot(home, managed, output):
    home, managed, output = map(Path, (home, managed, output))
    if not managed.is_dir():
        raise ValueError(f'Candidate home-files is missing: {managed}')
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    entries = {}
    total = 0

    def collect(path):
        nonlocal total
        relative = path.relative_to(home)
        if relative in entries or not os.path.lexists(path):
            return
        info = path.lstat()
        kind = 'symlink' if stat.S_ISLNK(info.st_mode) else 'directory' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'special'
        if kind == 'special':
            raise ValueError(f'Cannot safely snapshot special file: {path}')
        total += info.st_size if kind == 'file' else 0
        if len(entries) >= MAX_ENTRIES or total > MAX_BYTES:
            raise ValueError('Managed-file snapshot exceeds 10000 entries or 256 MiB; activation stopped. Preserve these files manually before retrying.')
        entries[relative] = {'path': str(relative), 'kind': kind, 'mode': stat.S_IMODE(info.st_mode)}
        if kind == 'symlink':
            entries[relative]['target'] = os.readlink(path)
        elif kind == 'directory':
            for child in sorted(path.iterdir()):
                collect(child)

    def destination(relative):
        # Preserve a symlinked parent itself. Never traverse its external target.
        cursor = home
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                collect(cursor)
                return
        collect(cursor)

    for parent, dirs, files in os.walk(managed, followlinks=False):
        base = Path(parent)
        for name in list(dirs):
            if (base / name).is_symlink():
                dirs.remove(name)
                files.append(name)
        for name in files:
            destination((base / name).relative_to(managed))
    archive = output / 'live-files.tar'
    with archive.open('xb') as stream:
        os.chmod(archive, 0o600)
        with tarfile.open(fileobj=stream, mode='w', dereference=False) as tar:
            for relative in sorted(entries):
                tar.add(home / relative, arcname=str(relative), recursive=False)
    manifest = output / 'manifest.json'
    manifest.write_text(json.dumps({'home':str(home), 'managed':str(managed), 'bytes':total,
                                    'entries':list(entries.values())}, indent=2) + '\n')
    manifest.chmod(0o600)
    return len(entries)

if __name__ == '__main__':
    try:
        count = snapshot(*sys.argv[1:])
    except (OSError, ValueError, tarfile.TarError) as error:
        sys.exit(f'Live configuration snapshot failed; activation stopped: {error}')
    print(f'Preserved {count} live configuration entries in {sys.argv[3]}/live-files.tar')
