import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'fleet/release' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class Publishing(unittest.TestCase):
    def test_dirty_source_never_pushes(self):
        p = module('publish')
        with patch.object(p, 'git', return_value=' M file') as git, patch.object(p, 'validate') as validate:
            with self.assertRaises(ValueError): p.submit(ROOT)
            validate.assert_not_called()
            self.assertEqual(git.call_count, 1)

    def test_validation_failure_prevents_push(self):
        p = module('publish')
        calls = []
        def git(root, *args):
            calls.append(args)
            if args[:2] == ('remote', 'get-url'): return 'git@github.com:jonathanwilner/simon-hp-os.git'
            if args[:2] == ('rev-parse', 'HEAD'): return 'a' * 40
            return ''
        with patch.object(p, 'git', side_effect=git), patch.object(p, 'validate', side_effect=ValueError('failed')):
            with self.assertRaises(ValueError): p.submit(ROOT)
        self.assertFalse(any(c[0] == 'push' for c in calls))

    def test_changed_source_after_validation_prevents_push(self):
        p = module('publish')
        statuses = iter(['', ' M new-change'])
        calls = []
        def git(root, *args):
            calls.append(args)
            if args[0] == 'status': return next(statuses)
            if args[0] == 'remote': return 'git@github.com:jonathanwilner/simon-hp-os.git'
            if args[0] == 'rev-parse': return 'a' * 40
            return ''
        with patch.object(p, 'git', side_effect=git), patch.object(p, 'validate'):
            with self.assertRaises(ValueError): p.submit(ROOT)
        self.assertFalse(any(c[0] == 'push' for c in calls))

    def test_submission_evaluates_without_building_on_submitter(self):
        p = module('publish')
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            def run(*args, **kwargs):
                (state / 'fleet-submit.status').write_text('0')
            with patch.dict(p.os.environ, {'NOM_DASHBOARD_STATE_DIR': tmp}), \
                    patch.object(p.platform, 'machine', return_value='x86_64'), \
                    patch.object(p.subprocess, 'run') as process, \
                    patch.object(p, 'run', side_effect=run) as runner:
                process.return_value.returncode = 1
                p.validate(ROOT)
                runner.assert_called_once_with(
                    'nom-tmux', 'fleet-submit', '--', 'bash',
                    'tests/release/validate.sh', 'x86_64-linux', '--evaluate-only',
                    cwd=ROOT, capture=False)

    def test_promotion_requires_full_revision(self):
        p = module('publish')
        with patch.object(p, 'run') as run:
            with self.assertRaises(ValueError): p.promote('main')
            run.assert_not_called()

    def test_missing_writer_config_never_dispatches(self):
        p = module('publish')
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, 'run') as run:
            with self.assertRaises(ValueError):
                p.promote('a' * 40, Path(tmp) / 'missing.json')
            run.assert_not_called()

    def test_promotion_uses_tracked_local_controller_and_exact_sha(self):
        p = module('publish')
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, 'run') as run:
            config = Path(tmp) / 'controller.json'
            config.write_text('{}')
            state = Path(tmp) / 'evidence'
            p.promote('a' * 40, config, state)
            run.assert_called_once_with(
                'nom-tmux', 'fleet-promote-' + 'a' * 12, '--', 'fleet-controller',
                '--config', str(config.resolve()), '--state', str(state.resolve()),
                '--revision', 'a' * 40, '--promote-only', capture=False)

    def test_dirty_consumer_is_preserved(self):
        c = module('consumers')
        with patch.object(c, 'run', return_value=' M local') as run:
            with self.assertRaises(ValueError): c.reconcile({'checkout': str(ROOT), 'branch': 'main'}, 'a' * 40)
            self.assertEqual(run.call_count, 1)

if __name__ == '__main__': unittest.main()
