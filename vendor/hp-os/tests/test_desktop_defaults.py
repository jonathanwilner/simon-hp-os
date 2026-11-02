"""Verify first-login defaults and preservation across upgrades."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('defaults', ROOT / 'packaging/initialize-config.py')
defaults = importlib.util.module_from_spec(spec)
spec.loader.exec_module(defaults)

class DesktopDefaults(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        (self.home / 'Documents').mkdir(parents=True)
        (self.home / 'Downloads').mkdir()
        self.state = self.root / 'state'
        self.config = self.root / 'config.json'
        self.apps = {name: dict(kind='application', target=name, label=name, icon='application-x-executable')
                     for name in ['org.kde.dolphin', 'hp-os-trash', 'org.kde.gwenview', 'firefox', 'kitty', 'hp-os-settings']}
        for mock in [patch.object(defaults, 'installed_apps', return_value=self.apps),
                     patch.object(Path, 'home', return_value=self.home),
                     patch.dict(os.environ, INIR_STATE_DIR=str(self.state))]:
            mock.start()
            self.addCleanup(mock.stop)

    def run_defaults(self):
        defaults.initialize(ROOT / 'packaging/default-config.json', self.config, '/runtime/assets/harmony-wallpaper.png')

    def test_fresh_desktop_has_real_apps_and_existing_folders(self):
        self.run_defaults()
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg['panelFamily'], 'harmony')
        self.assertEqual(cfg['dock']['pinnedApps'], ['org.kde.dolphin', 'hp-os-trash', 'org.kde.gwenview', 'hp-os-settings'])
        items = json.loads((self.state / 'user/desktop-items.json').read_text())['items']
        self.assertGreaterEqual(len(items), 6)
        for item in items.values():
            if item['kind'] == 'application': self.assertIn(item['target'], self.apps)
            else: self.assertTrue(Path(item['target']).is_dir())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_old_icon_theme_migrates_after_desktop_seed(self):
        self.run_defaults()
        user = self.state / 'user'
        (user / 'hp-os-original-icons-v1.json').unlink()
        cfg = json.loads(self.config.read_text())
        cfg['appearance']['iconTheme'] = 'Papirus'
        self.config.write_text(json.dumps(cfg))
        self.run_defaults()
        self.assertEqual(json.loads(self.config.read_text())['appearance']['iconTheme'], 'HP-OS')
        # A later explicit theme choice survives subsequent starts.
        cfg['appearance']['iconTheme'] = 'custom-theme'
        self.config.write_text(json.dumps(cfg))
        self.run_defaults()
        self.assertEqual(json.loads(self.config.read_text())['appearance']['iconTheme'], 'custom-theme')

    def legacy_seed(self, pins, current=None):
        self.config.write_text(json.dumps({'panelFamily': 'harmony', 'dock': {'pinnedApps': pins if current is None else current}}))
        user = self.state / 'user'
        user.mkdir(parents=True)
        (user / 'hp-os-desktop-defaults-v2.json').write_text(json.dumps({'version': 2, 'seededPins': pins}))
        (user / 'desktop-items.json').write_text('{"version":1,"items":{}}')

    def test_existing_seed_migrates_independently_of_desktop_marker(self):
        old = ['org.kde.dolphin', 'firefox', 'kitty', 'hp-os-settings']
        self.legacy_seed(old)
        self.run_defaults()
        self.assertEqual(json.loads(self.config.read_text())['dock']['pinnedApps'],
                         ['org.kde.dolphin', 'hp-os-trash', 'org.kde.gwenview', 'hp-os-settings'])
        self.assertEqual(json.loads((self.state / 'user/desktop-items.json').read_text())['items'], {})
        self.assertTrue((self.state / 'user/hp-os-dock-defaults-v3.json').exists())
        # Even reverting to the former defaults later is a user choice.
        cfg = json.loads(self.config.read_text())
        cfg['dock']['pinnedApps'] = old
        self.config.write_text(json.dumps(cfg))
        self.run_defaults()
        self.assertEqual(json.loads(self.config.read_text()), cfg)

    def test_customized_reordered_and_cleared_pins_are_preserved(self):
        old = ['org.kde.dolphin', 'firefox', 'kitty']
        for customized in [list(reversed(old)), ['firefox'], []]:
            with self.subTest(pins=customized):
                marker = self.state / 'user/hp-os-dock-defaults-v3.json'
                marker.unlink(missing_ok=True)
                (self.state / 'user').mkdir(parents=True, exist_ok=True)
                (self.state / 'user/hp-os-desktop-defaults-v2.json').write_text(json.dumps({'version': 2, 'seededPins': old}))
                config = {'panelFamily': 'harmony', 'dock': {'pinnedApps': customized}}
                self.config.write_text(json.dumps(config))
                self.run_defaults()
                self.assertEqual(json.loads(self.config.read_text()), config)

    def test_sparse_install_omits_unavailable_categories(self):
        self.assertEqual(defaults.defaults_for_installed_apps({'firefox': {}, 'kitty': {}}), [])
        self.assertEqual(defaults.defaults_for_installed_apps({'thunar': {}, 'org.gnome.Loupe': {}}),
                         ['thunar', 'org.gnome.Loupe'])

    def test_bad_seed_marker_does_not_authorize_pin_replacement(self):
        self.legacy_seed(['firefox'])
        (self.state / 'user/hp-os-desktop-defaults-v2.json').write_text('broken')
        self.run_defaults()
        self.assertEqual(json.loads(self.config.read_text())['dock']['pinnedApps'], ['firefox'])

    def test_non_harmony_with_old_marker_remains_unchanged(self):
        self.legacy_seed(['firefox'])
        config = {'panelFamily': 'iris', 'dock': {'pinnedApps': ['firefox']}}
        self.config.write_text(json.dumps(config))
        self.run_defaults()
        self.assertEqual(json.loads(self.config.read_text()), config)
        self.assertFalse((self.state / 'user/hp-os-dock-defaults-v3.json').exists())

    def test_restart_preserves_rearranged_icons_and_pins(self):
        self.run_defaults()
        path = self.state / 'user/desktop-items.json'
        doc = json.loads(path.read_text())
        first = next(iter(doc['items'].values()))
        first['x'], first['y'] = 400, 220
        path.write_text(json.dumps(doc))
        cfg = json.loads(self.config.read_text())
        cfg['dock']['pinnedApps'] = ['firefox']
        cfg['background']['wallpaperPath'] = '/custom/image.png'
        self.config.write_text(json.dumps(cfg))
        self.run_defaults()
        self.assertEqual(json.loads(path.read_text()), doc)
        self.assertEqual(json.loads(self.config.read_text()), cfg)

    def test_user_removal_stays_removed_after_seed(self):
        self.run_defaults()
        path = self.state / 'user/desktop-items.json'
        path.write_text('{"version":1,"items":{}}')
        self.run_defaults()
        self.assertEqual(json.loads(path.read_text())['items'], {})

    def test_legacy_defaults_migrate_but_custom_geometry_stays(self):
        self.config.write_text(json.dumps({'panelFamily':'harmony', 'iris':{'bar':{'height':40,'margin':12},'dock':{'iconSize':58}}, 'dock':{'pinnedApps':['firefox']}, 'background':{'wallpaperPath':'/custom.png'}}))
        self.run_defaults()
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg['iris']['bar']['margin'],20)
        self.assertEqual(cfg['iris']['dock']['iconSize'],58)
        self.assertEqual(cfg['dock']['pinnedApps'],['firefox'])
        self.assertEqual(cfg['background']['wallpaperPath'],'/custom.png')

    def test_failed_svg_shipped_fallback_migrates_once(self):
        old = '/nix/store/abc-hp-os-runtime-2.33.0/share/quickshell/inir/assets/wallpapers/qs-niri.jpg'
        self.config.write_text(json.dumps({'panelFamily': 'harmony', 'background': {'wallpaperPath': old}}))
        self.run_defaults()
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg['background']['wallpaperPath'], '/runtime/assets/harmony-wallpaper.png')
        cfg['background']['wallpaperPath'] = old
        self.config.write_text(json.dumps(cfg))
        self.run_defaults()
        self.assertEqual(json.loads(self.config.read_text())['background']['wallpaperPath'], old)

    def test_custom_wallpaper_named_like_fallback_is_preserved(self):
        old = '/home/user/assets/wallpapers/qs-niri.jpg'
        self.config.write_text(json.dumps({'panelFamily': 'harmony', 'background': {'wallpaperPath': old}}))
        self.run_defaults()
        self.assertEqual(json.loads(self.config.read_text())['background']['wallpaperPath'], old)

if __name__ == '__main__': unittest.main()
