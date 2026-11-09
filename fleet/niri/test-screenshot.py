import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name('screenshot-copy.sh')

class Screenshots(unittest.TestCase):
    def test_capture_modes_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            binaries = root / 'bin'
            binaries.mkdir()
            for name, body in {
                'slurp': 'exit "${CANCEL:-0}"',
                'grim': 'for last; do :; done; printf PNG > "$last"',
                'wl-copy': 'cat > "$HOME/copied"',
                'notify-send': ':',
                'niri': 'printf "%s\\n" "$*" > "$HOME/niri-call"',
            }.items():
                path = binaries / name
                path.write_text('#!/bin/sh\n' + body + '\n')
                path.chmod(0o755)
            env = dict(os.environ, HOME=str(root), PATH=str(binaries)+':'+os.environ['PATH'])
            def run(mode, **extra):
                return subprocess.run(['bash', '-eu', str(SCRIPT), mode], env=dict(env, **extra), capture_output=True)
            self.assertEqual(run('screen').returncode, 0)
            self.assertEqual((root/'copied').read_text(), 'PNG')
            before = list((root/'Pictures/Screenshots').glob('*.png'))
            self.assertEqual(run('area', CANCEL='1').returncode, 0)
            self.assertEqual(list((root/'Pictures/Screenshots').glob('*.png')), before)
            self.assertEqual(run('window').returncode, 0)
            self.assertIn('screenshot-window --write-to-disk true', (root/'niri-call').read_text())
            self.assertEqual(run('invalid').returncode, 2)

if __name__ == '__main__': unittest.main()
