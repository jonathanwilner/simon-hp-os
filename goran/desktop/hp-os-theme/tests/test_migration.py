import os
from pathlib import Path
import subprocess
import tempfile
import unittest

class BackupMigration(unittest.TestCase):
    def test_original_backups_survive_rename_and_repeat(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/hp-os-theme-migrate'
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            old = state / 'nixos-intc/harmonyos-dms-theme'
            new = state / 'nixos-intc/hp-os-dms-theme'
            old.mkdir(parents=True)
            for name, data in [('settings.pre-harmonyos.json', '{"pinnedApps":["custom"]}'), ('fontconfig.pre-harmonyos.conf', '<fontconfig/>')]:
                (old / name).write_text(data)
            env = dict(os.environ, XDG_STATE_HOME=tmp)
            subprocess.run(['bash', str(script)], env=env, check=True)
            self.assertEqual((new / 'settings.pre-hp-os.json').read_text(), '{"pinnedApps":["custom"]}')
            self.assertEqual((new / 'fontconfig.pre-hp-os.conf').read_text(), '<fontconfig/>')
            (old / 'settings.pre-harmonyos.json').write_text('changed')
            subprocess.run(['bash', str(script)], env=env, check=True)
            self.assertEqual((new / 'settings.pre-hp-os.json').read_text(), '{"pinnedApps":["custom"]}')
            self.assertEqual((new / 'settings.pre-hp-os.json').stat().st_mode & 0o777, 0o600)

if __name__ == '__main__': unittest.main()
