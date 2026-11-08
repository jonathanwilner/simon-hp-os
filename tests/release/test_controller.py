import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'fleet/release'
sys.path.insert(0, str(SOURCE))
import controller

class Controller(unittest.TestCase):
    def test_pending_ci_never_deploys(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(controller, 'tested_head', return_value=('a' * 40, None)), patch.object(controller.consumers, 'reconcile') as reconcile:
            result = controller.cycle({}, Path(directory))
            self.assertEqual(result['state'], 'waiting-for-ci')
            reconcile.assert_not_called()

    def test_old_windows_cannot_pass(self):
        with self.assertRaises(ValueError):
            controller.accept({'revision': 'a' * 40, 'system': 'aarch64-linux', 'passed': True}, 'a' * 40, 'aarch64-linux')

    def test_wrong_revision_cannot_pass(self):
        with self.assertRaises(ValueError):
            controller.accept({'revision': 'b' * 40, 'system': 'aarch64-linux', 'passed': True, 'fresh_launch': True}, 'a' * 40, 'aarch64-linux')

    def test_missing_canary_blocks_deployment(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(controller, 'tested_head', return_value=('a' * 40, {'conclusion':'success'})), patch.object(controller.consumers, 'reconcile') as reconcile:
            with self.assertRaises(ValueError): controller.cycle({'canaries': {}}, Path(directory))
            reconcile.assert_not_called()

if __name__ == '__main__': unittest.main()
