"""A failed unattended task must release its stable tmux name for the timer."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


class SessionTests(unittest.TestCase):
    def test_failure_releases_session_and_preserves_exit(self):
        script = Path(__file__).parents[1] / 'pkgs/nom-dashboard/nom-tmux.sh'
        session = f'fleet-timer-test-{os.getpid()}'
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, NOM_TMUX_KEEP_SESSION='0', NOM_DASHBOARD_STATE_DIR=directory,
                       NOM_DASHBOARD_PUBLIC_DIR=f'{directory}/public', NOM_DASHBOARD_REMOTE='')
            subprocess.run(['bash', str(script), session, '--', 'bash', '-c', 'exit 7'], env=env, check=True)
            self.addCleanup(subprocess.run, ['tmux', 'kill-session', '-t', f'={session}'], capture_output=True)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if subprocess.run(['tmux', 'has-session', '-t', f'={session}'], capture_output=True).returncode:
                    break
                time.sleep(.2)
            else:
                self.fail('failed scheduled task retained its tmux session')
            self.assertEqual((Path(directory) / f'{session}.status').read_text().strip(), '7')
