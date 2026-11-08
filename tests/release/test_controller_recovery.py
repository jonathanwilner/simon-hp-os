import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'fleet/release'))
import controller

REV = 'a' * 40


class Recovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name)
        self.marker = self.state / 'promotion-requested'
        self.workflow = {'id': 123, 'head_sha': REV, 'display_title': f'Promote fleet {REV}', 'event': 'workflow_dispatch',
                         'status': 'completed', 'conclusion': 'failure', 'run_attempt': 1,
                         'created_at': '1970-01-01T00:01:40Z', 'html_url': 'https://example.test/actions/123'}

    def requested(self, **extra):
        self.marker.write_text(json.dumps(dict(revision=REV, requested_at=100, attempts=1, **extra)))

    def test_new_dispatch_happens_once_while_waiting(self):
        with patch.object(controller, 'run') as run, patch.object(controller, 'api', return_value={'workflow_runs': []}):
            self.assertEqual(controller.promotion(self.state, REV, now=100)['state'], 'waiting-for-promotion')
            self.assertEqual(controller.promotion(self.state, REV, now=101)['state'], 'waiting-for-promotion')
            self.assertEqual(run.call_count, 1)

    def test_uncertain_dispatch_does_not_create_duplicate(self):
        with patch.object(controller, 'run', side_effect=OSError('Connection lost')):
            with self.assertRaises(OSError): controller.promotion(self.state, REV, now=100)
        with patch.object(controller, 'run') as run, patch.object(controller, 'api', return_value={'workflow_runs': []}):
            controller.promotion(self.state, REV, now=110)
            run.assert_not_called()

    def test_successful_workflow_with_missing_ref_has_bounded_wait(self):
        self.requested(run_id=123, success_seen_at=200)
        self.workflow['conclusion'] = 'success'
        with patch.object(controller, 'api', return_value=self.workflow):
            self.assertEqual(controller.promotion(self.state, REV, now=1000)['state'], 'promotion-ref-missing')

    def test_failed_workflow_retries_same_run_and_deduplicates_eventual_consistency(self):
        self.requested()
        with patch.object(controller, 'api', side_effect=[{'workflow_runs': [self.workflow]}, self.workflow]), patch.object(controller, 'run') as run:
            result = controller.promotion(self.state, REV, now=200)
            self.assertEqual(result['state'], 'promotion-retrying')
            self.assertEqual(run.call_args.args[0], ['gh', 'run', 'rerun', '123', '--repo', controller.REPO])
            result = controller.promotion(self.state, REV, now=201)
            self.assertEqual(result['state'], 'waiting-for-promotion')
            self.assertEqual(run.call_count, 1)

    def test_retry_exhaustion_reports_failure(self):
        self.marker.write_text(json.dumps(dict(revision=REV, requested_at=100, attempts=3, run_id=123, requested_attempt=3)))
        self.workflow['run_attempt'] = 3
        with patch.object(controller, 'api', return_value=self.workflow), patch.object(controller, 'run') as run:
            self.assertEqual(controller.promotion(self.state, REV, now=1000)['state'], 'promotion-failed')
            run.assert_not_called()

    def test_old_timestamp_marker_migrates_without_duplicate_dispatch(self):
        self.marker.write_text('100\n')
        self.workflow.update(status='in_progress', conclusion=None)
        with patch.object(controller, 'api', return_value={'workflow_runs': [self.workflow]}), patch.object(controller, 'run') as run:
            controller.promotion(self.state, REV, now=110)
            run.assert_not_called()
        self.assertEqual(json.loads(self.marker.read_text())['run_id'], 123)

    def test_wrong_revision_run_never_retried(self):
        self.requested(run_id=123)
        self.workflow['head_sha'] = 'b' * 40
        with patch.object(controller, 'api', return_value=self.workflow), patch.object(controller, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'exact requested revision'):
                controller.promotion(self.state, REV, now=200)
            run.assert_not_called()

    def test_missing_dispatch_reports_explicit_unobserved_without_duplicate(self):
        self.requested()
        with patch.object(controller, 'api', return_value={'workflow_runs': []}), patch.object(controller, 'run') as run:
            self.assertEqual(controller.promotion(self.state, REV, now=1000)['state'], 'promotion-unobserved')
            run.assert_not_called()

    def test_pending_retry_not_observed_is_reported(self):
        self.requested(run_id=123, requested_attempt=2, retry_at=200)
        with patch.object(controller, 'api', return_value=self.workflow), patch.object(controller, 'run') as run:
            self.assertEqual(controller.promotion(self.state, REV, now=1000)['state'], 'promotion-unobserved')
            run.assert_not_called()

    def test_evidence_is_content_addressed_and_verified_before_return(self):
        evidence = {'revision': REV, 'system': 'x86_64-linux', 'passed': True, 'fresh_launch': True}
        payload = (json.dumps(evidence, indent=2, sort_keys=True) + '\n').encode()
        host = {'evidence_url': 'https://example.test/logs/{session}.txt'}
        with patch.dict(os.environ, {'NOM_DASHBOARD_STATE_DIR': str(self.state)}), \
             patch.object(controller, 'run') as run, patch.object(controller.urllib.request, 'urlopen', side_effect=lambda *a, **kw: io.BytesIO(payload)):
            first = controller.publish_evidence(host, evidence, REV, 'x86_64-linux')
            second = controller.publish_evidence(host, evidence, REV, 'x86_64-linux')
        self.assertEqual(first, second); self.assertIn(REV, first)
        self.assertEqual(len(list(self.state.glob('*.log'))), 1)
        self.assertEqual(next(self.state.glob('*.log')).read_bytes(), payload)
        self.assertTrue(any(call.args[0][0] == 'nom-dashboard-sync' for call in run.call_args_list))

    def test_mutable_evidence_url_refused(self):
        with self.assertRaisesRegex(ValueError, 'immutable'):
            controller.publish_evidence({'evidence_url': 'https://example.test/controller.log'}, {}, REV, 'x86_64-linux')

    def test_wrong_downloaded_bytes_never_publish_status(self):
        host = {'evidence_url': 'https://example.test/{session}.txt'}
        with patch.dict(os.environ, {'NOM_DASHBOARD_STATE_DIR': str(self.state)}), patch.object(controller, 'run'), \
             patch.object(controller.time, 'sleep'), patch.object(controller.urllib.request, 'urlopen', side_effect=lambda *a, **kw: io.BytesIO(b'wrong')):
            with self.assertRaisesRegex(ValueError, 'could not be verified'):
                controller.publish_evidence(host, {}, REV, 'x86_64-linux')


if __name__ == '__main__': unittest.main()
