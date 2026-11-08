import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('status', Path(__file__).parents[2] / 'fleet/release/status.py')
status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(status)


class DriftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / 'remote'
        self.repo = self.base / 'repo'
        subprocess.run(['git', 'init', '--bare', str(self.remote)], check=True, capture_output=True)
        subprocess.run(['git', 'clone', str(self.remote), str(self.repo)], check=True, capture_output=True)
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'file').write_text('first')
        self.git('add', '.')
        self.git('commit', '-m', 'first')
        self.revision = self.git('rev-parse', 'HEAD')
        self.git('push', 'origin', 'HEAD:main', 'HEAD:fleet-stable')
        self.generation = self.base / 'generation'
        self.generation.mkdir()
        self.active = self.base / 'active'
        self.active.symlink_to(self.generation)
        self.record = self.base / 'installed.json'
        self.record.write_text(json.dumps(dict(source_revision=self.revision, fleet_revision=self.revision, generation=str(self.generation))))
        self.args = argparse.Namespace(checkout=self.repo, remote='origin', release_url='', offline=False,
                                       consumer_lock=None, input='desktop-fleet', installed_record=self.record,
                                       active_generation=self.active)

    def git(self, *args):
        return status.git(self.repo, *args)

    def report(self):
        return status.collect(self.args)

    def test_current_requires_remote_pin_and_active_generation(self):
        self.assertEqual(self.report()['status'], 'current')

    def test_local_commit_is_unpushed_and_activation_pending(self):
        (self.repo / 'file').write_text('second')
        self.git('commit', '-am', 'second')
        report = self.report()
        self.assertEqual(report['checks']['publication']['commits'], 1)
        self.assertEqual(report['checks']['activation']['status'], 'pending')

    def test_other_branch_publication_counts_as_pushed(self):
        (self.repo / 'file').write_text('second')
        self.git('commit', '-am', 'second')
        self.git('push', 'origin', 'HEAD:feature')
        report = self.report()
        self.assertEqual(report['checks']['publication']['status'], 'published')
        self.assertEqual(report['checks']['release_pin']['status'], 'differs')

    def test_offline_is_unknown(self):
        self.args.offline = True
        report = self.report()
        self.assertEqual(report['status'], 'unknown')
        self.assertEqual(report['checks']['publication']['status'], 'unknown')

    def test_stale_activation_record_is_unknown(self):
        self.active.unlink()
        other = self.base / 'other'
        other.mkdir()
        self.active.symlink_to(other)
        self.assertEqual(self.report()['checks']['activation']['status'], 'unknown')

    def test_missing_release_is_unknown(self):
        self.git('push', 'origin', ':fleet-stable')
        self.assertEqual(self.report()['checks']['release_pin']['status'], 'unknown')

    def test_consumer_pin_is_independent_of_consumer_source(self):
        lock = self.base / 'flake.lock'
        lock.write_text(json.dumps({'root': 'root', 'nodes': {'root': {'inputs': {'desktop-fleet': 'fleet'}}, 'fleet': {'locked': {'rev': self.revision}}}}))
        self.args.consumer_lock = lock
        (self.repo / 'file').write_text('consumer change')
        self.git('commit', '-am', 'consumer')
        report = self.report()
        self.assertEqual(report['checks']['release_pin']['status'], 'current')
        self.assertEqual(report['checks']['activation']['status'], 'current')

    def test_separate_release_remote_and_generic_record(self):
        self.args.release_url = str(self.remote)
        lock = self.base / 'consumer.lock'
        lock.write_text(json.dumps({'nodes': {'root': {'inputs': {'desktop-fleet': 'fleet'}}, 'fleet': {'locked': {'rev': self.revision}}}}))
        self.args.consumer_lock = lock
        self.record.write_text(json.dumps(dict(fleet_revision=self.revision, generation=str(self.generation))))
        self.assertEqual(self.report()['checks']['activation']['status'], 'current')
        self.assertEqual(self.report()['checks']['release_pin']['status'], 'current')

    def test_missing_record_is_unknown(self):
        self.record.unlink()
        self.assertEqual(self.report()['checks']['activation']['status'], 'unknown')

    def test_simon_directory_record(self):
        record = self.base / 'simon-record'
        record.mkdir()
        (record / 'source-revision').write_text(self.revision)
        (record / 'published-revision').write_text(self.revision)
        (record / 'candidate').symlink_to(self.generation)
        self.args.installed_record = record
        self.assertEqual(self.report()['checks']['activation']['status'], 'current')

    def test_dirty_tree_reported(self):
        (self.repo / 'file').write_text('uncommitted')
        self.assertEqual(self.report()['checks']['working_tree']['status'], 'dirty')


if __name__ == '__main__':
    unittest.main()
