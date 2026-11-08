import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('fleet_rulesets', ROOT / 'scripts/fleet-rulesets.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Rulesets(unittest.TestCase):
    def test_active_rules_are_idempotent(self):
        desired = [json.loads(p.read_text()) for p in sorted((ROOT / '.github/rulesets').glob('fleet-*.json'))]
        live = [dict(item, id=i + 1) for i, item in enumerate(desired)]
        def api(path, method='GET', body=None):
            self.assertEqual(method, 'GET', 'unchanged apply must not write')
            if path.endswith('/actions/permissions'): return {'enabled': False}
            return live if '?' in path else live[int(path.rsplit('/', 1)[1]) - 1]
        with patch.object(m, 'api', side_effect=api), patch('sys.argv', ['rulesets', '--apply']):
            self.assertEqual(m.main(), 0)

    def test_actions_drift_check_never_writes(self):
        with patch.object(m, 'api', return_value={'enabled': True}) as api:
            self.assertTrue(m.reconcile_actions('example/fleet'))
            api.assert_called_once_with('repos/example/fleet/actions/permissions')

    def test_actions_apply_disables_and_reads_back(self):
        with patch.object(m, 'api', side_effect=[{'enabled': True}, {}, {'enabled': False}]) as api:
            self.assertFalse(m.reconcile_actions('example/fleet', apply=True))
            self.assertEqual(api.call_args_list[1].args, ('repos/example/fleet/actions/permissions', 'PUT', {'enabled': False}))
            self.assertEqual(api.call_args_list[2].args, ('repos/example/fleet/actions/permissions',))

    def test_actions_failed_readback_fails_closed(self):
        with patch.object(m, 'api', side_effect=[{'enabled': True}, {}, {'enabled': True}]):
            with self.assertRaisesRegex(RuntimeError, 'remain disabled'):
                m.reconcile_actions('example/fleet', apply=True)

    def test_actions_204_response_is_supported(self):
        with patch.object(m.subprocess, 'check_output', return_value=b''):
            self.assertEqual(m.api('repos/example/fleet/actions/permissions', 'PUT', {'enabled': False}), {})

    def test_gate_contract(self):
        branch = json.loads((ROOT / '.github/rulesets/fleet-stable-gates.json').read_text())
        self.assertEqual(branch['bypass_actors'], [])
        checks = next(r['parameters'] for r in branch['rules'] if r['type'] == 'required_status_checks')
        self.assertFalse(checks['do_not_enforce_on_create'])
        self.assertEqual(len(checks['required_status_checks']), 5)
        self.assertEqual({c['context'] for c in checks['required_status_checks'] if c['context'].startswith('fleet/validation/')}, {'fleet/validation/aarch64-linux', 'fleet/validation/x86_64-linux', 'fleet/validation/nvidia'})
        self.assertTrue(all('integration_id' not in c for c in checks['required_status_checks']))
        changed = dict(branch, enforcement='disabled')
        self.assertFalse(m.matches(changed, branch))
        self.assertTrue(m.matches(dict(branch, id=99), branch))


if __name__ == '__main__':
    unittest.main()
