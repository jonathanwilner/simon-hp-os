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


def version4(gpu=False):
    return {'version': 4, 'derivations': {
        Path(path).name: {'version': 4, 'name': item['env']['name'], 'env': {},
            'structuredAttrs': {'cudaSupport': True} if path == GPU else None,
            'inputs': {'drvs': {Path(child).name: {'outputs': outputs, 'dynamicOutputs': {}}
                               for child, outputs in item['inputDrvs'].items()}}}
        for path, item in graph(gpu).items()}}


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

    def test_v4_generic_build_and_nvidia_rejection(self):
        for gpu in [False, True]:
            with patch.object(client_build.socket, 'gethostname', return_value='slazenger'), \
                 patch.object(client_build.subprocess, 'check_output', side_effect=[DRV, json.dumps(version4(gpu))]), \
                 patch.object(client_build.subprocess, 'run') as build:
                if gpu:
                    with self.assertRaisesRegex(ValueError, 'Goran-only'):
                        client_build.build('.#activation', '/tmp/result')
                    build.assert_not_called()
                else:
                    client_build.build('.#activation', '/tmp/result')
                    build.assert_called_once()

    def test_router_build_normalizes_v4_before_routing(self):
        router = client_build.build_router
        with patch.object(router.subprocess, 'check_output', return_value=json.dumps(version4())), \
             patch.object(router.subprocess, 'run') as build, \
             patch.dict(router.os.environ, {'FLEET_ARM_STORE': 'ssh-ng://builder@dropshot-arm-linux'}):
            self.assertEqual(router.build([DRV], 'aarch64-linux'), ['dropshot'])
            build.assert_called_once()

    def test_v4_unknown_and_dynamic_graphs_fail_closed(self):
        values = []
        unknown = version4(); unknown['version'] = 5; values.append(unknown)
        dynamic = version4(True)
        dynamic['derivations'][Path(DRV).name]['inputs']['drvs'][Path(GPU).name]['dynamicOutputs'] = {'out': {}}
        values.append(dynamic)
        for value in values:
            with self.assertRaises(ValueError):
                client_build.build_router.normalize_graph(value)

    def test_invalid_eval_result_cannot_be_built(self):
        with patch.object(client_build.subprocess, 'check_output', return_value='bogus'), \
             patch.object(client_build.subprocess, 'run') as build:
            with self.assertRaisesRegex(ValueError, 'valid derivation'):
                client_build.build('.#homeConfigurations.simon.activationPackage', '/tmp/result')
            build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
