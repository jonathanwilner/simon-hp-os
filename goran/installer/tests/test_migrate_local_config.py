import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).parents[1] / 'migrate-local-config.py'
spec = importlib.util.spec_from_file_location('migration', SCRIPT)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old = pathlib.Path(self.temp.name) / 'old'
        self.new = pathlib.Path(self.temp.name) / 'new'
        for repo in (self.old, self.new):
            repo.mkdir()
            self.git(repo, 'init', '-q')
            self.git(repo, 'config', 'user.email', 'test@example.invalid')
            self.git(repo, 'config', 'user.name', 'Test')
            self.write(repo, 'goran/desktop/niri.nix', 'a=1\nb=2\nc=3\nd=4\ne=5\n')
            self.git(repo, 'add', '.')
            self.git(repo, 'commit', '-qm', 'baseline')
        self.base = self.git(self.old, 'rev-parse', 'HEAD').strip()

    def git(self, repo, *args):
        return subprocess.check_output(['git', '-C', str(repo), *args]).decode()

    def write(self, repo, name, data):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)

    def run_merge(self):
        return migration.migrate(self.old, self.new, self.base)

    def test_committed_and_dirty_deltas_merge_with_public_changes(self):
        self.write(self.old, 'goran/desktop/niri.nix', 'a=11\nb=2\nc=3\nd=4\ne=5\n')
        self.git(self.old, 'commit', '-qam', 'local customization')
        self.write(self.old, 'goran/desktop/niri.nix', 'a=12\nb=2\nc=3\nd=4\ne=5\n')
        self.write(self.new, 'goran/desktop/niri.nix', 'a=1\nb=2\nc=3\nd=4\ne=55\n')
        before = self.git(self.old, 'status', '--porcelain')
        result = self.run_merge()
        self.assertTrue(result['applied'])
        self.assertEqual((self.new/'goran/desktop/niri.nix').read_text(), 'a=12\nb=2\nc=3\nd=4\ne=55\n')
        self.assertEqual(self.git(self.old, 'status', '--porcelain'), before)

    def test_conflict_applies_nothing(self):
        self.write(self.old, 'goran/desktop/niri.nix', 'conflicting legacy\n')
        self.write(self.new, 'goran/desktop/niri.nix', 'conflicting public\n')
        self.assertFalse(self.run_merge()['applied'])
        self.assertEqual((self.new/'goran/desktop/niri.nix').read_text(), 'conflicting public\n')

    def test_new_module_blocks_and_private_unrelated_retained(self):
        self.write(self.old, 'goran/desktop/custom.nix', '{ custom = true; }')
        self.write(self.old, 'secrets/private.key', 'private data')
        report = self.run_merge()
        self.assertFalse(report['applied'])
        self.assertEqual(report['blocked'][0]['path'], 'goran/desktop/custom.nix')
        self.assertIn('secrets/private.key', report['retained_in_legacy'])
        self.assertFalse((self.new/'secrets').exists())

    def test_missing_upstream_requires_explicit_base(self):
        with self.assertRaisesRegex(ValueError, 'legacy-base'):
            migration.migrate(self.old, self.new)

    def test_upstream_merge_base(self):
        self.git(self.old, 'branch', 'upstream')
        self.git(self.old, 'branch', '--set-upstream-to=upstream')
        self.write(self.old, 'goran/desktop/niri.nix', 'local customization\n')
        self.git(self.old, 'commit', '-qam', 'custom')
        self.assertEqual(migration.migrate(self.old, self.new)['base'], self.base)

    def test_theme_and_shell_paths(self):
        self.assertEqual(migration.mapped('goran/desktop/harmonyos.nix'), 'goran/desktop/hp-os-theme.nix')
        self.assertEqual(migration.mapped('goran/desktop/harmonyos-theme/themes/harmonyos.json'), 'goran/desktop/hp-os-theme/themes/hp-os.json')
        self.assertEqual(migration.mapped('HarmonyShell/foo.qml'), 'vendor/HP-OSShell/foo.qml')

    def test_shell_renamed_component_three_way_merge(self):
        old = 'HarmonyShell/overlay/modules/harmony/design/HarmonyTokens.qml'
        new = 'vendor/HP-OSShell/overlay/modules/hpos/design/HposTokens.qml'
        self.write(self.old, old, 'size: 10\n// spacer\n// spacer2\ncolor: "red"\n')
        self.git(self.old, 'add', '.')
        self.git(self.old, 'commit', '-qm', 'legacy shell base')
        self.base = self.git(self.old, 'rev-parse', 'HEAD').strip()
        self.write(self.old, old, 'size: 12\n// spacer\n// spacer2\ncolor: "red"\n')
        self.write(self.new, new, 'size: 10\n// spacer\n// spacer2\ncolor: "blue"\n')
        self.git(self.new, 'add', '.')
        self.git(self.new, 'commit', '-qm', 'public renamed shell')
        report = self.run_merge()
        self.assertTrue(report['applied'])
        self.assertEqual((self.new/new).read_text(), 'size: 12\n// spacer\n// spacer2\ncolor: "blue"\n')
        self.assertEqual(report['merged'][0]['to'], new)

    def test_shell_known_renames_preserve_font_provenance(self):
        cases = {
            'overlay/assets/harmony-app-center.svg': 'overlay/assets/hpos-app-center.svg',
            'packaging/files/harmony-files.qss': 'packaging/files/hpos-files.qss',
            'packaging/fonts/harmony-fonts.py': 'packaging/fonts/hpos-fonts.py',
            'patches/harmony-style.patch': 'patches/hpos-style.patch',
            'patches/inir-harmony.patch': 'patches/inir-hpos.patch',
            'tests/test_harmony_contract.py': 'tests/test_hpos_contract.py',
            'packaging/fonts/HarmonyOS_Sans.ttf': 'packaging/fonts/HarmonyOS_Sans.ttf',
        }
        for old, new in cases.items():
            self.assertEqual(migration.mapped('HarmonyShell/' + old), 'vendor/HP-OSShell/' + new)

    def test_secret_in_relevant_file_blocks(self):
        self.write(self.old, 'goran/desktop/niri.nix', '-----BEGIN OPENSSH PRIVATE KEY-----\n')
        self.assertFalse(self.run_merge()['applied'])


if __name__ == '__main__':
    unittest.main()
