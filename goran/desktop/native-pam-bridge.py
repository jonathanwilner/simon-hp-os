#!/usr/bin/env python3
"""Expose Ubuntu PAM libraries to the HP-OS process without exposing host Qt."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

EXCLUDE = {"libc.so.6", "libm.so.6", "libpthread.so.0", "libdl.so.2", "librt.so.1"}

def prepare(destination, pcre):
    host = Path('/usr/lib/aarch64-linux-gnu')
    modules = list((host / 'security').glob('pam_*.so'))
    if not modules or not (host / 'libpam.so.0').is_file():
        raise RuntimeError('Ubuntu ARM64 PAM libraries are unavailable')
    paths = set(modules) | {host / 'libpam.so.0'}
    for module in list(paths):
        result = subprocess.run(['/usr/bin/ldd', str(module)], text=True, capture_output=True, check=True)
        if 'not found' in result.stdout:
            raise RuntimeError(f'Unresolved native PAM dependency: {module}')
        paths.update(Path(value) for value in re.findall(r'=> (/[^ ]+)', result.stdout))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    generation = Path(tempfile.mkdtemp(prefix='native-pam-', dir=destination.parent))
    for path in sorted(paths):
        if path.name in EXCLUDE or path.name.startswith(('ld-linux', 'libQt')):
            continue
        # Nix GLib requires PCRE symbol versions absent from Ubuntu's build.
        source = Path(pcre) if path.name == 'libpcre2-8.so.0' else path
        if not source.is_file():
            raise RuntimeError(f'Missing PAM bridge library: {source}')
        (generation / path.name).symlink_to(source)
    temporary = destination.with_name(destination.name + '.next')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(generation)
    os.replace(temporary, destination)

if __name__ == '__main__':
    prepare(*sys.argv[1:])
