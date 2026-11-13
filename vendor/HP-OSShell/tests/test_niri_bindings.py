import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('sync_niri', Path(__file__).parents[1] / 'packaging/sync-niri-bindings.py')
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class BindingSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'regular.kdl'
        self.target = self.root / 'hpos.kdl'
        self.baseline = self.root / 'baseline.kdl'
        self.validator = self.root / 'niri'
        self.validator.write_text('#!/bin/sh\ntest "$1" = validate && test "$2" = --config && test -f "$3"\n')
        self.validator.chmod(0o755)
        self.default = '''input { keyboard { xkb { layout "us"; }; } }
binds {
Mod+L { spawn "hp-os" "ipc" "lock" "activate"; }
Mod+C { spawn "hp-os" "ipc" "hpos" "controlCenter"; }
Mod+Comma { spawn "hp-os" "settings"; }
Mod+Return { spawn "foot"; }
}
'''
        self.baseline.write_text(self.default)
        self.target.write_text(self.default)
        self.source.write_text('binds { Mod+L { focus-column-right; }; Mod+C { center-column; }; Mod+Comma { consume-window-into-column; }; }\n')

    def sync(self):
        MOD.sync(self.source, self.target, self.baseline, str(self.validator))

    def test_dms_media_steps_and_unknown_device(self):
        actions = [
            ('audio', 'increment', '"10"', 'volume-up'),
            ('audio', 'decrement', '"10"', 'volume-down'),
            ('audio', 'mute', '', 'mute'),
            ('audio', 'micmute', '', 'mic-mute'),
            ('brightness', 'increment', '"10" ""', 'brightness-up'),
            ('brightness', 'decrement', '"10" ""', 'brightness-down'),
        ]
        source = 'binds {\n' + '\n'.join(
            f'F{i+1} {{ spawn "dms" "ipc" "call" "{kind}" "{action}" {extra}; }}'
            for i, (kind, action, extra, _) in enumerate(actions)) + '\n}\n'
        self.source.write_text(source)
        self.sync()
        result = self.target.read_text()
        for _, _, extra, action in actions:
            expected = f'"hp-os-media-key" "{action}"' + (' "10"' if extra else '')
            self.assertIn(expected, result)
        self.assertEqual(self.source.read_text(), source)
        for extra in ('"10" "panel1"', '"0" ""', '"101" ""'):
            with self.assertRaises(ValueError):
                MOD.adapt(f'F1 {{ spawn "dms" "ipc" "call" "brightness" "increment" {extra}; }}')

    def test_direct_host_media_commands_keep_hardware_and_add_feedback(self):
        import json
        import subprocess
        commands = [
            (["/nix/store/example/bin/wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "10%+"], "hp-os ipc osd volume"),
            (["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"], "hp-os ipc osd mic"),
            (["goran-brightness", "up"], "hp-os-media-key brightness-osd"),
            (["playerctl", "play-pause"], "hp-os ipc osd media play"),
        ]
        for argv, expected in commands:
            original = 'F1 { spawn ' + ' '.join(json.dumps(v) for v in argv) + '; }'
            result = MOD.adapt(original)
            action = MOD.nodes(result)[0].children[0]
            values = [t.value for t in action.head]
            self.assertEqual(values[1:3], ['sh', '-c'])
            self.assertEqual(values[5:], argv)
            self.assertIn(expected, values[3])
            self.assertEqual(subprocess.run(['sh', '-n', '-c', values[3]]).returncode, 0)
            self.assertEqual(MOD.adapt(result), result)
        self.assertEqual(MOD.adapt('F1 { spawn "wpctl" "status"; }'), 'F1 { spawn "wpctl" "status"; }')

    def test_native_conflicts_and_idempotence(self):
        self.sync()
        first = self.target.read_text()
        self.assertIn('focus-column-right', first)
        self.assertIn('center-column', first)
        self.assertIn('consume-window-into-column', first)
        self.assertIn('Mod+Return', first)
        self.assertNotIn('"lock"', first)
        self.assertTrue(first.startswith('input {'))
        backup = self.target.with_suffix('.kdl.before-bindings-sync')
        self.assertEqual(backup.read_text(), self.default)
        self.sync()
        self.assertEqual(first, self.target.read_text())
        self.assertEqual(backup.read_text(), self.default)

    def test_includes_nested_comments_strings_and_only_binds(self):
        (self.root / 'child.kdl').write_text('/* { nested /* } */ } */\nspawn-at-startup "DONT-RUN"\nbinds { Mod+X { spawn "/exact/app" "}" "// literal"; }; }\n')
        self.source.write_text('include "child.kdl"\ninclude optional=true "missing.kdl"\ninput { mouse { natural-scroll; }; }\n')
        self.sync()
        result = self.target.read_text()
        self.assertIn('spawn "/exact/app" "}" "// literal"', result)
        self.assertNotIn('DONT-RUN', result)
        self.assertNotIn('natural-scroll', result)

    def test_custom_override_and_future_source_updates(self):
        self.target.write_text(self.default.replace('Mod+C { spawn "hp-os" "ipc" "hpos" "controlCenter"; }', 'Mod+C { spawn "/custom/action"; }').replace('binds {', 'binds {\nMod+Z { spawn "/custom/extra"; }'))
        self.sync()
        self.source.write_text(self.source.read_text().replace('focus-column-right', 'focus-column-left'))
        self.sync()
        text = self.target.read_text()
        self.assertIn('/custom/action', text)
        self.assertIn('/custom/extra', text)
        self.assertIn('focus-column-left', text)

    def test_shell_adaptation(self):
        self.source.write_text('binds {\nMod+Space { spawn "/nix/store/pkg/bin/dms" "ipc" "call" "spotlight" "toggle"; }\nMod+P { spawn "dms" "ipc" "call" "wallhavenCarousel" "discover"; }\nMod+K { spawn "dms" "ipc" "call" "lock" "lock"; }\n}\n')
        self.sync()
        text = self.target.read_text()
        self.assertIn('"ipc" "overview" "toggle"', text)
        self.assertIn('"ipc" "wallpaperSelector" "toggle"', text)
        self.assertIn('"ipc" "lock" "activate"', text)
        self.assertNotIn('"dms"', text)

    def test_unsupported_duplicate_and_cycle_fail_closed(self):
        for source in ['binds { Mod+L { quit; }; Mod+L { quit; }; }',
                       'binds { Mod+L { spawn "dms" "ipc" "call" "unknown"; }; }',
                       'binds { Mod+L { spawn "sh" "-c" "dms ipc call spotlight toggle"; }; }',
                       'binds { Mod+L { spawn r#"unterminated; }; }',
                       'include "regular.kdl"']:
            self.source.write_text(source)
            with self.assertRaises(ValueError): self.sync()
            self.assertEqual(self.target.read_text(), self.default)
            self.assertFalse(self.target.with_suffix('.kdl.bindings-state.json').exists())

    def test_disabled_nodes_bindings_actions_and_entries(self):
        self.source.write_text('''/-output "eDP-1" { scale 2; }
/-window-rule { match app-id=r#"^foo{bar}$"#; }
/-include "absent.kdl"
/-binds { Mod+L { quit; }; }
binds {
/-Mod+L { quit; }
Mod+L { /-spawn "dms" "ipc" "call" "unknown"; focus-column-right; }
Mod+P { spawn /-"ignored" "dms" /-unused="value" "ipc" "call" "wallhaven" "toggle"; }
}
''')
        self.sync()
        result = self.target.read_text()
        self.assertIn('focus-column-right', result)
        self.assertNotIn('quit', result)
        self.assertNotIn('eDP-1', result)
        self.assertIn('"ipc" "wallpaperSelector" "toggle"', result)
        self.assertEqual(len(MOD.nodes('binds { /-Mod+A { quit; }; }')[0].children), 0)

    def test_raw_strings_and_continuation(self):
        self.source.write_text(r'''window-rule { match app-id=r#"^org\.foo$"#; }
binds {
Mod+X { spawn r"/exact/app" r##"literal \" } // #"##; }
Mod+P { spawn "dms" \ // continued comment
 "ipc" "call" "spotlight" "toggle"; }
}
''')
        self.sync()
        result = self.target.read_text()
        self.assertIn('r##"literal', result)
        self.assertIn('"ipc" "overview" "toggle"', result)
        self.assertEqual(MOD.tokens('#"literal } //"#')[0].value, 'literal } //')
        with self.assertRaises(ValueError): MOD.nodes('binds \\ nope')

    def test_validation_failure_does_not_write(self):
        self.validator.write_text('#!/bin/sh\nexit 1\n')
        with self.assertRaises(Exception): self.sync()
        self.assertEqual(self.target.read_text(), self.default)
        self.assertFalse(self.target.with_suffix('.kdl.before-bindings-sync').exists())
        self.assertFalse(self.target.with_suffix('.kdl.bindings-state.json').exists())

    def test_session_wrappers_are_adapted_without_shared_session_effects(self):
        self.source.write_text('binds { Mod+E { spawn "/home/user/.local/bin/niri-shutdown"; }; Mod+K { spawn "vnc-safe-spawn" "lock-screen"; }; Mod+T { spawn "vnc-safe-spawn" "/exact/terminal" "--title" "test"; }; }')
        self.sync()
        text = self.target.read_text()
        self.assertIn('Mod+E { quit;', text)
        self.assertIn('"ipc" "lock" "activate"', text)
        self.assertIn('spawn "/exact/terminal" "--title" "test"', text)
        self.assertNotIn('vnc-safe-spawn', text)
        self.assertNotIn('niri-shutdown', text)

    def test_symlinked_config_resolves_includes_beside_config_not_store(self):
        store = self.root / 'store'
        store.mkdir()
        (store / 'config.kdl').write_text('include "local.kdl"')
        (self.root / 'local.kdl').write_text('binds { Mod+Y { spawn "/local/app"; }; }')
        self.source.unlink()
        self.source.symlink_to(store / 'config.kdl')
        self.sync()
        self.assertIn('/local/app', self.target.read_text())

    def test_missing_source_skips(self):
        self.source.unlink()
        self.sync()
        self.assertEqual(self.target.read_text(), self.default)


if __name__ == '__main__': unittest.main()
