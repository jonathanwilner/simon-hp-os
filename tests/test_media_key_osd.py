import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class MediaKeyOverlayTests(unittest.TestCase):
    def test_declarative_bindings_use_shared_helper(self):
        source = (ROOT / "goran/desktop/niri.nix").read_text()
        for line in source.splitlines():
            if "XF86Audio" in line:
                self.assertIn("${mediaKeys}/bin/hp-os-media-key", line)
        self.assertIn("pkgs.python3 mediaKeys", source)

    def test_actions_and_headless_fallback(self):
        for action, expected in [('volume-up', 'volume'), ('volume-down', 'volume'), ('mute', 'volume'), ('mic-mute', 'mic'), ('next', 'media next'), ('previous', 'media previous'), ('brightness-osd', 'brightnessValue 45'), ('brightness-up', 'brightnessValue 65'), ('brightness-down', 'brightnessValue 65')]:
            with self.subTest(action=action), tempfile.TemporaryDirectory() as d:
                for name in ['wpctl', 'playerctl', 'hp-os', 'brightnessctl']:
                    p=Path(d,name)
                    p.write_text('#!/bin/sh\necho "'+name+' $*" >> "$TEST_LOG"\n')
                    if name == 'brightnessctl': p.write_text(p.read_text() + 'echo device,backlight,65,65%,100\n')
                    p.chmod(0o755)
                env=dict(os.environ, PATH=d+':'+os.environ['PATH'], TEST_LOG=d+'/log')
                subprocess.run(['bash',str(ROOT/'fleet/media-key.sh'),action,'45'],env=env,check=True)
                self.assertIn('hp-os ipc osd '+expected, Path(d,'log').read_text())
                Path(d,'hp-os').write_text('#!/bin/sh\nexit 1\n')
                subprocess.run(['bash',str(ROOT/'fleet/media-key.sh'),action,'45'],env=env,check=True)

    def test_explicit_steps_preserved_and_invalid_steps_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ('wpctl', 'brightnessctl'):
                p = Path(d, name)
                p.write_text('#!/bin/sh\necho "$*" >> "$TEST_LOG"\n' +
                             ('echo device,backlight,65,65%,100\n' if name == 'brightnessctl' else ''))
                p.chmod(0o755)
            env = dict(os.environ, PATH=d+':'+os.environ['PATH'], TEST_LOG=d+'/log')
            for action, expected in [('volume-up', '10%+'), ('volume-down', '10%-'),
                                     ('brightness-up', '+10%'), ('brightness-down', '10%-')]:
                subprocess.run(['bash', str(ROOT/'fleet/media-key.sh'), action, '10'], env=env, check=True)
                self.assertIn(expected, Path(d, 'log').read_text())
            before = Path(d, 'log').read_text()
            for step in ('0', '101', '-1', 'invalid'):
                result = subprocess.run(['bash', str(ROOT/'fleet/media-key.sh'), 'brightness-up', step], env=env)
                self.assertEqual(result.returncode, 2)
            self.assertEqual(before, Path(d, 'log').read_text())

    def test_invalid_brightness_rejected(self):
        for value in ['-1', '101', 'NaN', '']:
            self.assertNotEqual(subprocess.run(['bash',str(ROOT/'fleet/media-key.sh'),'brightness-osd',value],capture_output=True).returncode,0)

    def test_external_level_is_display_only_and_both_surfaces_use_it(self):
        patch=(ROOT/'vendor/HP-OSShell/patches/hpos-media-key-osd.patch').read_text()
        self.assertIn('function brightnessValue(percent: string)',patch)
        self.assertNotIn('setBrightness(',patch)
        self.assertEqual(patch.count('GlobalStates.externalBrightnessPercent / 100'),2)
        self.assertIn('Qt.callLater',patch)

if __name__=='__main__':unittest.main()
