#!/usr/bin/env python3
"""Live user-systemd regression: changed refresh units must not interrupt work.

Run outside a sandbox with SD_SWITCH pointing at Home Manager's sd-switch.
Uses only uniquely named temporary test units and removes them on completion.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


with tempfile.TemporaryDirectory(prefix='hp-os-switch-test-') as directory:
    base = Path(directory)
    old, new = base / 'old', base / 'new'
    old.mkdir(); new.mkdir()
    units = []
    try:
        for phase in ('activating', 'active'):
            name = f'hp-os-switch-proof-{os.getpid()}-{phase}.service'
            units.append(name)
            worker = base / f'{phase}.py'
            worker.write_text(f'import os,time\nfrom pathlib import Path\np=Path({str(base / phase)!r})\np.write_text(str(os.getpid()))\ntime.sleep({3 if phase == "activating" else 0.05})\np.with_suffix(".done").touch()\n')
            (old / name).write_text(f'[Unit]\nDescription=HP-OS isolated upgrade proof\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart={sys.executable} {worker}\n')
            (new / name).write_text('[Unit]\nDescription=Changed HP-OS isolated upgrade proof\nX-SwitchMethod=keep-old\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/does-not-exist-hp-os-proof\n')
            run('systemctl', '--user', 'link', str(old / name))
        run('systemctl', '--user', 'daemon-reload')
        for name in units:
            run('systemctl', '--user', 'start', '--no-block', name)
        deadline = time.monotonic() + 2
        while not (base / 'activating').exists() or not (base / 'active.done').exists():
            assert time.monotonic() < deadline, 'test workers did not start'
            time.sleep(.02)
        assert run('systemctl', '--user', 'show', '-p', 'ActiveState', '--value', units[0]).strip() == 'activating'
        assert run('systemctl', '--user', 'show', '-p', 'ActiveState', '--value', units[1]).strip() == 'active'
        output = run(os.environ['SD_SWITCH'], '--verbose', '--old-units', str(old), '--new-units', str(new))
        print(output)
        pid = int((base / 'activating').read_text())
        os.kill(pid, 0)
        deadline = time.monotonic() + 5
        while not (base / 'activating.done').exists():
            assert time.monotonic() < deadline, 'in-progress refresh was interrupted'
            time.sleep(.05)
        for name in units:
            assert run('systemctl', '--user', 'show', '-p', 'Result', '--value', name).strip() == 'success'
            assert run('systemctl', '--user', 'show', '-p', 'ActiveState', '--value', name).strip() == 'active'
        print('PASS: changed active and activating units preserved; original operation completed')
    finally:
        for name in units:
            subprocess.run(['systemctl', '--user', 'stop', name], check=False, capture_output=True)
            subprocess.run(['systemctl', '--user', 'disable', name], check=False, capture_output=True)
        run('systemctl', '--user', 'daemon-reload')
