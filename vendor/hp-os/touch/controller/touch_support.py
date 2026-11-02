#!/usr/bin/env python3
"""HP-OS touch policy and child ownership. Never records text-input content."""
from __future__ import annotations
import argparse
import asyncio
import contextlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile

MODES = ('off', 'manual', 'tablet-only', 'always')
BACKENDS = ('hp-os-qml', 'squeekboard', 'wvkbd', 'none')

def canonical_backend(value):
    # Migrate persisted and declarative configurations from the former name.
    return 'hp-os-qml' if value == 'celia-qml' else value



def preferences_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home()/".config")))/"hp-os/touch-preferences.json"


def load_config(path=None, preferences=True):
    paths = [Path(path or os.environ.get('HP_OS_TOUCH_CONFIG', '/nonexistent')),
             Path.home()/'.config/hp-os/touch.json', Path('/etc/hp-os/touch.json')]
    cfg = next((json.loads(p.read_text()) for p in paths if p.is_file()), {})
    cfg.setdefault('enable', False)
    cfg.setdefault('profile', 'laptop')
    kb = cfg.setdefault('keyboard', {})
    kb.setdefault('mode', {'convertible': 'tablet-only', 'tablet': 'always'}.get(cfg['profile'], 'off'))
    kb.setdefault('backend', 'hp-os-qml')
    kb.setdefault('fallback', 'squeekboard')
    kb.setdefault('allowFallback', True)
    kb.setdefault('autoShowOnTextFocus', True)
    cfg['_policyOff'] = not cfg['enable'] or kb['mode'] == 'off'
    if preferences and preferences_path().is_file():
        saved = json.loads(preferences_path().read_text())
        for key in ('mode', 'backend', 'allowFallback'):
            if key in saved and not (key == 'mode' and cfg['_policyOff']): kb[key] = saved[key]
    cfg.setdefault('rotation', {}).setdefault('mode', 'off')
    cfg.setdefault('gestures', {}).setdefault('enable', True)
    if preferences and preferences_path().is_file():
        saved = json.loads(preferences_path().read_text())
        if isinstance(saved.get('gestures.enable'), bool): cfg['gestures']['enable'] = saved['gestures.enable']
    kb['backend'] = canonical_backend(kb['backend'])
    if kb['mode'] not in MODES or kb['backend'] not in BACKENDS:
        raise ValueError('Invalid keyboard mode or backend')
    return cfg


def runtime_dir():
    base = os.environ.get('XDG_RUNTIME_DIR')
    if not base:
        raise RuntimeError('XDG_RUNTIME_DIR is required')
    p = Path(base)/'hp-os-touch'
    return p


def enabled(cfg):
    return cfg['enable'] and cfg['keyboard']['mode'] != 'off' and cfg['keyboard']['backend'] != 'none'


def permitted(cfg, posture, explicit=False):
    if not enabled(cfg):
        return False
    return {'manual': explicit, 'tablet-only': posture == 'tablet', 'always': True}[cfg['keyboard']['mode']]


def desired_visible(cfg, posture, explicit, active, hidden):
    return permitted(cfg, posture, explicit) and not hidden and (explicit or (cfg['keyboard']['mode'] != 'manual' and cfg['keyboard']['autoShowOnTextFocus'] and active))


def safe_state(state):
    # Deliberately exclude preedit, candidates, surrounding text and input values.
    allowed = ('visible', 'backend', 'posture', 'postureSource', 'screen', 'orientation', 'error', 'active', 'secure', 'purpose', 'available', 'mode')
    return {k: state[k] for k in allowed if k in state}


def safe_config(cfg):
    """Only known declarative UI policy; never include native input state."""
    result = {k:cfg[k] for k in ('enable','profile') if k in cfg}
    fields = {
        'keyboard': ('mode','backend','fallback','allowFallback','autoShowOnTextFocus','showPanelButton','theme','colorScheme','languages','prediction','chineseEngine','floating','haptics','height','keyScale','popups','keyPreview','accentColor','sound','reducedMotion'),
        'rotation': ('mode','output'), 'gestures': ('enable','backend','keyboardEdge','controlsEdge')}
    for section, keys in fields.items():
        result[section] = {k:cfg.get(section,{}).get(k) for k in keys if k in cfg.get(section,{})}
    return result


def atomic_json(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix='.'+path.name, dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f)
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(tmp)


