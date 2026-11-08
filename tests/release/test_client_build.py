import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'fleet/release'))
import client_build

DRV = '/nix/store/' + 'a' * 32 + '-activation.drv'
GPU = '/nix/store/' + 'b' * 32 + '-cuda.drv'


def graph(gpu=False):
    values = {DRV: {'env': {'name': 'activation'}, 'inputDrvs': {}}}
    if gpu:
        values[DRV]['inputDrvs'][GPU] = ['out']
        values[GPU] = {'env': {'name': 'cuda-12'}, 'inputDrvs': {}}
    return values


class ClientBuild(unittest.TestCase):
    def test_nvidia_rejected_before_build_on_other_clients(self):
        with patch.object(client_build.socket, 'gethostname', return_value='simon'), \
             patch.object(client_build.subprocess, 'check_output', side_effect=[DRV, json.dumps(graph(True))]), \
             patch.object(client_build.subprocess, 'run') as build:
            with self.assertRaisesRegex(ValueError, 'Goran-only'):
                client_build.build('.#homeConfigurations.simon.activationPackage', '/tmp/result')
            build.assert_not_called()

    def test_nvidia_allowed_only_on_goran_and_cannot_delegate(self):
        with patch.object(client_build.socket, 'gethostname', return_value='goran.local'), \
             patch.object(client_build.subprocess, 'check_output', side_effect=[DRV, json.dumps(graph(True))]) as read, \
             patch.object(client_build.subprocess, 'run') as build:
            client_build.build('.#homeConfigurations.simon.activationPackage', '/tmp/result')
            command = build.call_args.args[0]
            self.assertIn(DRV + '^*', command)
            self.assertIn(['--option', 'builders', ''], [command[i:i+3] for i in range(len(command))])
            for invocation in read.call_args_list + build.call_args_list:
                args = invocation.args[0]
                self.assertIn(['--option', 'allow-import-from-derivation', 'false'],
                              [args[i:i+3] for i in range(len(args))])
            self.assertNotIn('.#homeConfigurations.simon.activationPackage', command)

    def test_generic_client_needs_no_private_builder(self):
        self.assertFalse(client_build.authorize(graph(), DRV, 'some-other-client'))

    def test_missing_transitive_graph_rejected(self):
        incomplete = graph(True)
        del incomplete[GPU]
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            client_build.authorize(incomplete, DRV, 'goran')

    def test_invalid_eval_result_cannot_be_built(self):
        with patch.object(client_build.subprocess, 'check_output', return_value='bogus'), \
             patch.object(client_build.subprocess, 'run') as build:
            with self.assertRaisesRegex(ValueError, 'valid derivation'):
                client_build.build('.#homeConfigurations.simon.activationPackage', '/tmp/result')
            build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
