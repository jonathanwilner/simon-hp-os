"""No-radio tests for the controller's network and recovery boundaries."""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

source = os.environ.get('CONTROLLER_SOURCE', str(Path(__file__).with_name('controller.py')))
spec = importlib.util.spec_from_loader('controller', SourceFileLoader('controller', source))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

def result(stdout=''):
    return subprocess.CompletedProcess([], 0, stdout, '')

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, XDG_RUNTIME_DIR=self.temp.name)
        self.env.start()
        c.DEADLINE = None
    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()
    def scan(self, rows):
        outputs = ['wlo1:wifi:connected\n', 'wlo1:original\n', rows]
        with patch.object(c, 'run', return_value=result('{"mode":"shared","hardware":true}')), patch.object(c, 'nm', side_effect=[result(x) for x in outputs]):
            return c.snapshot()
    def test_same_network_security_and_best_supported_channel(self):
        wifi = self.scan('*:Qguest:aa:64::70\n:Qguest:bb:149::50\n:Qguest:cc:6::40\n:other:dd:44::100\n:Qguest:ee:44:WPA2:99\n:Qguest:ff:36::98')
        self.assertEqual(wifi['target']['bssid'], 'bb')
    def test_no_candidate(self):
        self.assertIsNone(self.scan('*:Qguest:aa:64::70')['target'])
    def test_exclusive_refused_before_network_commands(self):
        with patch.object(c, 'run', return_value=result('{"mode":"exclusive","hardware":true}')), patch.object(c, 'nm') as nm:
            with self.assertRaises(c.Failure): c.snapshot()
            nm.assert_not_called()
    def test_escaped_fields(self):
        self.assertEqual(c.fields(r'Q\:guest:90\:56\:71'), ['Q:guest', '90:56:71'])
    def test_duration_bounds(self):
        self.assertEqual(c.duration('20s'), 20)
        self.assertEqual(c.duration('30m'), 1800)
        for value in ['once', '31m', '0', ';touch /tmp/x']:
            with self.assertRaises(c.Failure): c.duration(value)
    def test_backend_timeout_cannot_prevent_restore_and_cleanup_idempotent(self):
        c.write_state(dict(clone_uuid='clone', original_uuid='original', original_bssid='aa', interface='wlo1'))
        with patch.object(c, 'run', side_effect=c.Failure('backend hung')), patch.object(c, 'nm', return_value=result()) as nm, patch.object(c, 'stop_timer'):
            c.restore_locked()
            self.assertIn(('connection','up','uuid','original','ifname','wlo1','ap','aa'), [x.args for x in nm.call_args_list])
            self.assertIsNone(c.read_state())
            c.restore_locked()
    def test_clone_delete_failure_retains_retry_state(self):
        c.write_state(dict(clone_uuid='clone', original_uuid='original', original_bssid='aa', interface='wlo1'))
        def nm(*args, **kwargs):
            if args[:2] == ('connection','delete'): raise c.Failure('delete denied')
            return result('clone')
        with patch.object(c,'run',return_value=result()), patch.object(c,'nm',side_effect=nm):
            with self.assertRaises(c.Failure): c.restore_locked()
            self.assertEqual(c.read_state()['clone_uuid'], 'clone')
    def test_failed_activation_health_or_backend_restores(self):
        wifi = dict(interface='wlo1', original_uuid='original', original_bssid='aa', current={'channel':64}, target={'bssid':'bb','channel':149})
        for stage in ['activation', 'health', 'backend']:
            with self.subTest(stage=stage):
                events = []
                def nm(*args, **kwargs):
                    events.append(args)
                    if args[:2] == ('connection','up') and stage == 'activation': raise c.Failure('activation failed')
                    return result('clone')
                def health(*args, **kwargs):
                    if stage == 'health': raise c.Failure('management lost')
                def run(args, **kwargs):
                    if args[:2] == [c.OMDROP, 'on']: raise c.Failure('backend failed')
                    return result()
                def restore():
                    events.append(('restore',))
                    (c.runtime() / 'controller.json').unlink(missing_ok=True)
                    c.DEADLINE = None
                with patch.object(c,'ALLOW_STEERING',True), patch.object(c,'snapshot',return_value=wifi), patch.object(c,'health_baseline',return_value='100.1.2.3'), patch.object(c,'health_check',side_effect=health), patch.object(c,'systemctl'), patch.object(c,'arm_timer',side_effect=lambda *args: events.append(('timer',))), patch.object(c,'nm',side_effect=nm), patch.object(c,'run',side_effect=run), patch.object(c,'restore_locked',side_effect=restore):
                    with self.assertRaises(c.Failure): c.enable('20s')
                self.assertEqual(events[0], ('timer',))
                self.assertEqual(events[-1], ('restore',))
                self.assertTrue(any(x[:3] == ('connection','clone','--temporary') for x in events))
                self.assertTrue(any('connection.autoconnect' in x and 'no' in x for x in events))
    def test_monitor_stopped_or_expired_restores(self):
        for live, expires in [(False, c.time.time()+100), (True, c.time.time()-1)]:
            c.write_state(dict(token='window', expires=expires))
            with patch.object(c.sys,'argv',['controller','monitor','window']), patch.object(c,'run',return_value=result(c.json.dumps({'receiving':live}))), patch.object(c,'restore_locked') as restore:
                c.monitor()
                restore.assert_called_once()
    def test_stale_monitor_does_not_touch_new_window(self):
        c.write_state(dict(token='new', expires=c.time.time()+100))
        with patch.object(c.sys,'argv',['controller','monitor','old']), patch.object(c,'run') as run:
            c.monitor()
            run.assert_not_called()
    def test_default_gate_blocks_roam_before_any_network_change(self):
        wifi = dict(interface='wlo1', original_uuid='original', original_bssid='aa', current={'channel':64}, target={'bssid':'bb','channel':149})
        with patch.object(c,'ALLOW_STEERING',False), patch.object(c,'snapshot',return_value=wifi), patch.object(c,'systemctl'), patch.object(c,'nm') as nm, patch.object(c,'arm_timer') as timer:
            self.assertEqual(c.report()['reason'], 'steering_disabled')
            with self.assertRaises(c.Failure): c.enable('20s')
            nm.assert_not_called()
            timer.assert_not_called()
            self.assertIsNone(c.read_state())
    def test_compatible_current_ap_is_allowed_without_roaming(self):
        wifi = dict(original_bssid='aa', current={'channel':149}, target={'bssid':'aa','channel':149})
        with patch.object(c,'ALLOW_STEERING',False), patch.object(c,'snapshot',return_value=wifi):
            self.assertTrue(c.report()['can_enable'])
            self.assertFalse(c.report()['needs_steering'])
    def test_deadline_and_argv_only(self):
        c.DEADLINE = c.time.monotonic()-1
        with patch.object(c.subprocess,'run') as run:
            with self.assertRaises(c.Failure): c.run(['echo', '$(touch /tmp/evil)'])
            run.assert_not_called()
        c.DEADLINE = None
        with patch.object(c.subprocess,'run',return_value=result()) as run:
            c.run(['echo','$(touch /tmp/evil)'])
            self.assertNotIn('shell', run.call_args.kwargs)
            self.assertEqual(run.call_args.args[0][1], '$(touch /tmp/evil)')

if __name__ == '__main__': unittest.main()
