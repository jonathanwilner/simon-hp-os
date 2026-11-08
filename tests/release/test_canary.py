import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('canary', Path(__file__).resolve().parents[2] / 'fleet/release/canary.py')
canary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(canary)
REV = 'a' * 40


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.generation = self.root / 'generation'
        self.revision = self.generation / 'home-files/.config/hp-os-fleet/revision'
        self.revision.parent.mkdir(parents=True)
        self.revision.write_text(REV + '\n')
        self.active = self.root / 'active'
        self.active.symlink_to(self.generation)
        self.record = self.root / 'installed.json'
        self.record.write_text(json.dumps({'fleet_revision': REV, 'generation': str(self.generation)}))
        self.args = SimpleNamespace(system='x86_64-linux', revision=REV, installed_record=self.record,
                                    active_generation=self.active, niri_socket='/test/niri.sock')

    def test_generation_and_embedded_revision_required(self):
        self.assertEqual(canary.installed_generation(self.record, self.active, REV), self.generation)
        self.revision.write_text('b' * 40)
        with self.assertRaisesRegex(canary.ProbeError, 'embed'):
            canary.installed_generation(self.record, self.active, REV)

    def test_record_alone_cannot_prove_activation(self):
        other = self.root / 'other'
        other.mkdir()
        self.active.unlink()
        self.active.symlink_to(other)
        with self.assertRaisesRegex(canary.ProbeError, 'generation differs'):
            canary.installed_generation(self.record, self.active, REV)

    def test_wrong_revision_fails(self):
        with self.assertRaisesRegex(canary.ProbeError, 'revision differs'):
            canary.installed_generation(self.record, self.active, 'b' * 40)

    def test_non_full_revision_fails(self):
        with self.assertRaisesRegex(canary.ProbeError, 'full Git SHA'):
            canary.installed_generation(self.record, self.active, 'main')

    def test_executable_must_be_immutable_store_package(self):
        self.assertEqual(canary.store_root('/nix/store/' + 'a' * 32 + '-ghostty/bin/.ghostty-wrapped'), '/nix/store/' + 'a' * 32 + '-ghostty')
        with self.assertRaises(canary.ProbeError):
            canary.store_root('/tmp/ghostty/bin/ghostty')

    def sockets(self, display='/run/user/1000/wayland-1', compositor=42, state='ESTAB'):
        return (f'u_str {state} 0 0 * 111 * 222 users:(("ghostty",pid=100,fd=7))\n'
                f'u_str ESTAB 0 0 {display} 222 * 111 users:(("niri",pid={compositor},fd=8))\n')

    def test_actual_peer_socket_is_proof(self):
        result = canary.wayland_peer(self.sockets(), 100, '/run/user/1000/wayland-1', 42)
        self.assertEqual(result['server_inode'], '222')

    def test_different_display_or_compositor_fails(self):
        for data in [self.sockets(display='/tmp/X11'), self.sockets(compositor=43), self.sockets(state='LISTEN')]:
            with self.assertRaises(canary.ProbeError):
                canary.wayland_peer(data, 100, '/run/user/1000/wayland-1', 42)

    def test_environment_without_connection_is_not_proof(self):
        with self.assertRaises(canary.ProbeError):
            canary.wayland_peer('', 100, '/run/user/1000/wayland-1', 42)

    def run_probe(self, windows, evidence=None):
        with patch.object(canary.platform, 'machine', return_value='x86_64'), \
             patch.object(canary.platform, 'system', return_value='Linux'), \
             patch.object(canary, 'niri_windows', return_value=(windows, 42)), \
             patch.object(canary.subprocess, 'run', return_value=SimpleNamespace(stdout='')), \
             patch.object(canary, 'process_evidence', side_effect=evidence or (lambda *args: {'window_registered': True})):
            return canary.probe(self.args)

    def test_missing_window_never_passes(self):
        with self.assertRaisesRegex(canary.ProbeError, 'No accepted ghostty'):
            self.run_probe([])

    def test_missing_moonlight_never_passes(self):
        with self.assertRaisesRegex(canary.ProbeError, 'No accepted moonlight'):
            self.run_probe([{'app_id': 'com.mitchellh.ghostty'}])

    def test_rejected_process_never_passes(self):
        with self.assertRaisesRegex(canary.ProbeError, 'different package'):
            self.run_probe([{'app_id': 'com.mitchellh.ghostty'}], canary.ProbeError('different package'))

    def test_both_windows_recorded_and_scope_explicit(self):
        result = self.run_probe([{'app_id': 'com.mitchellh.ghostty'}, {'app_id': 'com.moonlight_stream.Moonlight'}])
        self.assertTrue(result['passed'])
        self.assertEqual(set(result['apps']), {'ghostty', 'moonlight'})
        self.assertIn('excludes visual rendering', result['scope'])

    def test_wrong_architecture_fails_before_ui_probe(self):
        self.args.system = 'aarch64-linux'
        with patch.object(canary.platform, 'machine', return_value='x86_64'), patch.object(canary.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(canary.ProbeError, 'Expected aarch64-linux'):
                canary.probe(self.args)


if __name__ == '__main__':
    unittest.main()
