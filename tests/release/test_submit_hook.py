import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('publish_hook', Path(__file__).resolve().parents[2] / 'fleet/release/publish.py')
publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish)


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo with spaces'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Hook test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('remote', 'add', 'origin', 'https://github.com/jonathanwilner/simon-hp-os.git')
        self.fixture = self.root / 'fake_publish.py'
        self.fixture.write_text('import json,os,pathlib,sys\nwith pathlib.Path(os.environ["TEST_SUBMITS"]).open("a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n')
        self.env = patch.dict(os.environ, {'TEST_SUBMITS': str(self.root / 'submits'), 'XDG_STATE_HOME': str(self.root / 'state')})
        self.env.start(); self.addCleanup(self.env.stop)
        self.hook = self.repo / '.git/hooks/post-commit'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def install(self):
        with patch.object(publish, '__file__', str(self.fixture)):
            publish.install_hook(self.repo)

    def commit(self):
        self.git('commit', '--allow-empty', '-m', 'Test')

    def wait_submit(self, count=1):
        limit = time.monotonic() + 5
        path = self.root / 'submits'
        while time.monotonic() < limit:
            if path.exists() and len(path.read_text().splitlines()) >= count:
                return [json.loads(row) for row in path.read_text().splitlines()]
            time.sleep(.02)
        self.fail('Hook fixture did not run')

    def test_existing_python_hook_exit_cannot_bypass_submission(self):
        original = '#!/usr/bin/env python3\nfrom pathlib import Path\nPath("prior-hook-ran").touch()\nraise SystemExit(0)\n'
        self.hook.write_text(original); self.hook.chmod(0o755)
        self.install(); self.commit()
        self.assertTrue((self.repo / 'prior-hook-ran').exists())
        self.assertEqual(self.hook.with_name('post-commit.hp-os-fleet-original').read_text(), original)
        self.assertEqual(self.wait_submit()[0], ['drain', '--checkout', str(self.repo)])

    def test_idempotent_install_runs_once(self):
        self.install(); first = self.hook.read_bytes(); self.install()
        self.assertEqual(first, self.hook.read_bytes())
        self.commit(); self.wait_submit(); time.sleep(.1)
        self.assertEqual(len((self.root / 'submits').read_text().splitlines()), 1)

    def test_executable_symlink_preserved(self):
        target = self.root / 'original'; target.write_text('#!/bin/sh\ntouch prior-symlink\nexit 0\n'); target.chmod(0o755)
        self.hook.symlink_to(target)
        self.install(); self.commit(); self.wait_submit()
        self.assertTrue(self.hook.with_name('post-commit.hp-os-fleet-original').is_symlink())
        self.assertTrue((self.repo / 'prior-symlink').exists())

    def test_original_nonzero_exit_preserved(self):
        self.hook.write_text('#!/bin/sh\nexit 17\n'); self.hook.chmod(0o755)
        self.install()
        result = subprocess.run([str(self.hook)], cwd=self.repo)
        self.assertEqual(result.returncode, 17)
        self.wait_submit()

    def test_feature_branch_requires_explicit_submission(self):
        self.git('checkout', '-b', 'feature/test'); self.install(); self.commit()
        time.sleep(.1)
        self.assertFalse((self.root / 'submits').exists())

    def test_origin_rechecked_at_commit_time(self):
        self.install(); self.git('remote', 'set-url', 'origin', 'https://example.invalid/other.git'); self.commit()
        time.sleep(.1)
        self.assertFalse((self.root / 'submits').exists())

    def test_wrong_origin_install_refused(self):
        self.git('remote', 'set-url', 'origin', 'https://example.invalid/other.git')
        with self.assertRaises(ValueError): self.install()
        self.assertFalse(self.hook.exists())

    def test_v1_migration_keeps_original_and_removes_duplicate_submit(self):
        original = '#!/bin/sh\ntouch prior-v1\n\n# hp-os-fleet-submit-v1\ntouch duplicate-submit\n'
        self.hook.write_text(original); self.hook.chmod(0o755)
        self.install(); self.install(); self.commit(); self.wait_submit()
        self.assertTrue((self.repo / 'prior-v1').exists())
        self.assertFalse((self.repo / 'duplicate-submit').exists())
        self.assertEqual(self.hook.with_name('post-commit.hp-os-fleet-original').read_text(), original)

    def test_rapid_commits_submit_latest_after_current_validation(self):
        self.commit(); first = self.git('rev-parse', 'HEAD')
        entered = threading.Event(); release = threading.Event(); attempted = []
        def submit(root):
            revision = self.git('rev-parse', 'HEAD'); attempted.append(revision)
            if revision == first:
                entered.set(); self.assertTrue(release.wait(5))
                raise ValueError('Source changed during validation')
            return revision
        with patch.object(publish, 'submit', side_effect=submit):
            worker = threading.Thread(target=publish.drain, args=(self.repo,)); worker.start()
            self.assertTrue(entered.wait(5)); self.commit(); latest = self.git('rev-parse', 'HEAD')
            queued = threading.Thread(target=publish.drain, args=(self.repo,)); queued.start()
            release.set(); worker.join(5); queued.join(5)
            self.assertFalse(worker.is_alive()); self.assertFalse(queued.is_alive())
        self.assertEqual(attempted, [first, latest])

    def test_queued_workers_do_not_repeat_unchanged_failed_build(self):
        self.commit()
        with patch.object(publish, 'submit', side_effect=ValueError('Build failed')) as submit:
            self.assertFalse(publish.drain(self.repo)); self.assertFalse(publish.drain(self.repo))
            self.assertEqual(submit.call_count, 1)
            self.commit(); publish.drain(self.repo)
            self.assertEqual(submit.call_count, 2)
        result = json.loads(next((self.root / 'state/hp-os-fleet').glob('*/last-attempt.json')).read_text())
        self.assertEqual(result['state'], 'failed')


if __name__ == '__main__': unittest.main()
