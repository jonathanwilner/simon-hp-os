import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'fleet/release'))
SPEC = importlib.util.spec_from_file_location('launch_test', ROOT / 'fleet/release/launch_test.py')
launch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launch)


class LaunchTests(unittest.TestCase):
    def window(self, ident, pid, app='ghostty'):
        return {'id': ident, 'pid': pid, 'app_id': launch.APPS[app]}

    def test_old_window_and_old_pid_cannot_pass(self):
        windows = [self.window(1, 10), self.window(2, 11), self.window(3, 12)]
        with mock.patch.object(launch, 'token_matches', return_value=True):
            self.assertEqual(launch.owned_windows(windows, {1}, {11}, 'test'), [windows[2]])

    def test_new_unrelated_window_is_never_owned(self):
        with mock.patch.object(launch, 'token_matches', return_value=False):
            self.assertEqual(launch.owned_windows([self.window(2, 22)], {1}, {11}, 'test'), [])

    def test_cleanup_closes_only_owned_new_windows(self):
        old = self.window(1, 10)
        own = self.window(2, 20)
        unrelated = self.window(3, 30)
        inventories = [([old, own, unrelated], 99), ([old, own, unrelated], 99), ([old, unrelated], 99)]
        with mock.patch.object(launch.canary, 'niri_windows', side_effect=inventories), \
             mock.patch.object(launch, 'token_matches', side_effect=lambda pid, token: pid == 20), \
             mock.patch.object(launch, 'action') as action:
            self.assertEqual(launch.close_owned('/socket', {1}, {10}, 'token', {}), [])
            action.assert_called_once_with('/socket', 'close-window', '--id', '2')

    def test_cleanup_rechecks_id_and_pid_before_close(self):
        own = self.window(2, 20)
        reused = self.window(2, 30)
        with mock.patch.object(launch.canary, 'niri_windows', side_effect=[([own], 99), ([reused], 99), ([reused], 99)]), \
             mock.patch.object(launch, 'token_matches', side_effect=lambda pid, token: pid == 20), \
             mock.patch.object(launch, 'action') as action:
            self.assertEqual(launch.close_owned('/socket', set(), set(), 'token', {}), [])
            action.assert_not_called()

    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name)
        launcher = home / '.local/bin/fuzzel-launch'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\nexec "$@"\n')
        launcher.chmod(0o755)
        generation = home / 'generation'
        expected = generation / 'home-files/.local/bin/fuzzel-launch'
        expected.parent.mkdir(parents=True)
        expected.symlink_to(launcher)
        args = argparse.Namespace(revision='a' * 40, system='x86_64-linux', installed_record=home / 'record',
                                  active_generation=generation, niri_socket='/socket', timeout=.001)
        return home, generation, args

    def test_old_windows_only_fail_and_cleanup_runs(self):
        home, generation, args = self.fixture()
        old = [self.window(1, 10), self.window(2, 11, 'moonlight')]
        with mock.patch.object(launch.Path, 'home', return_value=home), \
             mock.patch.object(launch.canary, 'installed_generation', return_value=generation), \
             mock.patch.object(launch.canary, 'niri_windows', return_value=(old, 99)), \
             mock.patch.object(launch, 'process_ids', return_value={10, 11}), \
             mock.patch.object(launch, 'action'), \
             mock.patch.object(launch.time, 'sleep'), \
             mock.patch.object(launch, 'close_owned', return_value=[]) as cleanup:
            with self.assertRaisesRegex(launch.canary.ProbeError, 'Fresh tagged'):
                launch.launch_test(args)
            cleanup.assert_called_once()

    def test_success_uses_fresh_evidence_and_launcher_hash(self):
        home, generation, args = self.fixture()
        fresh = [self.window(2, 20), self.window(3, 30, 'moonlight')]
        with mock.patch.object(launch.Path, 'home', return_value=home), \
             mock.patch.object(launch.canary, 'installed_generation', return_value=generation), \
             mock.patch.object(launch.canary, 'niri_windows', side_effect=[([], 99), (fresh, 99)]), \
             mock.patch.object(launch, 'process_ids', return_value={1}), \
             mock.patch.object(launch, 'token_matches', return_value=True), \
             mock.patch.object(launch, 'action') as action, \
             mock.patch.object(launch.canary, 'process_evidence', side_effect=lambda w, *args: {'pid': w['pid'], 'window_id': w['id']}), \
             mock.patch.object(launch.canary, 'probe', return_value={'passed': True, 'revision': args.revision, 'apps': {'old': {}}}), \
             mock.patch.object(launch.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='')), \
             mock.patch.object(launch, 'close_owned', return_value=[]) as cleanup:
            result = launch.launch_test(args)
            self.assertTrue(result['fresh_launch'])
            self.assertEqual(result['apps']['ghostty']['pid'], 20)
            self.assertEqual(len(result['launcher']['source_sha256']), 64)
            self.assertEqual(action.call_count, 2)
            argv = action.call_args_list[1].args
            self.assertTrue(str(argv[-1]).endswith('/home-path/bin/moonlight'))
            cleanup.assert_called_once()


if __name__ == '__main__':
    unittest.main()
