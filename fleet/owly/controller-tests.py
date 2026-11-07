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
        self.authorized_check = c.authorized
        self.authorization = patch.object(c, 'authorized', return_value=True)
        self.authorization.start()
    def tearDown(self):
        self.authorization.stop()
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
        self.assertIsNone(c.duration('forever'))
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
    def test_opt_out_blocks_roam_before_any_network_change(self):
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

    def test_receive_window_roams_temporarily_then_restores_original_profile(self):
        # Exercise the full successful lifecycle, including persisted recovery
        # state and expiry protection. Only external commands are replaced.
        for channel, band in [(6, 'bg'), (44, 'a'), (149, 'a')]:
            with self.subTest(channel=channel):
                events = []
                wifi = dict(interface='wlo1', original_uuid='original', original_bssid='aa',
                            current={'channel':153}, target={'bssid':'bb', 'channel':channel})
                def nm(*args, **kwargs):
                    events.append(('nm', args, kwargs))
                    if args[:2] == ('connection', 'up') and args[3] == 'clone':
                        state = c.read_state()
                        self.assertEqual(state['original_uuid'], 'original')
                        self.assertEqual(state['clone_uuid'], 'clone')
                        self.assertEqual(state['phase'], 'steering')
                        self.assertGreater(kwargs['timeout'], 15)
                    return result('clone')
                def run(args, **kwargs):
                    events.append(('run', args))
                    return result('{"receiving":true}' if args[1:3] == ['status', '--json'] else '')
                def timer(suffix, seconds):
                    self.assertTrue(c.read_state()['token'])
                    events.append(('timer', suffix, seconds))
                with patch.object(c, 'ALLOW_STEERING', True), patch.object(c, 'snapshot', return_value=wifi), \
                     patch.object(c, 'health_baseline', return_value='100.1.2.3'), \
                     patch.object(c, 'health_check', side_effect=lambda *a, **k: events.append(('health',))), \
                     patch.object(c, 'systemctl'), patch.object(c, 'native', side_effect=lambda name: '/usr/bin/' + name), \
                     patch.object(c, 'nm', side_effect=nm), patch.object(c, 'run', side_effect=run), \
                     patch.object(c, 'arm_timer', side_effect=timer), \
                     patch.object(c, 'stop_timer', side_effect=lambda suffix: events.append(('stop', suffix))):
                    c.enable('20s')
                    self.assertEqual(c.report()['phase'], 'receiving')
                    self.assertIsNone(c.DEADLINE)
                    c.restore_locked()
                self.assertIsNone(c.read_state())
                self.assertEqual(events[0][0:2], ('timer', 'rollback'))
                commands = [e[1] for e in events if e[0] == 'nm']
                self.assertEqual(commands[0][:5], ('connection', 'clone', '--temporary', 'uuid', 'original'))
                modify = next(args for args in commands if args[:2] == ('connection', 'modify'))
                self.assertEqual(modify[2:5], ('--temporary', 'uuid', 'clone'))
                self.assertEqual(modify[modify.index('connection.autoconnect') + 1], 'no')
                self.assertEqual(modify[modify.index('802-11-wireless.band') + 1], band)
                self.assertEqual(commands[-1], ('connection', 'delete', 'uuid', 'clone'))
                self.assertIn(('connection', 'up', 'uuid', 'original', 'ifname', 'wlo1', 'ap', 'aa'), commands)
                start = next(i for i, event in enumerate(events) if event == ('run', [c.OMDROP, 'on', '20s']))
                self.assertLess(events.index(('health',)), start)
                self.assertLess(events.index(('timer', 'expiry', 30)), events.index(('stop', 'rollback')))

    def test_unrelated_or_incompatible_access_points_never_change_wifi(self):
        wifi = self.scan('*:saved:aa:153:WPA2:70\n:other:bb:44:WPA2:99\n:saved:cc:6::98\n:saved:dd:36:WPA2:97')
        with patch.object(c, 'ALLOW_STEERING', True), patch.object(c, 'snapshot', return_value=wifi), \
             patch.object(c, 'systemctl'), patch.object(c, 'nm') as nm, \
             patch.object(c, 'run') as run, patch.object(c, 'arm_timer') as timer:
            self.assertEqual(c.report()['reason'], 'no_compatible_ap')
            with self.assertRaises(c.Failure): c.enable('20s')
            nm.assert_not_called()
            run.assert_not_called()
            timer.assert_not_called()
            self.assertIsNone(c.read_state())

    def test_unreachable_management_baseline_never_changes_wifi(self):
        wifi = dict(interface='wlo1', original_uuid='original', original_bssid='aa',
                    current={'channel':153}, target={'bssid':'bb', 'channel':44})
        with patch.object(c, 'ALLOW_STEERING', True), patch.object(c, 'snapshot', return_value=wifi), \
             patch.object(c, 'systemctl'), patch.object(c, 'health_baseline', side_effect=c.Failure('peer unreachable')), \
             patch.object(c, 'nm') as nm, patch.object(c, 'arm_timer') as timer:
            with self.assertRaises(c.Failure): c.enable('20s')
            nm.assert_not_called()
            timer.assert_not_called()
            self.assertIsNone(c.read_state())

    def test_network_manager_wait_allows_slow_roam_inside_process_deadline(self):
        # Goran needed longer than the former fixed 15-second nmcli limit.
        with patch.object(c, 'native', return_value='/usr/bin/nmcli'), \
             patch.object(c.subprocess, 'run', return_value=result()) as run:
            c.nm('connection', 'up', 'uuid', 'clone', timeout=35)
            args = run.call_args.args[0]
            wait = int(args[args.index('--wait') + 1])
            self.assertGreater(wait, 15)
            self.assertLess(wait, run.call_args.kwargs['timeout'])
            self.assertEqual(run.call_args.kwargs['timeout'], 35)
            c.DEADLINE = c.time.monotonic() + 4
            c.nm('connection', 'up', 'uuid', 'clone', timeout=35)
            self.assertGreater(run.call_args.kwargs['timeout'], 0)
            self.assertLessEqual(run.call_args.kwargs['timeout'], 4)

    def test_missing_original_ap_falls_back_only_to_original_saved_network(self):
        c.write_state(dict(clone_uuid='clone', original_uuid='original', original_bssid='aa', interface='wlo1'))
        def nm(*args, **kwargs):
            if 'ap' in args: raise c.Failure('original AP disappeared')
            return result('clone')
        with patch.object(c, 'nm', side_effect=nm) as calls, patch.object(c, 'run', return_value=result()), \
             patch.object(c, 'stop_timer'):
            c.restore_locked()
        activations = [call for call in calls.call_args_list if call.args[:2] == ('connection', 'up')]
        self.assertEqual(len(activations), 2)
        self.assertEqual(activations[1].args, ('connection', 'up', 'uuid', 'original', 'ifname', 'wlo1'))
        self.assertTrue(all(call.kwargs['timeout'] > 15 for call in activations))
        self.assertIsNone(c.read_state())

    def test_failed_restoration_keeps_recovery_state_and_timer(self):
        c.write_state(dict(token='recover', clone_uuid='clone', original_uuid='original', original_bssid='aa', interface='wlo1'))
        with patch.object(c, 'nm', side_effect=c.Failure('NetworkManager unavailable')), \
             patch.object(c, 'run', return_value=result()), patch.object(c, 'stop_timer') as stop:
            with self.assertRaises(c.Failure): c.restore_locked()
            stop.assert_not_called()
            self.assertEqual(c.read_state()['original_uuid'], 'original')
            self.assertEqual(c.read_state()['token'], 'recover')

    def test_invalid_backend_status_triggers_monitor_restore(self):
        c.write_state(dict(token='window', expires=c.time.time() + 100))
        with patch.object(c.sys, 'argv', ['controller', 'monitor', 'window']), \
             patch.object(c, 'run', return_value=result('service restarting')), \
             patch.object(c, 'restore_locked') as restore:
            c.monitor()
            restore.assert_called_once()

    def test_forever_preserves_startup_rollback_without_expiry(self):
        wifi = dict(interface='wlo1', original_uuid='original', original_bssid='aa',
                    current={'channel':149}, target={'bssid':'aa','channel':149})
        with patch.object(c, 'snapshot', return_value=wifi), patch.object(c, 'systemctl'), \
             patch.object(c, 'native', side_effect=lambda name: '/usr/bin/' + name), \
             patch.object(c, 'run', return_value=result('{"receiving":true}')) as run, \
             patch.object(c, 'arm_timer') as timer, patch.object(c, 'stop_timer') as stop:
            c.enable('forever')
        timer.assert_called_once_with('rollback', 90)
        stop.assert_called_once_with('rollback')
        self.assertIsNone(c.read_state()['expires'])
        self.assertEqual(c.read_state()['phase'], 'receiving')
        self.assertIn([c.OMDROP, 'on', 'forever'], [call.args[0] for call in run.call_args_list])

    def test_forever_monitor_waits_without_expiry_and_restores_on_loss(self):
        c.write_state(dict(token='window', expires=None))
        with patch.object(c.sys, 'argv', ['controller', 'monitor', 'window']), \
             patch.object(c, 'run', side_effect=[result('{"receiving":true}'), result('{"receiving":false}')]), \
             patch.object(c.time, 'sleep') as sleep, patch.object(c, 'restore_locked') as restore:
            c.monitor()
        sleep.assert_called_once_with(3)
        restore.assert_called_once()

    def test_authorization_preflight_never_requests_interaction(self):
        denied = subprocess.CompletedProcess([], 1, '', '')
        with patch.object(c, 'native', return_value='/usr/bin/pkcheck'), \
             patch.object(c, 'run', side_effect=[result(), denied]) as run:
            self.assertFalse(self.authorized_check())
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual([args[2] for args in commands],
                         ['org.omarchy.omdrop.radio', 'io.github.t4t5.Owly.acquire'])
        self.assertTrue(all('--allow-user-interaction' not in args for args in commands))

    def test_automatic_missing_policy_does_not_start_receiver_or_restore(self):
        with patch.object(c, 'authorized', return_value=False), \
             patch.object(c, 'enable') as enable, patch.object(c, 'restore_locked') as restore:
            with self.assertRaises(c.Failure): c.automatic_step()
            enable.assert_not_called()
            restore.assert_not_called()

    def test_automatic_starts_forever_then_honors_manual_stop(self):
        with patch.object(c, 'enable') as enable:
            c.automatic_step()
            enable.assert_called_once_with('forever', background=True)
        with patch.object(c.sys, 'argv', ['controller', 'off']), patch.object(c, 'restore_locked'):
            self.assertEqual(c.main(), 0)
        with patch.object(c, 'enable') as enable:
            c.automatic_step()
            enable.assert_not_called()

    def test_background_enable_rechecks_pause_under_lock(self):
        (c.runtime() / 'automatic-paused').touch()
        with patch.object(c, 'snapshot') as snapshot:
            c.enable('forever', background=True)
            snapshot.assert_not_called()

    def test_automatic_does_not_replace_active_window(self):
        c.write_state(dict(token='window', phase='receiving', expires=None))
        with patch.object(c, 'enable') as enable, patch.object(c, 'restore_locked') as restore, \
             patch.object(c, 'run', return_value=result('{"receiving":true}')), \
             patch.object(c, 'systemctl', return_value=result()):
            c.automatic_step()
            enable.assert_not_called()
            restore.assert_not_called()

    def test_automatic_restarts_missing_monitor_without_roaming(self):
        c.write_state(dict(token='window', phase='receiving', expires=None))
        inactive = subprocess.CompletedProcess([], 3, '', '')
        with patch.object(c, 'run', return_value=result('{"receiving":true}')), \
             patch.object(c, 'systemctl', return_value=inactive), \
             patch.object(c, 'start_monitor') as monitor, patch.object(c, 'enable') as enable:
            c.automatic_step()
        monitor.assert_called_once_with(c.read_state())
        enable.assert_not_called()

    def test_automatic_restores_stale_receiving_state_then_restarts(self):
        c.write_state(dict(token='window', phase='receiving', expires=None))
        events = []
        with patch.object(c, 'run', return_value=result('{"receiving":false}')), \
             patch.object(c, 'restore_locked', side_effect=lambda: events.append('restore')), \
             patch.object(c, 'enable', side_effect=lambda value, **kwargs: events.append(value)):
            c.automatic_step()
        self.assertEqual(events, ['restore', 'forever'])

    def test_automatic_finishes_failed_restore_before_restart(self):
        c.write_state(dict(token='window', phase='restore_failed'))
        events = []
        with patch.object(c, 'restore_locked', side_effect=lambda: events.append('restore')), \
             patch.object(c, 'enable', side_effect=lambda value, **kwargs: events.append(value)):
            c.automatic_step()
        self.assertEqual(events, ['restore', 'forever'])
        with patch.object(c, 'restore_locked', side_effect=c.Failure('unavailable')), \
             patch.object(c, 'enable') as enable:
            with self.assertRaises(c.Failure): c.automatic_step()
            enable.assert_not_called()

if __name__ == '__main__': unittest.main()
