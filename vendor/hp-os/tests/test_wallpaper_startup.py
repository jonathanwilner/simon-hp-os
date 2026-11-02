"""Exercise first-run wallpaper and welcome dispatch from the patched service."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(os.environ.get('HP_OS_UPSTREAM', '/tmp/hp-os-upstream'))

class FirstRunWallpaper(unittest.TestCase):
    def test_first_run_preserves_harmony_wallpaper_and_waits_for_config(self):
        node = shutil.which('node')
        if not node or not (UPSTREAM / 'services/FirstRunExperience.qml').exists():
            self.skipTest('Node and pinned upstream required')
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / 'services').mkdir()
            shutil.copy2(UPSTREAM / 'services/FirstRunExperience.qml', base / 'services')
            subprocess.run(['patch', '-s', '-p1', '-d', str(base), '-i', str(ROOT / 'patches/harmony-wallpaper-startup.patch')], check=True)
            text = (base / 'services/FirstRunExperience.qml').read_text()
            # Execute the actual dispatch and startup bodies with service boundaries mocked.
            handle = text.split('    function handleFirstRun(): void {', 1)[1].split('\n    }', 1)[0]
            load = text.split('    function load() {', 1)[1].split('\n    }', 1)[0]
            program = '''
const assert = require('node:assert/strict');
const calls = [];
const Config = {ready: false, options: {panelFamily: 'harmony'}};
const root = {defaultWallpaperPath: '/bundled/qs-niri.jpg'};
const Quickshell = {execDetached: args => calls.push(args), shellPath: x => x};
const Directories = {wallpaperSwitchScriptPath: '/switchwall.sh'};
const checkFirstRunProc = {running: false};
const listWallpapersProc = {running: false};
'''+ '\nfunction load() {' + load + '\n}\nfunction handle() {' + handle + '''
}
load(); assert.equal(checkFirstRunProc.running, false);
Config.ready = true; load(); assert.equal(checkFirstRunProc.running, true);
handle(); assert.equal(calls.length, 0, 'Harmony must not launch the upstream wizard or change wallpaper');
calls.length = 0; Config.options.panelFamily = 'ii';
handle(); assert.deepEqual(calls[0], ['/switchwall.sh', '/bundled/qs-niri.jpg']);
assert.equal(calls.length, 2);
assert.deepEqual(calls[1], ['scripts/inir', 'welcome']);
'''
            subprocess.run([node, '-e', program], check=True)
            self.assertIn('function onReadyChanged()', text)

if __name__ == '__main__':
    unittest.main()
