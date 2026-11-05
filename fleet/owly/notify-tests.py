#!/usr/bin/env python3
"""Focused adapter checks. No desktop notifications or processes are launched."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('notify_adapter', Path(__file__).with_name('notify.py'))
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        state = Path(self.temp.name) / 'hp-os-omdrop'
        state.mkdir()
        (state / 'controller.json').write_text(json.dumps({
            'notification_bus': 'unix:path=/tmp/private-session',
            'notification_display': ':4', 'notification_wayland_display': 'wayland-9'}))
        env = patch.dict(os.environ, {'XDG_RUNTIME_DIR': self.temp.name})
        env.start()
        self.addCleanup(env.stop)

    @patch.object(notify.subprocess, 'run')
    def test_literal_arguments_and_private_bus(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout='', stderr='')
        title, body = '--help', '$(touch /tmp/never); `false`'
        self.assertEqual(notify.main([title, body, '--image', '/tmp/a b.png']), 0)
        args, kw = run.call_args
        self.assertEqual(args[0][-3:], ['--', title, body])
        self.assertIn('/tmp/a b.png', args[0])
        self.assertFalse(kw.get('shell', False))
        self.assertEqual(kw['env']['DBUS_SESSION_BUS_ADDRESS'], 'unix:path=/tmp/private-session')
        self.assertEqual(kw['env']['WAYLAND_DISPLAY'], 'wayland-9')
        self.assertEqual(kw['env']['DISPLAY'], ':4')

    @patch.object(notify.subprocess, 'Popen')
    @patch.object(notify.subprocess, 'run')
    def test_action_requires_explicit_default_response(self, run, spawn):
        command = ['xdg-open', '/tmp/a b;$(false).pdf']
        for answer, launches in [('', 0), ('dismissed', 0), ('default\n', 1)]:
            spawn.reset_mock()
            run.return_value = SimpleNamespace(returncode=0, stdout=answer, stderr='')
            self.assertEqual(notify.main(['--worker', 'Title', 'Body', '--exec', *command]), 0)
            self.assertEqual(spawn.call_count, launches)
            if launches:
                self.assertEqual(spawn.call_args.args[0], command)
                self.assertFalse(spawn.call_args.kwargs.get('shell', False))
                self.assertEqual(spawn.call_args.kwargs['env']['DBUS_SESSION_BUS_ADDRESS'], 'unix:path=/tmp/private-session')

    @patch.object(notify.subprocess, 'Popen')
    @patch.object(notify.subprocess, 'run')
    def test_action_notification_detaches_worker(self, run, spawn):
        self.assertEqual(notify.main(['-t', '6000', 'Title', 'Body', '--exec', 'xdg-open', '/tmp/file']), 0)
        run.assert_not_called()
        self.assertIn('--worker', spawn.call_args.args[0])
        self.assertTrue(spawn.call_args.kwargs['start_new_session'])

    def test_incomplete_timeout_is_validation_error(self):
        with self.assertRaises(ValueError):
            notify.main(['-t'])

    def test_packaging_substitutes_executable_and_installs_runtime_path(self):
        source = Path(__file__).with_name('omdrop-package.nix').read_text()
        self.assertIn("--replace-fail '@notifySend@' '${libnotify}/bin/notify-send'", source)
        self.assertIn('notificationAdapter coreutils', source)
        self.assertIn('chmod 755 $out/bin/omarchy-notification-send', source)


if __name__ == '__main__':
    unittest.main()
