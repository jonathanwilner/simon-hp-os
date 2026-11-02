#!/usr/bin/env python3
"""Atomically refresh shell-owned update metadata in the isolated config."""
import json
import os
from pathlib import Path
import sys
import tempfile

config = Path(sys.argv[1])
metadata = dict(version='0.1.0', upstreamVersion='2.33.0', installMode='package', updateStrategy='package-manager', installSource='HP-OS')
fd, temporary = tempfile.mkstemp(prefix='.version-', suffix='.json', dir=config)
try:
    with os.fdopen(fd, 'w') as output:
        json.dump(metadata, output, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, config / 'version.json')
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
