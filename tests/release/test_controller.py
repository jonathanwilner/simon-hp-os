import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'fleet/release'
sys.path.insert(0, str(SOURCE))
import controller

REV = 'a' * 40

def config():
    return {'checkout': '/tmp/trusted-fleet', 'validation': {
        lane: {'host': host, 'command': ['validate', '{revision}', lane], 'evidence_url': 'https://example.test/{session}.txt'}
        for lane, host in [('aarch64-linux', 'dropshot'), ('x86_64-linux', 'armstrong'), ('nvidia', 'goran')]},
        'canaries': {'aarch64-linux': {'host': 'goran'}, 'x86_64-linux': {'host': 'slazenger'}}}

def evidence(lane):
    if lane == 'nvidia':
        return dict(source_clean=True, revision=REV, system='aarch64-linux', host='goran', capability='nvidia', passed=True)
    return dict(source_clean=True, revision=REV, system=lane, host=config()['validation'][lane]['host'], evaluation='passed', launcher='passed', build='passed')

class Controller(unittest.TestCase):
    def test_missing_validation_never_deploys(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(controller.consumers, 'reconcile') as reconcile:
            with self.assertRaises(ValueError): controller.cycle({}, Path(directory), REV)
            reconcile.assert_not_called()

    def test_wrong_arm_host_rejected(self):
        conf=config(); conf['validation']['aarch64-linux']['host']='goran'
        with self.assertRaisesRegex(ValueError, 'Dropshot'): controller.validate_config(conf)

    def test_nvidia_cannot_run_on_dropshot(self):
        conf=config(); conf['validation']['nvidia']['host']='dropshot'
        with self.assertRaisesRegex(ValueError, 'Goran'): controller.validate_config(conf)

    def test_no_generic_arm_hardware_canary(self):
        conf=config(); conf['canaries']['aarch64-linux']['host']='dropshot'
        with self.assertRaisesRegex(ValueError, 'Goran'): controller.validate_config(conf)

    def test_failed_validation_stops_before_canary(self):
        result=evidence('aarch64-linux'); result['build']='failed'
        with tempfile.TemporaryDirectory() as directory, patch.object(controller, 'run', return_value=json.dumps(result)), patch.object(controller.consumers, 'reconcile') as reconcile:
            with self.assertRaisesRegex(ValueError, 'gates'): controller.cycle(config(), Path(directory), REV)
            reconcile.assert_not_called()
            self.assertTrue((Path(directory)/REV/'validation-aarch64-linux.failed').exists())

    def test_wrong_evidence_revision(self):
        result=evidence('aarch64-linux'); result['revision']='b'*40
        with self.assertRaisesRegex(ValueError, 'revision'): controller.accept_validation(result,REV,'aarch64-linux','dropshot')

    def test_dirty_or_unasserted_source_fails(self):
        result=evidence('aarch64-linux'); result.pop('source_clean')
        with self.assertRaisesRegex(ValueError, 'clean'): controller.accept_validation(result,REV,'aarch64-linux','dropshot')

    def test_nvidia_evidence_requires_host_capability(self):
        result=evidence('nvidia'); result['host']='dropshot'
        with self.assertRaises(ValueError): controller.accept_validation(result,REV,'nvidia','goran')
        result=evidence('nvidia'); result.pop('capability')
        with self.assertRaises(ValueError): controller.accept_validation(result,REV,'nvidia','goran')

    def test_old_windows_cannot_pass(self):
        with self.assertRaises(ValueError): controller.accept({'revision': REV, 'system': 'aarch64-linux', 'passed': True}, REV, 'aarch64-linux')

    def test_wrong_revision_cannot_pass(self):
        with self.assertRaises(ValueError): controller.accept({'revision': 'b'*40, 'system': 'aarch64-linux', 'passed': True, 'fresh_launch': True}, REV, 'aarch64-linux')

if __name__ == '__main__': unittest.main()
