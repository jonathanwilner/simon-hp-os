import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import test_status as fixtures

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'fleet/release'))
SPEC = importlib.util.spec_from_file_location('report', ROOT / 'fleet/release/report.py')
reporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reporter)


class ReportTests(fixtures.DriftTests):
    def report(self):
        return reporter.collect(self.args)

    def test_atomic_report_replaces_prior_and_leaves_no_temp(self):
        path = self.base / 'report.json'
        path.write_text('old')
        report = self.report()
        reporter.persist(report, path)
        self.assertEqual(json.loads(path.read_text())['status'], 'current')
        self.assertFalse(list(self.base.glob('.report.json.*')))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_report_never_fetches_all_branches(self):
        original = reporter.status.git
        with mock.patch.object(reporter.status, 'git', wraps=original) as git:
            self.assertEqual(self.report()['status'], 'current')
        for call in git.call_args_list:
            self.assertNotIn('+refs/heads/*:refs/remotes/origin/*', call.args)
            self.assertNotIn('--prune', call.args)

    def test_generic_record_without_source_revision(self):
        self.record.write_text(json.dumps(dict(fleet_revision=self.revision, generation=str(self.generation))))
        self.assertEqual(self.report()['checks']['activation']['status'], 'current')

    def test_generic_unknown_revision_is_unknown(self):
        self.record.write_text(json.dumps(dict(fleet_revision='unknown', generation=str(self.generation))))
        self.assertEqual(self.report()['checks']['activation']['status'], 'unknown')

    def test_upstream_fetch_is_targeted_for_unpushed_commit(self):
        self.git('branch', '--set-upstream-to=origin/main')
        (self.repo / 'file').write_text('second')
        self.git('commit', '-am', 'second')
        original = reporter.status.git
        with mock.patch.object(reporter.status, 'git', wraps=original) as git:
            self.assertEqual(self.report()['checks']['publication']['status'], 'unpushed')
        fetches = [call.args[1:] for call in git.call_args_list if 'fetch' in call.args]
        self.assertEqual(fetches, [('fetch', '--no-tags', 'origin', 'refs/heads/main')])

    def test_progress_summary_and_exit_codes(self):
        current = self.report()
        with mock.patch.dict(os.environ, {'NOM_DASHBOARD_PROGRESS_FILE': '/tmp/test-progress'}), \
             mock.patch.object(reporter.shutil, 'which', return_value='/bin/progress'), \
             mock.patch.object(reporter.subprocess, 'run') as run:
            reporter.announce(current, self.base / 'latest.json')
            self.assertIn('--label', run.call_args.args[0])
            self.assertIn('Fleet current:', run.call_args.args[0][-1])
        output = self.base / 'latest.json'
        command = [sys.executable, str(ROOT / 'fleet/release/report.py'), '--checkout', str(self.repo),
                   '--release-url', str(self.remote), '--installed-record', str(self.record),
                   '--active-generation', str(self.active), '--output', str(output)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(command + ['--offline'], capture_output=True).returncode, 2)
        (self.repo / 'file').write_text('dirty')
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)

    def test_local_commit_is_unpushed_and_activation_pending(self):
        self.git('branch', '--set-upstream-to=origin/main')
        super().test_local_commit_is_unpushed_and_activation_pending()


if __name__ == '__main__':
    unittest.main()
