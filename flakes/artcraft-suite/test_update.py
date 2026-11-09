import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('updater', Path(__file__).with_name('update.py'))
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

class UpdateTests(unittest.TestCase):
    def test_official_discovery_excludes_community(self):
        source = b'pub const SUITE: [CraftApp; 3] = ["storytold/photocraft", "tangency-labs/solidcraft", "storytold/figcraft"];'
        with patch.object(u, 'fetch', return_value=source):
            self.assertEqual(u.discover(), ['figcraft', 'photocraft'])

    def test_catalog_does_not_change_selection(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)/'versions.json'
            original = '{"photocraft":{"version":"1"}}'
            target.write_text(original)
            with patch.object(sys, 'argv', ['update.py', '--catalog', '--versions', str(target)]), patch.object(u, 'discover', return_value=['photocraft', 'figcraft']):
                u.main()
            self.assertEqual(target.read_text(), original)

    def test_missing_assets_preserves_pins(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)/'versions.json'
            original = '{"photocraft":{"version":"1"}}'
            target.write_text(original)
            with patch.object(sys, 'argv', ['update.py', '--versions', str(target)]), patch.object(u, 'fetch', return_value=json.dumps({'assets': []}).encode()):
                with self.assertRaises(KeyError):
                    u.main()
            self.assertEqual(target.read_text(), original)

if __name__ == '__main__':
    unittest.main()
