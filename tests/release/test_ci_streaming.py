import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

CI = Path(__file__).with_name('ci.sh').read_text()


class Streaming(unittest.TestCase):
    def test_live_log_and_final_status(self):
        for code in (0, 7):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'pkgs/nom-dashboard').mkdir(parents=True)
                (root / 'pkgs/nom-dashboard/nom-tmux.sh').write_text('''#!/bin/bash
mkdir -p "$NOM_DASHBOARD_STATE_DIR"
printf 'early-output\\n' > "$NOM_DASHBOARD_STATE_DIR/$1.log"
''')
                binpath = root / 'bin'
                binpath.mkdir()
                for name, text in {
                    'df': '#!/bin/bash\nexit 0\n',
                    'tmux': '#!/bin/bash\nexit 0\n',
                    'sleep': '#!/bin/bash\n/bin/sleep 0.05\n',
                }.items():
                    path = binpath / name
                    path.write_text(text.replace('/bin/bash', shutil.which('bash')).replace('/bin/sleep', shutil.which('sleep')))
                    path.chmod(0o755)
                script = root / 'ci.sh'
                script.write_text(CI)
                env = dict(os.environ, RUNNER_TEMP=tmp, PATH=str(binpath)+':'+os.environ['PATH'])
                process = subprocess.Popen(['bash', str(script), 'x86_64-linux'], cwd=root, env=env,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    # Receive output while there is still no completion status.
                    import select
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'live output timed out')
                    self.assertEqual(process.stdout.readline(), 'early-output\n')
                    state = root / 'fleet-release-nom/fleet-validation-x86_64-linux'
                    self.assertFalse(state.with_suffix('.status').exists())
                    with state.with_suffix('.log').open('a') as log:
                        log.write('final-output\n')
                    state.with_suffix('.status').write_text(str(code))
                    output, errors = process.communicate(timeout=5)
                    self.assertEqual(output, 'final-output\n')
                    self.assertEqual(process.returncode, code, errors)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
                    process.stdout.close()
                    process.stderr.close()


if __name__ == '__main__':
    unittest.main()
