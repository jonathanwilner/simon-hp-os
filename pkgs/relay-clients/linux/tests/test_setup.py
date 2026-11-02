import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import relay_setup as setup
from relay_agent import Agent

class EnrollmentTests(unittest.TestCase):
    def test_create_and_reopen_preserves_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'relay/linux.json'
            calls = []
            def api(*args):
                calls.append(args)
                return dict(device_id='linux1', token='device-secret', management_token='manager-secret')
            config = setup.enroll(path, request=api)
            original = path.read_bytes()
            setup.enroll(path, 'https://clipboard-api.thewilners.com/#invite=other', request=api)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1], '/enroll')
            self.assertEqual(path.read_bytes(), original)
            for file in (path, Path(config['token_file']), Path(config['management_token_file'])):
                self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('secret', path.read_text())

    def test_join_uses_invite_and_rejects_other_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def api(*args):
                calls.append(args)
                return dict(device_id='joined', token='d', management_token='m')
            setup.enroll(Path(directory)/'linux.json', 'https://clipboard-api.thewilners.com/#invite=abc', request=api)
            self.assertEqual(calls[0][1], '/join')
            self.assertEqual(calls[0][2]['code'], 'abc')
        with self.assertRaises(ValueError):
            setup.invite_code('https://evil.test/#invite=abc')

    def test_failed_enrollment_does_not_write_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'linux.json'
            with self.assertRaises(ValueError):
                setup.enroll(path, request=lambda *args: {'device_id':'bad'})
            self.assertFalse(path.exists())

    def test_service_environment_keeps_display_and_uses_manager_bus(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'XDG_RUNTIME_DIR':directory, 'WAYLAND_DISPLAY':'wayland-2', 'DBUS_SESSION_BUS_ADDRESS':'unix:path=/private/session'}), patch.object(setup.subprocess, 'run') as run:
                setup.start_service()
                env=run.call_args.kwargs['env']
                self.assertEqual(env['DBUS_SESSION_BUS_ADDRESS'], 'unix:path='+directory+'/bus')
                self.assertIn('WAYLAND_DISPLAY="wayland-2"', (Path(directory)/'relay-clipboard.env').read_text())
                self.assertEqual((Path(directory)/'relay-clipboard.env').stat().st_mode & 0o777, 0o600)

    def test_initial_clipboard_and_secret_links_never_upload(self):
        agent=Agent(dict(device_id='dev',device_name='name',pause_file='/nonexistent-relay-test-pause'))
        calls=[]
        current=['existing private clipboard']
        agent.read=lambda: current[0]
        def api(method,path,body=None):
            calls.append((method,path,body))
            return {'entries':[], 'deliveries':[]}
        agent.api=api
        agent.tick()
        current[0]='https://clipboard-api.thewilners.com/#invite=secret'
        agent.tick()
        current[0]='Account https://clipboard-api.thewilners.com/#account=secret'
        agent.tick()
        self.assertFalse(any(path=='/entries' for _,path,_ in calls))
        current[0]='intended new copy'
        agent.tick()
        uploads=[body for _,path,body in calls if path=='/entries']
        self.assertEqual([value['text'] for value in uploads], ['intended new copy'])

if __name__ == '__main__':
    unittest.main()
