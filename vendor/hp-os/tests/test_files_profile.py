"""Ensure app theming cannot redirect user files or rewrite normal KDE settings."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging'))
spec = importlib.util.spec_from_file_location('files_profile', ROOT / 'packaging/hp-os-files.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class FilesProfileTests(unittest.TestCase):
    def test_launch_tracks_mode_and_preserves_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'state/hp-os'
            state.mkdir(parents=True)
            env = {'HOME': directory, 'XDG_STATE_HOME': str(root / 'state')}
            for mode in ('light', 'dark', 'light'):
                (state / 'appearance-mode').write_text(mode)
                actual = profile.prepare_environment(env, ROOT / 'packaging/files')
                kde = Path(actual['XDG_CONFIG_HOME']) / 'kdeglobals'
                text = kde.read_text()
                self.assertIn('BackgroundNormal=' + ('35,38,41' if mode == 'dark' else '255,255,255'), text)
                self.assertIn('font=HarmonyOS Sans,12,', text)
                self.assertIn('SingleClick=false', text)
                self.assertEqual(text.count('[Colors:View]'), 1)
                if mode == 'light':
                    kde.write_text(text.replace('menuFont=HarmonyOS Sans,12,', 'menuFont=Custom,14,'))
                else:
                    self.assertIn('menuFont=Custom,14,', text)

    def test_upgrade_only_original_font_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'kdeglobals'
            path.write_text('[General]\nfont=Inter,11,-1,5,50,0,0,0,0,0\n'
                            'menuFont=Custom Font,13,-1,5,50,0,0,0,0,0\n'
                            'toolBarFont=Inter,11,-1,5,50,0,0,0,0,0\n'
                            'Unrelated[$e]=100% literal\n[Other]\n'
                            'font=Inter,11,-1,5,50,0,0,0,0,0\n')
            path.chmod(0o600)
            profile.upgrade_seeded_fonts(path)
            updated = path.read_text()
            self.assertIn('font=HarmonyOS Sans,12,-1,5,50,0,0,0,0,0', updated)
            self.assertIn('menuFont=Custom Font,13,-1,5,50,0,0,0,0,0', updated)
            self.assertIn('Unrelated[$e]=100% literal', updated)
            self.assertIn('[Other]\nfont=Inter,11,-1,5,50,0,0,0,0,0', updated)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            before = path.stat().st_mtime_ns
            profile.upgrade_seeded_fonts(path)
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_isolation_and_repeat_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config'
            config.mkdir()
            (config / 'kdeglobals').write_text('existing dark theme')
            (config / 'user-dirs.dirs').write_text('XDG_DOCUMENTS_DIR="$HOME/My Documents"')
            env = {'HOME': str(root), 'XDG_CONFIG_HOME': str(config),
                   'XDG_DATA_HOME': str(root / 'real-data'),
                   'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/real-bus',
                   'QT_PLUGIN_PATH': '/unrelated-qt/plugins', 'QT_QPA_PLATFORMTHEME': 'qt6ct',
                   'NIXPKGS_QT6_QML_IMPORT_PATH': '/unrelated-qt/qml',
                   'XDG_RUNTIME_DIR': '/run/user/123', 'XDG_DATA_DIRS': '/installed/share'}
            actual = profile.prepare_environment(env, ROOT / 'packaging/files')
            for key in ('HOME', 'XDG_DATA_HOME', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_RUNTIME_DIR'):
                self.assertEqual(actual[key], env[key])
            self.assertEqual((config / 'kdeglobals').read_text(), 'existing dark theme')
            self.assertEqual(actual['XDG_CONFIG_DIRS'], str(config) + ':/etc/xdg')
            self.assertEqual(actual['QT_QPA_PLATFORMTHEME'], 'kde')
            self.assertEqual(actual['QT_PLUGIN_PATH'], '@qtPlugins@')
            self.assertNotIn('NIXPKGS_QT6_QML_IMPORT_PATH', actual)
            self.assertEqual(env['QT_PLUGIN_PATH'], '/unrelated-qt/plugins')
            scoped = Path(actual['XDG_CONFIG_HOME'])
            self.assertEqual((scoped / 'user-dirs.dirs').resolve(), config / 'user-dirs.dirs')
            (scoped / 'dolphinrc').write_text('custom Files layout')
            profile.prepare_environment(env, ROOT / 'packaging/files')
            self.assertEqual((scoped / 'dolphinrc').read_text(), 'custom Files layout')
            self.assertNotIn('QT_STYLE_OVERRIDE', env)

    def test_default_data_location_remains_default(self):
        with tempfile.TemporaryDirectory() as directory:
            env = profile.prepare_environment({'HOME': directory}, ROOT / 'packaging/files')
            self.assertNotIn('XDG_DATA_HOME', env)
            self.assertEqual(env['XDG_CONFIG_HOME'], directory + '/.config/hp-os/apps/files')


if __name__ == '__main__':
    unittest.main()
