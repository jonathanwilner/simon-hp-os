import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[2] / 'fleet/release/build_router.py'
spec = importlib.util.spec_from_file_location('build_router', MODULE)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


def drv(name, dependencies=(), **env):
    return {'env': {'name': name, **env}, 'inputDrvs': {p: ['out'] for p in dependencies}}


class Routing(unittest.TestCase):
    env = {'FLEET_ARM_STORE': 'ssh-ng://builder@dropshot-arm-linux',
           'FLEET_NVIDIA_STORE': 'ssh-ng://jonathan@goran'}

    def test_transitive_nvidia_roots_go_only_to_goran(self):
        graph = {'app': drv('desktop-app', ['middle']), 'middle': drv('bridge', ['gpu']),
                 'gpu': drv('cuda-12.6'), 'plain': drv('ghostty-1.4')}
        routes = router.plan(graph, ['app', 'plain'], 'aarch64-linux', self.env)
        self.assertEqual([host for host, _ in routes], ['dropshot', 'goran'])
        for host, command in routes:
            self.assertEqual(command[command.index('--option')+1:command.index('--option')+3], ['builders', ''])
            self.assertIn('--eval-store', command)
            self.assertIn('app^*' if host == 'goran' else 'plain^*', command)
            self.assertNotIn('app^*' if host == 'dropshot' else 'plain^*', command)

    def test_x86_nvidia_is_rejected_even_on_armstrong(self):
        with self.assertRaisesRegex(ValueError, 'only ARM Goran'):
            router.plan({'gpu': drv('nvidia-x11-590')}, ['gpu'], 'x86_64-linux', self.env,
                        hostname='armstrong', machine='x86_64')

    def test_x86_generic_requires_armstrong_without_remote_builders(self):
        graph = {'app': drv('hello')}
        self.assertEqual(router.plan(graph, ['app'], 'x86_64-linux', {},
                         hostname='armstrong', machine='x86_64')[0][0], 'armstrong')
        for host, machine in [('goran', 'aarch64'), ('github-runner', 'x86_64')]:
            with self.assertRaisesRegex(ValueError, 'Armstrong'):
                router.plan(graph, ['app'], 'x86_64-linux', {}, hostname=host, machine=machine)

    def test_missing_or_wrong_endpoints_fail_before_builds(self):
        graph = {'app': drv('hello'), 'gpu': drv('cudnn-9')}
        for env in ({}, {'FLEET_ARM_STORE': self.env['FLEET_ARM_STORE']},
                    dict(self.env, FLEET_NVIDIA_STORE='ssh-ng://builder@dropshot-arm-linux'),
                    dict(self.env, FLEET_ARM_STORE='ssh-ng://github-runner')):
            with self.assertRaises(ValueError):
                router.plan(graph, ['app', 'gpu'], 'aarch64-linux', env)

    def test_incomplete_graph_rejected_even_after_gpu_dependency(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            router.classify({'app': drv('app', ['gpu', 'missing']), 'gpu': drv('cuda')}, ['app'])

    def test_missing_graph_fields_rejected(self):
        for item in [{}, {'inputDrvs': {}}, {'env': {}}]:
            with self.assertRaisesRegex(ValueError, 'Invalid'):
                router.classify({'app': item}, ['app'])

    def test_structured_flags_and_features(self):
        self.assertTrue(router.is_nvidia(drv('app', __json='{"cudaSupport": true}')))
        self.assertTrue(router.is_nvidia(drv('app', __json='{"requiredSystemFeatures": ["nvidia-gpu"]}')))
        with self.assertRaisesRegex(ValueError, 'Invalid structured'):
            router.is_nvidia(drv('app', __json='invalid'))

    def test_cycles_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            router.classify({'app': drv('app', ['app'])}, ['app'])

    def test_enabled_flags_features_and_vendor_names(self):
        for value in [drv('python-torch', cudaSupport='1'), drv('test', requiredSystemFeatures='nvidia-gpu'),
                      drv('libcublas-12'), drv('nccl-2'), drv('tensorrt-10')]:
            with self.subTest(value=value):
                self.assertTrue(router.is_nvidia(value))
        self.assertFalse(router.is_nvidia(drv('mesa', cudaSupport='false', buildCommand='optional NVIDIA detection')))

    def test_store_url_cannot_override_endpoint(self):
        for store in ['ssh-ng://goran?remote-store=ssh-ng://elsewhere', 'ssh-ng://goran:22',
                      'ssh://goran', 'ssh-ng://user:password@goran', 'ssh-ng://goran/path']:
            with self.assertRaises(ValueError):
                router.endpoint(store, 'nvidia')


if __name__ == '__main__':
    unittest.main()
