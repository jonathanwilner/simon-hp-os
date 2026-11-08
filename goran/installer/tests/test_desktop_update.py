"""Exercise update safety and the build-only path without touching a live profile."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'update-desktop.sh'


class DesktopUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        (self.repo / 'goran/installer').mkdir(parents=True)
        (self.repo / 'goran/installer/simon-home.nix').touch()
        shutil.copyfile(SCRIPT.parent / 'desktop-update-guards.sh', self.repo / 'goran/installer/desktop-update-guards.sh')
        (self.repo / 'flake.nix').touch()
        (self.repo / 'flake.lock').touch()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.stub('uname', 'echo aarch64')
        self.stub('id', 'echo jonathan')
        self.stub('git', '''case "$1" in
ls-files) exit "${TEST_UNTRACKED:-0}" ;;
status) printf '%s' "${TEST_DIRTY:-}" ;;
rev-parse) echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ;;
*) exit 2 ;;
esac''')
        self.stub('nix', '''printf '%s\\n' "$@" > "$TEST_NIX_ARGS"
while [ "$#" -gt 0 ]; do
 if [ "$1" = --out-link ]; then shift; ln -s "$TEST_CANDIDATE" "$1"; exit 0; fi
 shift
done
exit 2''')
        candidate = self.root / 'candidate'
        candidate.mkdir()
        activate = candidate / 'activate'
        activate.write_text('#!/bin/sh\ntouch "$TEST_ACTIVATED"\n')
        activate.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}',
                        XDG_STATE_HOME=str(self.root / 'state'),
                        NOM_DASHBOARD_PROGRESS_FILE=str(self.root / 'progress.json'),
                        TEST_NIX_ARGS=str(self.root / 'nix-args'),
                        TEST_CANDIDATE=str(candidate), TEST_ACTIVATED=str(self.root / 'activated'))

    def stub(self, name, text):
        p = self.bin / name
        p.write_text('#!/bin/sh\n' + text + '\n')
        p.chmod(0o755)

    def run_update(self, *args):
        return subprocess.run(['bash', str(SCRIPT), '--checkout', str(self.repo), *args],
                              env=self.env, text=True, capture_output=True)

    def test_build_only_never_activates(self):
        result = self.run_update('--worker', '--build-only', '--no-pull')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('No profile activated', result.stdout)
        self.assertIn('.#homeConfigurations.simon-daytona.activationPackage', (self.root / 'nix-args').read_text())
        self.assertIn('--no-update-lock-file', (self.root / 'nix-args').read_text())
        self.assertFalse((self.root / 'activated').exists())
        self.assertEqual(len(list((self.root / 'state/simon-desktop-update').glob('*/source-revision'))), 1)

    def test_worker_fetches_release_merge_tool_and_records_provenance(self):
        self.stub('git', '\n'.join([
            'case "$1" in',
            'ls-files|status) exit 0 ;;',
            'rev-parse) echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ;;',
            'fetch) printf "%s\\n" "$@" > "$TEST_FETCH_ARGS" ;;',
            'show) cat "$TEST_MERGE_HELPER" ;;',
            '*) exit 2 ;;',
            'esac',
        ]))
        helper = self.root / 'merge-helper'
        helper.write_text('mkdir -p "$2"\nprintf "%s\\n" "$3" > "$2/release-channel"\n'
                          'echo bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb > "$2/published-revision"\n')
        self.env['TEST_MERGE_HELPER'] = str(helper)
        self.env['TEST_FETCH_ARGS'] = str(self.root / 'fetch-args')
        result = self.run_update('--worker', '--build-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('refs/heads/fleet-stable', (self.root / 'fetch-args').read_text())
        records = list((self.root / 'state/simon-desktop-update').glob('*/published-revision'))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].read_text().strip(), 'b' * 40)
        self.assertEqual((records[0].parent / 'release-channel').read_text().strip(), 'fleet-stable')
        self.assertFalse((self.root / 'activated').exists())

    def test_untracked_required_source_rejected(self):
        self.env['TEST_UNTRACKED'] = '1'
        result = self.run_update('--worker', '--build-only', '--no-pull')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not tracked in Git', result.stderr)
        self.assertFalse((self.root / 'nix-args').exists())

    def test_dirty_checkout_rejected(self):
        self.env['TEST_DIRTY'] = ' M flake.nix'
        result = self.run_update('--worker', '--build-only', '--no-pull')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must be committed', result.stderr)

    def test_no_pull_cannot_activate(self):
        result = self.run_update('--no-pull')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--no-pull requires --build-only', result.stderr)

    def test_other_user_cannot_activate(self):
        result = self.run_update('--worker')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Simon’s own login', result.stderr)

    def test_worker_requires_tracker(self):
        self.env.pop('NOM_DASHBOARD_PROGRESS_FILE')
        result = self.run_update('--worker', '--build-only', '--no-pull')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('through nom-tmux', result.stderr)


if __name__ == '__main__':
    unittest.main()
