import asyncio
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('touch_support',Path(__file__).with_name('touch_support.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

def config(mode='off', profile='laptop'):
    return {'enable':True,'profile':profile,'keyboard':{'mode':mode,'backend':'hp-os-qml','fallback':'squeekboard','allowFallback':True,'autoShowOnTextFocus':True},'rotation':{'mode':'off'},'gestures':{'enable':True}}

class PolicyTests(unittest.TestCase):
    def test_legacy_backend_normalizes_saved_and_declarative_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'config.json'
            cfg = config('manual'); cfg['keyboard']['backend'] = 'celia-qml'
            path.write_text(json.dumps(cfg))
            self.assertEqual(t.load_config(str(path), preferences=False)['keyboard']['backend'], 'hp-os-qml')
            prefs = Path(tmp)/'prefs.json'; prefs.write_text(json.dumps({'backend':'celia-qml'}))
            with patch.object(t, 'preferences_path', return_value=prefs):
                self.assertEqual(t.load_config(str(path))['keyboard']['backend'], 'hp-os-qml')

    def test_off_has_no_runtime_side_effect(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(t, 'runtime_dir', side_effect=AssertionError('must not access runtime')):
                with patch.object(t,'load_config',return_value=config()): self.assertEqual(t.main(['run']),0)
    def test_off_blocks_all_activation(self):
        for posture in ('tablet','laptop'):
            for explicit in (True,False):self.assertFalse(t.permitted(config(),posture,explicit))
    def test_manual_never_autoshows(self):
        self.assertFalse(t.desired_visible(config('manual'),'tablet',False,True,False))
        self.assertTrue(t.desired_visible(config('manual'),'laptop',True,False,False))
    def test_convertible_requires_confirmation(self):
        c=config('tablet-only','convertible')
        self.assertFalse(t.permitted(c,'laptop',True))
        self.assertTrue(t.permitted(c,'tablet'))
        self.assertFalse(t.desired_visible(c,'tablet',False,False,False))
        self.assertTrue(t.desired_visible(c,'tablet',False,True,False))
    def test_always_focus_and_hide(self):
        c=config('always','tablet')
        self.assertTrue(t.desired_visible(c,'tablet',False,True,False))
        self.assertFalse(t.desired_visible(c,'tablet',False,True,True))
    def test_none_blocks_activation(self):
        c=config('always');c['keyboard']['backend']='none'
        self.assertFalse(t.permitted(c,'tablet',True))
    def test_diagnostics_strip_input(self):
        result=t.safe_state({'visible':True,'preedit':'secret','surrounding':'secret','candidates':['secret'],'secure':True})
        self.assertEqual(result,{'visible':True,'secure':True})
    def test_atomic_state_is_private(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json';t.atomic_json(p,{'visible':False})
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(p.read_text()),{'visible':False})
    def test_profile_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            for profile,mode in [('laptop','off'),('convertible','tablet-only'),('tablet','always')]:
                p=Path(d)/'cfg.json';p.write_text(json.dumps({'enable':True,'profile':profile}))
                self.assertEqual(t.load_config(str(p))['keyboard']['mode'],mode)
    def test_disabled_patch_explicitly_disables_default_gestures(self):
        c=config();c['enable']=False
        self.assertIn('off;',t.gesture_config(c,True))
        self.assertNotIn('touchscreen-swipe',t.gesture_config(c,False))
    def test_off_keeps_gestures_but_never_keyboard_edge(self):
        c=config();c['gestures']['keyboardEdge']=True
        self.assertIn('horizontal-swipe',t.gesture_config(c,True))
        self.assertNotIn('touch-support',t.gesture_config(c,True))
    def test_off_is_persisted_preference_ceiling(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d}):
            p=Path(d)/'base.json';p.write_text(json.dumps(config()))
            saved=t.preferences_path();saved.parent.mkdir();saved.write_text(json.dumps({'mode':'always','backend':'squeekboard'}))
            c=t.load_config(p)
            self.assertEqual(c['keyboard']['mode'],'off')
            self.assertEqual(c['keyboard']['backend'],'squeekboard')
    def test_rotation_off_has_no_runtime_side_effect(self):
        with patch.object(t,'load_config',return_value=config()),patch.object(t,'runtime_dir',side_effect=AssertionError('unexpected runtime')):
            self.assertEqual(t.main(['rotation-run']),0)
    def test_rotation_independent_of_keyboard_off(self):
        async def run():
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_RUNTIME_DIR':d}):
                c=config();c['rotation']={'mode':'tablet-only','output':'eDP-1'}
                r=t.RotationController(c);r.root.mkdir();calls=[]
                class Child:
                    returncode=0
                    async def wait(self):return 0
                async def spawn(args):calls.append(args);return Child()
                r.spawn=spawn
                r.start_backend=lambda *_:self.fail('rotation must never start keyboard')
                r.sensor_orientation='left-up'
                await r.reconcile()
                self.assertEqual(calls[-1][-1],'normal')
                r.state['posture']='tablet';await r.reconcile()
                self.assertEqual(calls[-1][-1],'90')
                r.state['posture']='laptop';await r.reconcile()
                self.assertEqual(calls[-1][-1],'normal')
                self.assertFalse((Path(d)/'hp-os-touch').exists())
                state=json.loads(r.state_path.read_text())
                self.assertNotIn('visible',state)
        asyncio.run(run())
    def test_effective_policy_published_without_text(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_RUNTIME_DIR':d}):
            c=config('manual');c['keyboard']['backend']='squeekboard'
            r=t.Controller(c);r.root.mkdir();r.state['preedit']='private';r.publish()
            state=json.loads(r.state_path.read_text())
            self.assertEqual(state['config']['keyboard']['mode'],'manual')
            self.assertEqual(state['config']['keyboard']['backend'],'squeekboard')
            self.assertNotIn('preedit',state)
            self.assertNotIn('config',t.safe_state(state))
    def test_stock_backend_disables_patched_defaults(self):
        c=config();c['gestures']['backend']='stock'
        self.assertIn('off;',t.gesture_config(c,True))
    def test_fallback_hide_stops_until_explicit_show(self):
        async def run():
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_RUNTIME_DIR':d}):
                r=t.Controller(config('always'));r.root.mkdir();r.state['backend']='squeekboard';calls=[]
                async def stop():calls.append('stop');r.backend=None
                async def start(name):calls.append(name)
                r.stop_backend=stop;r.start_backend=start
                await r.command({'op':'hide'})
                await r.reconcile()
                self.assertEqual(calls,['stop','stop'])
                await r.command({'op':'show'})
                self.assertIn('hp-os-qml',calls)
        asyncio.run(run())
    def test_command_mutation_waits_for_transition_lock(self):
        async def run():
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_RUNTIME_DIR':d}):
                r=t.Controller(config('always'));r.root.mkdir()
                await r.transition.acquire()
                pending=asyncio.create_task(r.command({'op':'mode','value':'off'}))
                await asyncio.sleep(0)
                self.assertEqual(r.cfg['keyboard']['mode'],'always')
                self.assertFalse(pending.done())
                r.transition.release()
                await asyncio.wait_for(pending,1)
                self.assertEqual(r.cfg['keyboard']['mode'],'off')
        asyncio.run(run())
    def test_foreign_native_socket_receives_no_configuration(self):
        async def run():
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_RUNTIME_DIR':d}):
                r=t.Controller(config('always'));r.root.mkdir();received=asyncio.Future()
                async def foreign(reader,writer):
                    received.set_result(await reader.read())
                    writer.close();await writer.wait_closed()
                server=await asyncio.start_unix_server(foreign,path=str(r.input_path))
                class Child:
                    pid=os.getpid()+100000
                    returncode=None
                    def terminate(self): self.returncode=-15
                    async def wait(self): return self.returncode
                child=Child();spawned=[]
                async def spawn(args):spawned.append(args);return child
                r.spawn=spawn
                try:
                    await r.start_backend('hp-os-qml')
                    self.assertEqual(await asyncio.wait_for(received,1),b'')
                    self.assertEqual(len(spawned),1)
                    self.assertEqual(r.state['error'],'socket-owner-conflict')
                    self.assertIsNone(r.backend)
                    self.assertEqual(child.returncode,-15)
                finally:server.close();await server.wait_closed()
        asyncio.run(run())
    def test_gesture_setting_independent_of_keyboard_off(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d,'INIR_NIRI_CONFIG_DIR':d+'/niri'}):
            p=Path(d)/'base.json';p.write_text(json.dumps(config()))
            with patch.object(t,'send',side_effect=RuntimeError('no keyboard controller')):
                self.assertEqual(t.main(['--config',str(p),'configure','gestures.enable','false']),0)
            c=t.load_config(p)
            self.assertFalse(c['gestures']['enable'])
            self.assertEqual(c['keyboard']['mode'],'off')
            self.assertFalse((Path(d)/'niri').exists())
    def test_gesture_replacement_validation_preserves_other_config(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'INIR_NIRI_CONFIG_DIR':d,'HP_OS_TOUCH_PATCHED':'1'}):
            directory=Path(d)/'config.d';directory.mkdir()
            target=directory/'60-touch.kdl';target.write_text('original')
            other=directory/'50-startup.kdl';other.write_text('unrelated')
            class Result: returncode=1
            with patch.object(t.subprocess,'run',return_value=Result()):
                with self.assertRaises(RuntimeError):t.update_gesture_file(config())
            self.assertEqual(target.read_text(),'original')
            self.assertEqual(list(directory.glob('.60-touch-*')),[])
            Result.returncode=0
            with patch.object(t.subprocess,'run',return_value=Result()):self.assertTrue(t.update_gesture_file(config()))
            self.assertIn('touchscreen-swipe',target.read_text())
            self.assertEqual(other.read_text(),'unrelated')
            self.assertEqual(target.stat().st_mode&0o777,0o600)
    def test_seat_conflict_never_falls_back(self):
        async def run():
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_RUNTIME_DIR':d}):
                c=t.Controller(config('always'));called=[]
                async def start(*args,**kwargs):called.append(args)
                c.start_backend=start
                await c.fallback(3)
                self.assertEqual(called,[])
                await c.fallback(1)
                self.assertEqual(called,[('squeekboard',)])
        asyncio.run(run())

if __name__=='__main__':unittest.main()
