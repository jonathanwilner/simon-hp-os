import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
spec = importlib.util.spec_from_file_location('appearance', Path(__file__).with_name('hp-os-appearance.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AppearanceTest(unittest.TestCase):
    def test_native_modes_preserve_other_kde_and_cosmic_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config'
            config.mkdir()
            kde = config / 'kdeglobals'
            kde.write_text('# User settings\n[General]\nColorScheme=OldScheme\nfont=Custom,11\n'
                           '[Other][Nested]\nlocalized[de]=100%\nflag\n')
            cosmic = config / 'cosmic/com.system76.CosmicTheme.Mode/v1'
            cosmic.mkdir(parents=True)
            (cosmic / 'auto_switch').write_text('false\n')
            files = config / 'hp-os/apps/files/kdeglobals'
            files.parent.mkdir(parents=True)
            files.write_text('[General]\nfont=Custom,13\n[Colors:View]\nBackgroundNormal=255,255,255\n')
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(config),
                                        'XDG_STATE_HOME': str(root / 'state')}), \
                    patch.object(module.subprocess, 'run'):
                for mode in ('light', 'dark', 'light'):
                    module.apply(mode)
                    scheme = 'BreezeDark' if mode == 'dark' else 'BreezeLight'
                    self.assertEqual(kde.read_text(),
                                     '# User settings\n[General]\nColorScheme=' + scheme + '\nfont=Custom,11\n'
                                     '[Other][Nested]\nlocalized[de]=100%\nflag\n')
                    self.assertEqual((cosmic / 'is_dark').read_text(),
                                     'true\n' if mode == 'dark' else 'false\n')
                    self.assertEqual((cosmic / 'auto_switch').read_text(), 'false\n')
                    self.assertIn('font=Custom,13', files.read_text())
                    self.assertIn('BackgroundNormal=' + ('35,38,41' if mode == 'dark' else '255,255,255'),
                                  files.read_text())

    def test_missing_kde_key_or_group(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'kdeglobals'
            for original, expected in (
                    ('[General]\nfont=Custom', '[General]\nfont=Custom\nColorScheme=BreezeDark\n'),
                    ('[Other]\nkey=value', '[Other]\nkey=value\n[General]\nColorScheme=BreezeDark\n')):
                path.write_text(original)
                module.set_kde_color_scheme(path, 'BreezeDark')
                self.assertEqual(path.read_text(), expected)

    def test_modes_preserve_settings_and_notify_both_buses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'config/gtk-3.0/settings.ini'
            path.parent.mkdir(parents=True)
            path.write_text('[Settings]\ngtk-theme-name=Adwaita-dark\ngtk-font-name=HarmonyOS Sans 11\n')
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(root/'config'), 'XDG_STATE_HOME': str(root/'state'), 'XDG_RUNTIME_DIR': str(root/'run'), 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/private'}), patch.object(module.subprocess, 'run') as run:
                for mode in ('light', 'dark'):
                    module.apply(mode)
                    self.assertEqual((root/'state/hp-os/appearance-mode').read_text().strip(), mode)
                    self.assertEqual((root/'state/hp-os/appearance-owner').read_text().strip(), str(os.getppid()))
                    text = path.read_text()
                    self.assertIn('gtk-font-name=HarmonyOS Sans 11', text)
                    self.assertIn('gtk-application-prefer-dark-theme=' + str(int(mode == 'dark')), text)
                self.assertEqual(run.call_count, 8)
    def test_uses_dconf_on_both_buses_despite_inherited_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environments = []
            def capture(*args, **kwargs):
                environments.append(dict(kwargs['env']))
            with patch.dict(os.environ, {
                'XDG_CONFIG_HOME': str(root/'config'),
                'XDG_STATE_HOME': str(root/'state'),
                'XDG_RUNTIME_DIR': str(root/'run'),
                'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/private',
                'GSETTINGS_BACKEND': 'keyfile',
                'GIO_EXTRA_MODULES': '/incompatible-host/modules',
            }), patch.object(module.subprocess, 'run', side_effect=capture):
                module.apply('dark')
            self.assertEqual(len(environments), 4)
            self.assertEqual({env['DBUS_SESSION_BUS_ADDRESS'] for env in environments},
                             {'unix:path=/private', 'unix:path=' + str(root/'run/bus')})
            for env in environments:
                self.assertEqual(env['GSETTINGS_BACKEND'], 'dconf')
                self.assertEqual(env['GIO_EXTRA_MODULES'], '@dconfModules@')
    def test_reject_unknown_mode(self):
        with self.assertRaises(ValueError):
            module.apply('invalid')

if __name__ == '__main__':
    unittest.main()