def tablet_switch(fd):
    """Read SW_TABLET_MODE using EVIOCGSW, without reading keyboard events."""
    bits = bytearray(8)
    fcntl.ioctl(fd, (2 << 30) | (len(bits) << 16) | (ord('E') << 8) | 0x1b, bits, True)
    return bool(bits[0] & (1 << 1))  # linux/input-event-codes.h SW_TABLET_MODE=1


def executable(env, fallback):
    return os.environ.get(env, fallback)


class Controller:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = runtime_dir()
        self.state_path = Path(os.environ.get('HP_OS_TOUCH_STATE', self.root/'state.json'))
        self.input_path = self.root/'input.sock'
        self.state = {'visible': False, 'backend': None, 'posture': 'laptop', 'postureSource': 'unconfirmed',
                      'active': False, 'secure': True, 'available': False, 'mode': cfg['keyboard']['mode'], 'error': None}
        if cfg['profile'] == 'tablet': self.state.update(posture='tablet', postureSource='configured-tablet')
        self.explicit = False
        self.hidden = False
        self.override = None
        self.external_hidden = False
        self.backend = None
        self.qml = None
        self.backend_writer = None
        self.generation = 0
        self.transition = asyncio.Lock()
        self.devices = {}
        self.stop = asyncio.Event()
        self.children = set()
        self.background = set()

    def task(self, coro):
        t = asyncio.create_task(coro); self.background.add(t); t.add_done_callback(self.background.discard)
        return t

    def publish(self):
        self.state['visible'] = bool(self.backend and desired_visible(self.cfg, self.state['posture'], self.explicit, self.state['active'], self.hidden))
        atomic_json(self.state_path, {**safe_state(self.state), 'config':safe_config(self.cfg)})

    async def spawn(self, args):
        # Child stderr is also discarded: IME libraries can log submitted text.
        env = dict(os.environ, HP_OS_TOUCH_STATE=str(self.state_path), HP_OS_TOUCH_INPUT_SOCKET=str(self.input_path))
        p = await asyncio.create_subprocess_exec(*args, env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        self.children.add(p)
        return p

    async def terminate(self, proc):
        if proc and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError): proc.terminate()
            try: await asyncio.wait_for(proc.wait(), 3)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError): proc.kill()
                await proc.wait()
        self.children.discard(proc)

    async def stop_backend(self):
        self.generation += 1
        if self.backend_writer:
            self.backend_writer.close(); self.backend_writer = None
        await self.terminate(self.qml); self.qml = None
        await self.terminate(self.backend); self.backend = None
        self.state.update(backend=None, active=False, available=False, visible=False)
        self.publish()

    async def reconcile(self):
        async with self.transition:
            await self.reconcile_locked()

    async def reconcile_locked(self):
        if self.external_hidden or not permitted(self.cfg, self.state['posture'], self.explicit):
            await self.stop_backend(); return
        if not self.backend:
            await self.start_backend(self.cfg['keyboard']['backend'])
        if self.backend_writer:
            self.backend_writer.write((json.dumps({'op': 'manual', 'enabled': self.explicit})+'\n').encode())
            await self.backend_writer.drain()
        self.publish()
        if self.state['backend'] == 'squeekboard' and self.explicit:
            await self.squeek_visible(True)

    async def start_backend(self, name, fallback=False):
        if name == 'squeekboard' and not self.explicit and not self.cfg['keyboard']['autoShowOnTextFocus']:
            return
        args = {
            'hp-os-qml': [executable('HP_OS_TOUCH_BACKEND', 'hp-os-input-backend'), '--socket', str(self.input_path)],
            'squeekboard': [executable('HP_OS_TOUCH_SQUEEKBOARD', 'squeekboard')],
            'wvkbd': [executable('HP_OS_TOUCH_WVKBD', 'wvkbd-mobintl')],
        }[name]
        if name == 'hp-os-qml' and os.environ.get('HP_OS_TOUCH_RIME_DATA'):
            args += ['--rime-data', os.environ['HP_OS_TOUCH_RIME_DATA']]
        try:
            self.backend = await self.spawn(args)
        except OSError:
            self.state['error'] = 'backend-unavailable'
            if not fallback: await self.fallback(1)
            return
        self.state.update(backend=name, error=None)
        generation = self.generation
        if name == 'hp-os-qml':
            reader = None
            for _ in range(1200):
                if self.backend.returncode is not None: break
                try:
                    reader, writer = await asyncio.open_unix_connection(str(self.input_path))
                    import struct
                    peer = writer.get_extra_info('socket')
                    pid, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if pid != self.backend.pid or uid != os.getuid():
                        writer.close(); await writer.wait_closed()
                        await self.stop_backend()
                        self.state['error'] = 'socket-owner-conflict'; self.publish()
                        return
                    self.backend_writer = writer
                    break
                except (FileNotFoundError, ConnectionRefusedError): await asyncio.sleep(.05)
            if not reader:
                code = self.backend.returncode
                await self.stop_backend()
                self.state['error'] = 'seat-conflict' if code == 3 else 'backend-startup-failed'
                if not fallback: await self.fallback(code if code is not None else 1)
                return
            settings = self.cfg['keyboard']
            initial = [{'op':'prediction','enabled':settings.get('prediction',{}).get('enable',True)}]
            languages = settings.get('languages',['en_US'])
            if languages: initial.append({'op':'language','language':languages[0]})
            for command in initial:
                self.backend_writer.write((json.dumps(command)+'\n').encode())
            await self.backend_writer.drain()
            self.task(self.read_backend(reader, generation))
            try:
                self.qml = await self.spawn([executable('HP_OS_TOUCH_QML', 'hp-os-keyboard')])
            except OSError:
                await self.stop_backend(); self.state['error'] = 'qml-unavailable'
                if not fallback: await self.fallback(1)
                return
            self.task(self.watch_qml(self.qml, generation))
        self.task(self.watch_backend(self.backend, generation, fallback))

    async def fallback(self, code):
        # Code 3 is an occupied seat. Never launch another input-method client.
        kb = self.cfg['keyboard']
        if code != 3 and kb.get('allowFallback', True) and kb.get('fallback') == 'squeekboard' and permitted(self.cfg, self.state['posture'], self.explicit):
            await self.start_backend('squeekboard', fallback=True)

    async def read_backend(self, reader, generation):
        try:
            while generation == self.generation:
                line = await reader.readline()
                if not line or generation != self.generation: break
                msg = json.loads(line)
                if msg.get('type') != 'state': continue
                previous = self.state['active']
                for key in ('active', 'available', 'secure', 'purpose'):
                    if key in msg: self.state[key] = msg[key]
                if not self.state['active'] and previous: self.hidden = False
                if msg.get('available') is False and self.backend and self.backend.returncode == 3:
                    self.state['error'] = 'seat-conflict'
                self.publish()
        except (ValueError, ConnectionError, asyncio.LimitOverrunError):
            self.state['error'] = 'backend-protocol-error'; self.publish()

    async def watch_backend(self, proc, generation, was_fallback):
        code = await proc.wait()
        if generation != self.generation: return
        async with self.transition:
            if generation != self.generation: return
            await self.stop_backend()
            self.state['error'] = 'seat-conflict' if code == 3 else 'backend-exited'
            if not was_fallback and code != 0: await self.fallback(code)
            self.publish()

    async def watch_qml(self, proc, generation):
        await proc.wait()
        if generation != self.generation: return
        async with self.transition:
            if generation != self.generation: return
            await self.stop_backend(); self.state['error'] = 'qml-exited'
            await self.fallback(1); self.publish()

    async def squeek_visible(self, visible):
        # Wait for the just-started child's DBus name before requesting visibility.
        for _ in range(30):
            if not self.backend or self.backend.returncode is not None: return
            try:
                p = await self.spawn(['gdbus', 'call', '--session', '--dest', 'sm.puri.OSK0', '--object-path', '/sm/puri/OSK0', '--method', 'sm.puri.OSK0.SetVisible', str(visible).lower()])
                try: await asyncio.wait_for(p.wait(), 2)
                except asyncio.TimeoutError: await self.terminate(p)
                self.children.discard(p)
                if p.returncode == 0: return
            except OSError: break
            await asyncio.sleep(.1)
        self.state['error'] = 'fallback-visibility-unavailable'; self.publish()

    async def squeek_is_visible(self):
        try:
            p = await asyncio.create_subprocess_exec('gdbus','call','--session','--dest','sm.puri.OSK0','--object-path','/sm/puri/OSK0','--method','org.freedesktop.DBus.Properties.Get','sm.puri.OSK0','Visible',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            self.children.add(p)
            try: data,_ = await asyncio.wait_for(p.communicate(),2)
            except asyncio.TimeoutError:
                await self.terminate(p); return self.state['visible']
            self.children.discard(p)
            if p.returncode == 0: return b'true' in data.lower()
        except OSError: pass
        return self.state['visible']

    async def command(self, request):
        async with self.transition:
            return await self.command_locked(request)

    async def command_locked(self, request):
        op = request.get('op')
        if op == 'status': return safe_state(self.state)
        if op in ('show', 'hide', 'toggle'):
            if op == 'toggle' and self.state['backend'] == 'squeekboard':
                self.state['visible'] = await self.squeek_is_visible()
            show = op == 'show' or (op == 'toggle' and not self.state['visible'])
            if show: self.external_hidden = False
            elif self.state['backend'] == 'squeekboard':
                # Squeekboard owns its focus listener. Stop it to guarantee hide.
                self.external_hidden = True
            self.explicit, self.hidden = show, not show
        elif op == 'posture':
            value = request.get('value')
            if value not in ('auto', 'laptop', 'tablet'): raise ValueError('Invalid posture')
            self.override = None if value == 'auto' else value
            self.refresh_posture()
        elif op == 'backend':
            value = canonical_backend(request.get('value'))
            if value not in BACKENDS: raise ValueError('Invalid backend')
            await self.stop_backend(); self.cfg['keyboard']['backend'] = value
        elif op == 'config-view':
            self.cfg['gestures'] = load_config()['gestures']
            self.publish(); return safe_state(self.state)
        elif op == 'reload':
            await self.stop_backend()
            self.cfg = load_config()
            self.state['mode'] = self.cfg['keyboard']['mode']
            if not enabled(self.cfg): self.stop.set(); return safe_state(self.state)
        elif op == 'mode':
            value = request.get('value')
            if value not in MODES: raise ValueError('Invalid mode')
            self.cfg['keyboard']['mode'] = value; self.state['mode'] = value
            if value == 'off':
                await self.stop_backend(); self.stop.set(); return safe_state(self.state)
        else: raise ValueError('Unsupported command')
        await self.reconcile_locked()
        return safe_state(self.state)

    async def client(self, reader, writer):
        try:
            # UDS directory is0700/socket0600 and peerUID checked independently.
            peer = writer.get_extra_info('socket')
            import struct
            _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != os.getuid(): raise PermissionError('Different user')
            line = await asyncio.wait_for(reader.readline(), 2)
            result = await self.command(json.loads(line))
            writer.write((json.dumps(result)+'\n').encode()); await writer.drain()
        except (ValueError, OSError, asyncio.TimeoutError):
            writer.write(b'{"error":"invalid-command"}\n')
        finally:
            writer.close(); await writer.wait_closed()

    def refresh_posture(self):
        if self.override:
            self.state.update(posture=self.override, postureSource='manual')
        elif self.cfg['profile'] == 'tablet':
            self.state.update(posture='tablet', postureSource='configured-tablet')
        elif self.devices:
            tablet = any(d['tablet'] for d in self.devices.values())
            self.state.update(posture='tablet' if tablet else 'laptop', postureSource='SW_TABLET_MODE')
        else:
            self.state.update(posture='laptop', postureSource='unconfirmed')
        self.task(self.reconcile())

    def scan_switches(self):
        try:
            import evdev
            from evdev import ecodes
        except ImportError:
            self.state['error'] = 'evdev-unavailable'; return
        paths = set(evdev.list_devices())
        for path in list(self.devices):
            if path not in paths:
                self.devices[path]['task'].cancel(); self.devices[path]['device'].close(); del self.devices[path]
        for path in paths - self.devices.keys():
            try:
                d = evdev.InputDevice(path)
                if ecodes.SW_TABLET_MODE not in d.capabilities().get(ecodes.EV_SW, []): d.close(); continue
                self.devices[path] = {'device': d, 'tablet': tablet_switch(d.fd)}
                self.devices[path]['task'] = self.task(self.watch_switch(path))
            except (OSError, PermissionError): continue
        self.refresh_posture()

    async def watch_switch(self, path):
        from evdev import ecodes
        d = self.devices[path]['device']
        try:
            async for e in d.async_read_loop():
                if e.type == ecodes.EV_SW and e.code == ecodes.SW_TABLET_MODE:
                    self.devices[path]['tablet'] = bool(e.value); self.refresh_posture()
        except OSError:
            if path in self.devices: self.devices.pop(path)['device'].close()
            self.refresh_posture()

    def watch_devices(self):
        self.scan_switches()
        try:
            import pyudev
            self.udev = pyudev.Monitor.from_netlink(pyudev.Context()); self.udev.filter_by('input'); self.udev.start()
            def ready():
                while self.udev.poll(timeout=0) is not None: pass
                self.scan_switches()
            asyncio.get_running_loop().add_reader(self.udev.fileno(), ready)
        except (ImportError, OSError):
            self.state['error'] = 'udev-unavailable'

    async def watch_resume(self):
        try:
            p = await asyncio.create_subprocess_exec('gdbus', 'monitor', '--system', '--dest', 'org.freedesktop.login1', '--object-path', '/org/freedesktop/login1', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        except OSError: return
        self.children.add(p)
        async for line in p.stdout:
            if b'PrepareForSleep' in line and b'false' in line: self.scan_switches()

    async def rotate(self):
        # monitor-sensor claims and releases the sensor through iio-sensor-proxy.
        output = self.cfg['rotation'].get('output')
        if not output:
            self.state['error'] = 'rotation-output-required'; return
        try:
            p = await asyncio.create_subprocess_exec('monitor-sensor', '--accel', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        except OSError:
            self.state['error'] = 'sensor-unavailable'; return
        self.children.add(p)
        async for line in p.stdout:
            value = line.decode(errors='replace').strip().split(':')[-1].strip().rstrip(')')
            if value not in ('normal', 'left-up', 'bottom-up', 'right-up'): continue
            self.sensor_orientation = value
            await self.reconcile()

    async def run(self):
        if not enabled(self.cfg): return 0
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or self.root.stat().st_uid != os.getuid(): raise RuntimeError('Unsafe runtime directory')
        os.chmod(self.root, 0o700)
        with (self.root/'seat.lock').open('w') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return 0
            os.chmod(self.root/'seat.lock', 0o600)
            path = self.root/'control.sock'
            with contextlib.suppress(FileNotFoundError): path.unlink()
            server = await asyncio.start_unix_server(self.client, path=str(path), limit=4096)
            os.chmod(path, 0o600)
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT): loop.add_signal_handler(sig, self.stop.set)
            self.publish()
            if self.cfg['keyboard']['mode'] == 'tablet-only': self.watch_devices()
            self.task(self.watch_resume())
            await self.reconcile()
            try: await self.stop.wait()
            finally:
                server.close(); await server.wait_closed()
                for task in list(self.background): task.cancel()
                await self.stop_backend()
                for proc in list(self.children): await self.terminate(proc)
                for d in self.devices.values(): d['device'].close()
                with contextlib.suppress(FileNotFoundError): path.unlink()
        return 0


class RotationController(Controller):
    """Independent sensor owner; never acquires an input-method seat or OSK child."""
    def __init__(self, cfg):
        super().__init__(cfg)
        self.root = runtime_dir().parent/'hp-os-rotation'
        self.state_path = self.root/'state.json'
        self.sensor_orientation = 'normal'
        self.applied_orientation = None
        self.override = cfg['rotation'].get('postureOverride')

    def publish(self):
        atomic_json(self.state_path, {k: self.state[k] for k in ('posture','postureSource','orientation','screen','error') if k in self.state})

    async def reconcile(self):
        async with self.transition:
            output = self.cfg['rotation'].get('output')
            if not output: return
            value = self.sensor_orientation
            if self.cfg['rotation']['mode'] == 'tablet-only' and self.state['posture'] != 'tablet': value = 'normal'
            if value == self.applied_orientation: return
            transforms = {'normal':'normal','left-up':'90','bottom-up':'180','right-up':'270'}
            try:
                q = await self.spawn([executable('HP_OS_TOUCH_NIRI','niri'), 'msg','output',output,'transform',transforms[value]])
                await q.wait(); self.children.discard(q)
            except OSError:
                self.state['error'] = 'rotation-compositor-unavailable'; self.publish(); return
            if q.returncode == 0:
                self.applied_orientation = value
                self.state.update(orientation=value, screen=output); self.publish()

    async def command(self, request):
        if request.get('op') == 'posture':
            value = request.get('value')
            if value not in ('auto','laptop','tablet'): raise ValueError('Invalid posture')
            self.override = None if value == 'auto' else value
            self.refresh_posture()
            await self.reconcile()
        elif request.get('op') != 'status': raise ValueError('Unsupported rotation command')
        return {k:self.state[k] for k in ('posture','postureSource','orientation','screen','error') if k in self.state}

    async def run(self):
        if not self.cfg['enable'] or self.cfg['rotation']['mode'] == 'off': return 0
        if not self.cfg['rotation'].get('output'): return 2
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or self.root.stat().st_uid != os.getuid(): raise RuntimeError('Unsafe rotation directory')
        os.chmod(self.root,0o700)
        with (self.root/'rotation.lock').open('w') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: return 0
            path=self.root/'control.sock'
            with contextlib.suppress(FileNotFoundError): path.unlink()
            server=await asyncio.start_unix_server(self.client,path=str(path),limit=4096)
            os.chmod(path,0o600)
            loop=asyncio.get_running_loop()
            for sig in (signal.SIGTERM,signal.SIGINT): loop.add_signal_handler(sig,self.stop.set)
            self.publish()
            if self.cfg['rotation']['mode'] == 'tablet-only':
                self.watch_devices(); self.task(self.watch_resume())
            sensor=self.task(self.rotate())
            sensor.add_done_callback(lambda _:self.stop.set())
            try: await self.stop.wait()
            finally:
                server.close(); await server.wait_closed()
                for task in list(self.background): task.cancel()
                for proc in list(self.children): await self.terminate(proc)
                for d in self.devices.values(): d['device'].close()
                with contextlib.suppress(FileNotFoundError): path.unlink()
        return 0


def send(command, rotation=False):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(65 if command.get('op') in ('show','toggle','backend','mode','reload') else 3)
        root=runtime_dir().parent/'hp-os-rotation' if rotation else runtime_dir()
        s.connect(str(root/'control.sock'))
        s.sendall((json.dumps(command)+'\n').encode())
        return json.loads(s.recv(8192))


def doctor(cfg):
    result = {'enabled': enabled(cfg), 'profile': cfg['profile'], 'mode': cfg['keyboard']['mode'], 'backend': cfg['keyboard']['backend'],
              'commands': {}, 'protocols': {}, 'tabletPosture': 'unconfirmed-laptop', 'rotation': cfg['rotation']['mode'],
              'inputMethodOwnership': 'One managed child; externally owned seat fails closed'}
    for env, name in [('HP_OS_TOUCH_BACKEND','hp-os-input-backend'),('HP_OS_TOUCH_QML','hp-os-keyboard'),('HP_OS_TOUCH_SQUEEKBOARD','squeekboard')]:
        result['commands'][name] = bool(shutil.which(executable(env,name)))
    try:
        p = subprocess.run(['wayland-info'], capture_output=True, timeout=3, text=True)
        result['protocols'] = {n: n in p.stdout for n in ('zwp_input_method_manager_v2','zwp_text_input_manager_v3','zwp_virtual_keyboard_manager_v1','zwlr_layer_shell_v1')}
    except (OSError, subprocess.TimeoutExpired): result['protocolProbe'] = 'unavailable'
    try: result['runtime'] = safe_state(send({'op':'status'}))
    except (OSError, RuntimeError, ValueError): result['runtime'] = 'stopped'
    result['rimeDataAvailable'] = Path(os.environ.get('HP_OS_TOUCH_RIME_DATA','/nonexistent')).is_dir()
    result['rotationSensorCommand'] = bool(shutil.which('monitor-sensor'))
    return result


def gesture_config(cfg, patched=False):
    """KDL for the pinned niri-tablet patch; stock Niri receives no unknown nodes."""
    gestures = cfg.get('gestures', {})
    if not patched:
        return '// Touchscreen gestures are unavailable in stock Niri.\n'
    if not cfg.get('enable') or not gestures.get('enable', True) or gestures.get('backend') == 'stock':
        return 'gestures { touchscreen-swipe { off; }; }\n'
    lines = ['gestures {', '    touchscreen-swipe {', '        fingers 3',
             '        horizontal-swipe "move-view"', '        tap-more { toggle-overview; }',
             '        swipe-more-up { fullscreen-window; }', '    }',
             '    touchscreen-edge-swipe {', '        left { focus-column-left; }',
             '        right { focus-column-right; }']
    if enabled(cfg) and gestures.get('keyboardEdge', False):
        lines.append('        bottom { spawn "touch-support" "toggle"; }')
    command = gestures.get('controlCenterCommand', [])
    if gestures.get('controlsEdge', False) and command:
        if not isinstance(command, list) or not all(isinstance(s, str) for s in command):
            raise ValueError('controlCenterCommand must be an argument list')
        lines.append('        top { spawn ' + ' '.join(json.dumps(s) for s in command) + '; }')
    lines += ['    }', '}']
    return '\n'.join(lines)+'\n'


def update_gesture_file(cfg):
    """Replace only the generated touch fragment after validation; never edit main KDL."""
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
    root = Path(os.environ.get('INIR_NIRI_CONFIG_DIR', str(config_home/'hp-os/niri')))
    target = root/'config.d/60-touch.kdl'
    if not target.exists(): return False
    if target.is_symlink() or not target.is_file(): raise RuntimeError('Unsafe generated config target')
    fd, name = tempfile.mkstemp(prefix='.60-touch-', suffix='.kdl', dir=target.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as f:
            f.write(gesture_config(cfg,os.environ.get('HP_OS_TOUCH_PATCHED')=='1'))
        result=subprocess.run([executable('HP_OS_TOUCH_NIRI','niri'),'validate','--config',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
        if result.returncode != 0: raise RuntimeError('Generated gesture configuration did not validate')
        os.replace(name,target)
        return True
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    sub = parser.add_subparsers(dest='command', required=True)
    for cmd in ('run','session-start','rotation-run','doctor','show','hide','toggle','status','settings'): sub.add_parser(cmd)
    configure = sub.add_parser('configure')
    configure.add_argument('key', choices=('keyboard.mode','keyboard.backend','keyboard.allowFallback','gestures.enable'))
    configure.add_argument('json_value')
    sub.add_parser('gestures').add_argument('--patched', action='store_true')
    sub.add_parser('rotation-posture').add_argument('value', choices=('auto','laptop','tablet'))
    sub.add_parser('posture').add_argument('value', choices=('auto','laptop','tablet'))
    sub.add_parser('backend').add_argument('value', type=canonical_backend, choices=BACKENDS)
    sub.add_parser('mode').add_argument('value', choices=MODES)
    a = parser.parse_args(argv)
    try:
        cfg = load_config(a.config)
        if a.command == 'gestures': print(gesture_config(cfg, a.patched), end=''); return 0
        if a.command == 'rotation-run':
            return asyncio.run(RotationController(cfg).run()) if cfg['enable'] and cfg['rotation']['mode'] != 'off' else 0
        if a.command == 'rotation-posture':
            print(json.dumps(send({'op':'posture','value':a.value}, rotation=True))); return 0
        if a.command == 'configure':
            value = json.loads(a.json_value); key = a.key.split('.')[-1]
            if key == 'mode' and (value not in MODES or (cfg.get('_policyOff') and value != 'off')): raise ValueError('Declarative off policy')
            if key == 'backend': value = canonical_backend(value)
            if key == 'backend' and value not in BACKENDS: raise ValueError('Invalid backend')
            if key in ('allowFallback','enable') and not isinstance(value, bool): raise ValueError('Expected boolean')
            p = preferences_path(); p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            saved = json.loads(p.read_text()) if p.is_file() else {}
            updated = False
            if a.key == 'gestures.enable':
                cfg['gestures']['enable'] = value
                updated = update_gesture_file(cfg)
                saved[a.key] = value
            else: saved[key] = value
            atomic_json(p, saved)
            with contextlib.suppress(OSError, RuntimeError): send({'op':'config-view' if a.key == 'gestures.enable' else 'reload'})
            print(json.dumps({'saved':a.key, 'restartSessionIfStopped':not updated})); return 0
        if a.command in ('run','session-start'): return asyncio.run(Controller(cfg).run()) if enabled(cfg) else 0
        if a.command == 'doctor': print(json.dumps(doctor(cfg),indent=2)); return 0
        if a.command == 'settings':
            command = os.environ.get('HP_OS_TOUCH_SETTINGS_COMMAND')
            if not command: print('Configure programs.hp-os.touchSupport or ~/.config/hp-os/touch.json'); return 0
            return subprocess.call([command])
        if not enabled(cfg) and a.command not in ('status',):
            print('On-screen keyboard is disabled by configuration.', file=sys.stderr); return 2
        print(json.dumps(send({'op':a.command, **({'value':a.value} if hasattr(a,'value') else {})})))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
        # Never interpolate untrusted input or protocol payloads into diagnostics.
        print('Touch support unavailable. Run touch-support doctor.', file=sys.stderr); return 1

if __name__ == '__main__': sys.exit(main())
