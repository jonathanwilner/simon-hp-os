#!/usr/bin/env python3
"""Exercise PTY probe failure, successful UDP marker and path fallback."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

CLIENT = Path(__file__).with_name('client.py')
spec = importlib.util.spec_from_file_location('client', CLIENT)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class MoshTests(unittest.TestCase):
    def test_probe_needs_marker_and_success(self):
        self.assertFalse(client.probe(['/bin/sh', '-c', 'exit 0'], timeout=1))
        self.assertFalse(client.probe(['/bin/sh', '-c', 'sleep 4'], timeout=.2))

    def test_fallback_and_explicit_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / 'mosh'
            fake.write_text('''#!/usr/bin/env python3
import os, sys
with open(os.environ['CALL_LOG'], 'a') as f: f.write(sys.argv[1:].__repr__() + '\\n')
if 'private.example' in sys.argv: sys.exit(1)
# Execute only the bounded remote marker command after the argument separator.
i = sys.argv.index('--')
os.execvp(sys.argv[i + 1], sys.argv[i + 1:])
''')
            fake.chmod(0o755)
            cfg = root / 'hosts.json'
            cfg.write_text(json.dumps({'test': {'private': 'private.example', 'tailscale': 'tail.example', 'hostKeyAlias': 'trusted'}}))
            env = dict(os.environ, FLEET_MOSH_BINARY=str(fake), CALL_LOG=str(root / 'calls'))
            result = subprocess.run(['python3', str(CLIENT), '--config', str(cfg), '--check', 'test'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('UDP verified via tailscale', result.stderr)
            calls = (root / 'calls').read_text()
            self.assertIn('ProxyCommand=none', calls)
            self.assertIn('StrictHostKeyChecking=yes', calls)
            self.assertIn('MOSH_SERVER_NETWORK_TMOUT=15', calls)
            self.assertNotIn('FLEET_MOSH_', result.stderr)
            result = subprocess.run(['python3', str(CLIENT), '--config', str(cfg), '--check', '--path', 'private', 'test'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
