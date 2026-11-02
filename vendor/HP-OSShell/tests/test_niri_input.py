"""Existing input customizations survive the clickfinger default migration."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('migration', Path(__file__).resolve().parents[1] / 'packaging/migrate-niri-input.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)

class NiriInput(unittest.TestCase):
    def test_default_upgrade_is_idempotent_and_backed_up(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'config.kdl'
            old = 'input {\n' + migration.OLD + '}\n'
            path.write_text(old)
            migration.migrate(path)
            updated = path.read_text()
            self.assertIn('click-method "clickfinger"', updated)
            self.assertEqual(path.with_name('config.kdl.before-clickfinger').read_text(), old)
            migration.migrate(path)
            self.assertEqual(path.read_text(), updated)

    def test_custom_input_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'config.kdl'
            for old in ['input { touchpad { tap; click-method "button-areas"; } }',
                        'input {\n' + migration.OLD + '    mouse { natural-scroll; }\n}\n']:
                path.write_text(old)
                migration.migrate(path)
                self.assertEqual(path.read_text(), old)
