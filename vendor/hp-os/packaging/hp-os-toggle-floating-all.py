#!@python@
"""Toggle all windows in the current Niri session between floating and tiled."""
import json
import subprocess
import sys

NIRI = '@niri@'


def toggle(niri=NIRI):
    windows = json.loads(subprocess.check_output([niri, 'msg', '--json', 'windows'], text=True))
    if not windows:
        return
    floating = not all(window['is_floating'] for window in windows)
    action = 'move-window-to-floating' if floating else 'move-window-to-tiling'
    failures = []
    for window in windows:
        if window['is_floating'] == floating:
            continue
        result = subprocess.run([niri, 'msg', 'action', action, '--id', str(window['id'])],
                                text=True, capture_output=True)
        if result.returncode:
            failures.append(result.stderr.strip())
    if failures:
        raise RuntimeError('; '.join(failures))


if __name__ == '__main__':
    try:
        toggle()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit('Could not toggle all windows: ' + str(error))
