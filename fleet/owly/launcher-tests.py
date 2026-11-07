"""Exercise the real launcher with IPC endpoints, including false-success replies."""
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

class LauncherTests(unittest.TestCase):
    def launch(self, shell_reply='', shell_code=0, panel_reply='', panel_code=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stub = '''#!/bin/bash
printf '%s %s\\n' "${0##*/}" "$*" >> "$CALL_LOG"
if [[ ${0##*/} == hp-os ]]; then
  printf '%s' "$SHELL_REPLY"; exit "$SHELL_CODE"
fi
if [[ $1 == ipc ]]; then
  printf '%s' "$PANEL_REPLY"; exit "$PANEL_CODE"
fi
'''
            for name in ['hp-os', 'quickshell']:
                (root/name).write_text(stub.replace('#!/bin/bash', '#!'+os.environ.get('BASH', shutil.which('bash'))))
                (root/name).chmod(0o755)
            source = Path(os.environ.get('LAUNCHER_SOURCE', str(Path(__file__).with_name('launcher.sh')))).read_text()
            source = source.replace('@shell@', os.environ.get('BASH', shutil.which('bash'))).replace('@quickshell@', str(root/'quickshell')).replace('@panel@', '/test/panel')
            launcher = root/'launch'
            launcher.write_text(source); launcher.chmod(0o755)
            env = dict(os.environ, PATH=str(root)+':'+os.environ['PATH'], CALL_LOG=str(root/'calls'), SHELL_REPLY=shell_reply, SHELL_CODE=str(shell_code), PANEL_REPLY=panel_reply, PANEL_CODE=str(panel_code))
            subprocess.run([str(launcher)], env=env, check=True, timeout=5)
            return (root/'calls').read_text().splitlines()
    def test_integrated_shell_success(self):
        self.assertEqual(self.launch(), ['hp-os ipc hpos sharing'])
    def test_missing_shell_function_with_zero_exit_uses_panel(self):
        for reply in ['Function not found.', 'Target not found.', 'No running instances']:
            with self.subTest(reply=reply):
                calls = self.launch(shell_reply=reply)
                self.assertEqual(calls[-1], 'quickshell ipc -p /test/panel call omdrop open')
    def test_missing_shell_and_panel_launches_visible_window(self):
        calls = self.launch(shell_reply='Function not found.', panel_reply='Target not found.')
        self.assertEqual(calls[-1], 'quickshell -p /test/panel --no-duplicate')
    def test_nonzero_ipc_failures_launch_window(self):
        self.assertEqual(self.launch(shell_code=1, panel_code=1)[-1], 'quickshell -p /test/panel --no-duplicate')

if __name__ == '__main__': unittest.main()
