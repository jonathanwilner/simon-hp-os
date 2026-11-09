#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('profile', HERE / 'prepare-profile.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BootstrapTests(unittest.TestCase):
    def test_identity_is_data_and_user_is_not_simon(self):
        with tempfile.TemporaryDirectory() as directory:
            run = pathlib.Path(directory)
            module.profile(run, 'alice', '/home/alice', 'a' * 40)
            values = json.loads((run / 'profile/identity.json').read_text())
            self.assertEqual(values['home.username'], 'alice')
            self.assertEqual(values['home.homeDirectory'], '/home/alice')
            source = (run / 'profile/flake.nix').read_text()
            self.assertIn('simon-hp-os/' + 'a' * 40, source)
            self.assertIn('homeModules.ubuntuSnapdragon', source)
            self.assertNotIn('assistant-ost', source)

    def test_launcher_handles_home_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='hp os ') as directory:
            home = pathlib.Path(directory)
            (home / '.local/bin').mkdir(parents=True)
            (home / '.local/share/applications').mkdir(parents=True)
            module.launcher(home / 'run', home)
            subprocess.run(['sh', '-n', str(home / '.local/bin/hp-os-snapdragon-update')], check=True)
            desktop = (home / '.local/share/applications/hp-os-snapdragon-update.desktop').read_text()
            self.assertIn('Terminal=true', desktop)
            self.assertIn('Exec="', desktop)

    def test_help_requires_no_privileges_or_network(self):
        result = subprocess.run(['bash', str(HERE / 'bootstrap.sh'), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--source-revision', result.stdout)


if __name__ == '__main__':
    unittest.main()
