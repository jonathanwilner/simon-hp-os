#!/usr/bin/env python3
"""Visual preference writes remain private and reject nonvisual keys."""
import json, os, pathlib, subprocess, tempfile
helper=pathlib.Path(__file__).with_name('preferences.py')
with tempfile.TemporaryDirectory() as directory:
    env=dict(os.environ, XDG_CONFIG_HOME=directory)
    subprocess.run(['python3',str(helper),'height','380'],env=env,check=True)
    path=pathlib.Path(directory)/'hp-os/touch-ui/preferences.json'
    assert json.loads(path.read_text())=={'height':380}
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    result=subprocess.run(['python3',str(helper),'mode','"always"'],env=env,capture_output=True)
    assert result.returncode!=0
    assert json.loads(path.read_text())=={'height':380}
print('Private preference checks passed')
