import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('consumers', ROOT / 'fleet/release/consumers.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REVISION = 'a' * 40

class ConsumerRetries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / 'remote.git'
        self.source = self.base / 'source'
        self.command('git', 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.command('git', 'clone', str(self.remote), str(self.source))
        self.git('config', 'user.name', 'Fleet Test')
        self.git('config', 'user.email', 'fleet-test@example.invalid')
        (self.source / 'flake.lock').write_text(json.dumps({'revision': 'old'}) + '\n')
        self.git('add', 'flake.lock')
        self.git('commit', '-m', 'Initial consumer')
        self.git('push', 'origin', 'main')
        self.initial = self.git('rev-parse', 'HEAD')
        self.entry = {'checkout': str(self.source), 'branch': 'main', 'flakes': ['.'], 'checks': [['test-validator']]}
        self.validation_fails = False
        self.push_fails = False
        self.validations = 0
        self.real_run = c.run
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'XDG_STATE_HOME': str(self.base / 'state')}).start()
        patch.object(c, 'run', side_effect=self.fake_run).start()
    def command(self, *args):
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    def git(self, *args):
        return self.command('git', '-C', str(self.source), *args)
    def fake_run(self, args, cwd=None):
        if args[0] == 'nix':
            (Path(cwd) / 'flake.lock').write_text(json.dumps({'revision': args[-1].rsplit('/', 1)[1]}) + '\n')
            return ''
        if args[0] == 'test-validator':
            self.validations += 1
            if self.validation_fails:
                raise subprocess.CalledProcessError(1, args)
            return ''
        if args[0] == 'git' and 'push' in args and self.push_fails:
            raise subprocess.CalledProcessError(1, args)
        return self.real_run(args, cwd=cwd)
    def assert_source_untouched(self):
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.initial)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(json.loads((self.source / 'flake.lock').read_text()), {'revision': 'old'})
        self.assertEqual(len([l for l in self.git('worktree', 'list', '--porcelain').splitlines() if l.startswith('worktree ')]), 1)
    def test_failed_validation_preserves_checkout_and_retries(self):
        self.validation_fails = True
        with self.assertRaises(subprocess.CalledProcessError): c.reconcile(self.entry, REVISION)
        self.assert_source_untouched()
        self.assertEqual(self.command('git', '--git-dir', str(self.remote), 'rev-parse', 'main'), self.initial)
        self.validation_fails = False
        self.assertEqual(c.reconcile(self.entry, REVISION)['state'], 'pushed')
        self.assert_source_untouched()
    def test_failed_push_retains_validated_commit_then_retries(self):
        self.push_fails = True
        with self.assertRaises(subprocess.CalledProcessError): c.reconcile(self.entry, REVISION)
        self.assert_source_untouched()
        pending = list((self.base / 'state/hp-os-fleet/consumers').glob('*.json'))
        self.assertEqual(len(pending), 1)
        candidate = json.loads(pending[0].read_text())['candidate']
        self.push_fails = False
        result = c.reconcile(self.entry, REVISION)
        self.assertEqual(result['commit'], candidate)
        self.assertEqual(self.validations, 1)
        self.assertFalse(pending[0].exists())
        self.assert_source_untouched()
    def test_same_revision_does_not_duplicate_commit(self):
        first = c.reconcile(self.entry, REVISION)
        second = c.reconcile(self.entry, REVISION)
        self.assertEqual(second['state'], 'current')
        self.assertEqual(second['commit'], first['commit'])
        self.assertEqual(self.validations, 1)
        self.assert_source_untouched()
    def test_remote_advance_regenerates_and_revalidates(self):
        self.push_fails = True
        with self.assertRaises(subprocess.CalledProcessError): c.reconcile(self.entry, REVISION)
        other = self.base / 'other'
        self.command('git', 'clone', str(self.remote), str(other))
        self.command('git', '-C', str(other), 'config', 'user.name', 'Other')
        self.command('git', '-C', str(other), 'config', 'user.email', 'other@example.invalid')
        (other / 'other.txt').write_text('Another machine\n')
        self.command('git', '-C', str(other), 'add', 'other.txt')
        self.command('git', '-C', str(other), 'commit', '-m', 'Remote advanced')
        self.command('git', '-C', str(other), 'push', 'origin', 'main')
        advanced = self.command('git', '-C', str(other), 'rev-parse', 'HEAD')
        self.push_fails = False
        result = c.reconcile(self.entry, REVISION)
        self.assertEqual(self.git('rev-parse', result['commit'] + '^'), advanced)
        self.assertEqual(self.validations, 2)
        self.assert_source_untouched()
    def test_changed_checks_invalidate_pending_validation(self):
        self.push_fails = True
        with self.assertRaises(subprocess.CalledProcessError): c.reconcile(self.entry, REVISION)
        self.entry['checks'] = [['test-validator', 'new-policy']]
        self.push_fails = False
        c.reconcile(self.entry, REVISION)
        self.assertEqual(self.validations, 2)

if __name__ == '__main__': unittest.main()
