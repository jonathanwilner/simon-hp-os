#!/usr/bin/env python3
"""Store visual preferences only. No text input enters this helper."""
import json, os, pathlib, sys, tempfile
ALLOWED = {'colorScheme', 'height', 'keyScale', 'keyPreview', 'reducedMotion', 'floating', 'floatPositions', 'toolbar', 'prediction', 'sound', 'language'}
key = sys.argv[1]
if key not in ALLOWED:
    raise SystemExit('Unsupported visual preference')
root = pathlib.Path(os.environ.get('XDG_CONFIG_HOME', pathlib.Path.home() / '.config')) / 'hp-os' / 'touch-ui'
root.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(root, 0o700)
path = root / 'preferences.json'
try:
    data = json.loads(path.read_text())
except (FileNotFoundError, ValueError):
    data = {}
data[key] = json.loads(sys.argv[2])
fd, tmp = tempfile.mkstemp(dir=root)
try:
    with os.fdopen(fd, 'w') as out:
        json.dump(data, out)
    os.replace(tmp, path)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
