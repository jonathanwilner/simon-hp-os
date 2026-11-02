import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('brand', Path(__file__).resolve().parents[1] / 'packaging/migrate-brand.py')
brand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brand)
class Migration(unittest.TestCase):
    def test_existing_preferences_and_active_paths_survive(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {}, clear=True):
            home = Path(tmp)
            old = home / '.config/harmonyshell'
            (old / 'niri').mkdir(parents=True)
            (old / 'config.json').write_text(json.dumps({'appearance': {'iconTheme':'HarmonyOS', 'font':'HarmonyOS Sans'}, 'custom':42, 'panelFamily':'harmony', 'harmony':{'quality':'balanced','customPreference':7}}))
            (old / 'niri/config.kdl').write_text('spawn-at-startup "harmonyshell" "run"\nbinds { Mod+S { spawn "hp-os" "ipc" "harmony" "search"; } }\n')
            brand.migrate(home)
            brand.migrate(home)
            self.assertTrue(old.is_symlink())
            data=json.loads((home / '.config/hp-os/config.json').read_text())
            self.assertEqual(data['custom'],42)
            self.assertEqual(data['panelFamily'],'hpos')
            self.assertEqual(data['hpos']['customPreference'],7)
            self.assertNotIn('harmony',data)
            self.assertEqual(data['appearance'], {'iconTheme':'HP-OS','font':'HarmonyOS Sans'})
            self.assertIn('"hp-os"', (old / 'niri/config.kdl').read_text())
            self.assertIn('"hpos" "search"', (old / 'niri/config.kdl').read_text())
            self.assertNotIn('"harmony"', (old / 'niri/config.kdl').read_text())
    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {}, clear=True):
            home=Path(tmp)
            for name in ['harmonyshell','hp-os']:
                path=home/'.config'/name;path.mkdir(parents=True);(path/'keep').write_text(name)
            brand.migrate(home)
            self.assertEqual((home/'.config/hp-os/keep').read_text(),'hp-os')
            self.assertEqual((home/'.config/harmonyshell/keep').read_text(),'harmonyshell')
if __name__ == '__main__': unittest.main()
