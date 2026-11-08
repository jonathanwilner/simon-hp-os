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
