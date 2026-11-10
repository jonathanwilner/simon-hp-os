#!/usr/bin/env python3
"""Regression coverage for cross-generation and cross-session shell control."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('runtime_control', Path(__file__).resolve().parents[1] / 'packaging/runtime-control.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class RuntimeControlTests(unittest.TestCase):
    def test_discovery_requires_same_uid_and_hp_os_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pid, executable, config in [('10', 'quickshell', '/home/test/.config/hp-os'), ('11', 'quickshell', '/home/test/.config/dms'), ('12', 'niri', '/home/test/.config/hp-os')]:
                process = root / pid
                process.mkdir()
                (process / 'cmdline').write_bytes(f'{executable}\0-n\0-p\0/old/inir\0'.encode())
                (process / 'environ').write_bytes(f'INIR_RUNTIME_DIR=/old/inir\0INIR_CONFIG_DIR={config}\0WAYLAND_DISPLAY=wayland-1\0'.encode())
                (process / 'stat').write_text(f'{pid} ({executable}) S ' + ' '.join(['0'] * 18 + ['123']))
            self.assertEqual([p['pid'] for p in control.discover(root)], [10])
            self.assertEqual(control.discover(root, uid=os.getuid() + 1), [])

    def test_stale_generation_uses_live_pid_and_private_environment(self):
        live = dict(pid=45, runtime='/old/inir', env=dict(WAYLAND_DISPLAY='wayland-1', DBUS_SESSION_BUS_ADDRESS='private', INIR_CONFIG_DIR='/home/test/.config/hp-os'))
        with patch.object(control, 'discover', return_value=[live]), patch.object(control.os, 'execvpe') as execute, patch.object(control.sys, 'argv', ['runtime-control.py', 'ipc', '/new/inir', '/new/bin/hp-os', 'hpos', 'status']), patch.dict(os.environ, live['env'], clear=True):
            control.main()
        self.assertEqual(execute.call_args.args, ('qs', ['qs', 'ipc', '--pid', '45', 'call', 'hpos', 'status'], live['env']))

    def test_sibling_desktop_and_ambiguous_sessions_are_not_selected(self):
        first = dict(env=dict(WAYLAND_DISPLAY='wayland-1', DBUS_SESSION_BUS_ADDRESS='bus-a'))
        second = dict(env=dict(WAYLAND_DISPLAY='wayland-2', DBUS_SESSION_BUS_ADDRESS='bus-b'))
        self.assertIs(control.select([first, second], first['env']), first)
        self.assertIsNone(control.select([first], dict(WAYLAND_DISPLAY='wayland-2')))
        with self.assertRaises(RuntimeError):
            control.select([first, second], {})

    def test_ssh_shared_bus_selects_unique_private_shell(self):
        shell = dict(env=dict(WAYLAND_DISPLAY='wayland-1', DBUS_SESSION_BUS_ADDRESS='private'))
        ssh = dict(DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{os.getuid()}/bus')
        self.assertIs(control.select([shell], ssh), shell)
        with self.assertRaises(RuntimeError):
            control.select([shell, shell], ssh)

    def test_activation_launches_persistent_unit_and_shell_survives_unit_exit(self):
        root = Path(__file__).resolve().parents[3]
        for path, unit in [(root / 'fleet/home.nix', 'hp-os-runtime-refresh.service'), (root / 'vendor/HP-OSShell/packaging/home-module.nix', 'hp-os-package-runtime-refresh.service')]:
            source = path.read_text()
            self.assertIn('entryAfter [ "reloadSystemd" ]', source)
            self.assertIn('start --no-block ' + unit, source)
            self.assertIn('KillMode = "process"', source)

    def test_launch_preserves_compositor_and_private_bus_but_cleans_qt_generation(self):
        old = dict(HP_OS_RUNTIME='/old', INIR_RUNTIME_DIR='/old', QML_IMPORT_PATH='/old/qml', QT_PLUGIN_PATH='/old/plugins', HP_OS_PACKAGING='/old/packaging', WAYLAND_DISPLAY='wayland-1', DBUS_SESSION_BUS_ADDRESS='private', NIRI_SOCKET='/run/niri.sock')
        new = control.launch_env(dict(env=old), '/new')
        self.assertEqual(new['INIR_RUNTIME_DIR'], '/new')
        self.assertEqual(new['HP_OS_RUNTIME'], '/new')
        self.assertNotIn('QML_IMPORT_PATH', new)
        self.assertNotIn('HP_OS_PACKAGING', new)
        for key in ('WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'NIRI_SOCKET'):
            self.assertEqual(new[key], old[key])

    def test_locked_and_unknown_sessions_defer_without_stopping(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'shell.qml').touch()
            instance = dict(pid=44, runtime='/old', env={'HP_OS_OWNED_SESSION': '1'})
            for status, code in [('secure', 0), ('locked', 0), ('activating', 0), ('', 1)]:
                with patch.object(control.subprocess, 'run', return_value=SimpleNamespace(stdout=status, returncode=code)) as run:
                    control.refresh(instance, directory, '/runner')
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][-2:], ['lock', 'status'])

    def test_current_generation_and_unowned_session_are_untouched(self):
        with patch.object(control.subprocess, 'run') as run:
            control.refresh(dict(runtime='/new', env={'HP_OS_OWNED_SESSION': '1'}), '/new', '/runner')
            control.refresh(dict(runtime='/old', env={}), '/new', '/runner')
        run.assert_not_called()

    def test_installed_wrapper_ignores_stale_inherited_runtime(self):
        source = Path(__file__).resolve().parents[1] / 'packaging/hp-os'
        with tempfile.TemporaryDirectory() as directory:
            runner = Path(directory) / 'hp-os'
            runner.write_text(source.read_text().replace('@runtime@', '/installed/inir'))
            # Inspect the selected runtime through a fake controller before any
            # runtime exists. This exercises the installed Bash entry point.
            packaging = Path(directory) / 'packaging'
            packaging.mkdir()
            for name in ('session-environment.sh', 'migrate-brand.py'):
                (packaging / name).write_text('hpos_clean_data_dirs() { :; }' if name.endswith('.sh') else '')
            (packaging / 'runtime-control.py').write_text('import sys; print(sys.argv[2])')
            import subprocess
            result = subprocess.run(['bash', str(runner), 'settings'], env=dict(os.environ, HP_OS_RUNTIME='/stale/inir', HP_OS_PACKAGING=str(packaging)), capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), '/installed/inir')


if __name__ == '__main__':
    unittest.main()
