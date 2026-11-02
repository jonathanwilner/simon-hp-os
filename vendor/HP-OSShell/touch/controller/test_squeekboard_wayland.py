"""Opt-in compositor test. Importing this file does not launch anything."""
import asyncio, importlib.util, os, tempfile, json
from pathlib import Path
spec=importlib.util.spec_from_file_location('touch_support',Path(__file__).with_name('touch_support.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
async def test(args):
    with tempfile.TemporaryDirectory(prefix='hp-os-squeek-runtime-') as directory:
        os.environ.update(XDG_RUNTIME_DIR=directory,WAYLAND_DISPLAY=args.isolated_display,HP_OS_TOUCH_SQUEEKBOARD=args.squeekboard)
        if args.backend: os.environ['HP_OS_TOUCH_BACKEND']=args.backend
        if args.qml: os.environ['HP_OS_TOUCH_QML']=args.qml
        cfg={'enable':True,'profile':'laptop','keyboard':{'mode':'manual','backend':'squeekboard','fallback':'squeekboard','allowFallback':True,'autoShowOnTextFocus':True},'rotation':{'mode':'off'}}
        c=t.Controller(cfg);run=asyncio.create_task(c.run())
        try:
            for _ in range(40):
                if (c.root/'control.sock').exists():break
                await asyncio.sleep(.05)
            assert c.backend is None,'manual startup spawned keyboard'
            await c.command({'op':'show'})
            assert c.backend and c.backend.returncode is None,'fallback exited'
            for _ in range(40):
                if await c.squeek_is_visible():break
                await asyncio.sleep(.05)
            assert await c.squeek_is_visible(),'Squeekboard did not report Visible=true'
            await c.command({'op':'hide'})
            assert c.backend is None,'hide retained fallback'
            await c.reconcile()
            assert c.backend is None,'focus reconciliation restarted hidden keyboard'
            if args.backend and args.qml:
                await c.command({'op':'backend','value':'hp-os-qml'})
                await c.command({'op':'show'})
                await asyncio.sleep(.4)
                assert c.state['backend']=='hp-os-qml' and c.qml and c.qml.returncode is None, 'custom startup failed'
                old_backend,old_qml=c.backend,c.qml
                await c.command({'op':'backend','value':'squeekboard'})
                assert old_backend.returncode is not None and old_qml.returncode is not None,'custom children survived switch'
                assert c.state['backend']=='squeekboard' and await c.squeek_is_visible(),'fallback switch failed'
                old_fallback=c.backend
                await c.command({'op':'backend','value':'hp-os-qml'})
                await asyncio.sleep(.4)
                assert old_fallback.returncode is not None,'fallback survived switch'
                assert c.state['backend']=='hp-os-qml' and c.qml.returncode is None,'custom return failed'
                print(json.dumps({'backendSwitch':'hp-os -> squeekboard -> hp-os','previousChildren':'terminated before next backend'}))
            print(json.dumps({'manualStartup':'no-keyboard','manualShow':'DBus Visible=true','hide':'child-terminated','hiddenReconcile':'no-keyboard'}))
        finally:
            c.stop.set();await run
if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Run only against a disposable compositor under dbus-run-session. Claims its input-method seat.')
    parser.add_argument('--isolated-display',required=True,help='Absolute path of disposable Wayland socket; never the active desktop')
    parser.add_argument('--squeekboard',required=True)
    parser.add_argument('--backend')
    parser.add_argument('--qml',help='Executable wrapper launching actual HP-OS Quickshell UI; enables round-trip switch test with --backend')
    args=parser.parse_args()
    if not Path(args.isolated_display).is_absolute() or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        parser.error('Use an absolute disposable display socket and dbus-run-session')
    current=os.environ.get('WAYLAND_DISPLAY','')
    active=Path(current) if current.startswith('/') else Path(os.environ.get('XDG_RUNTIME_DIR','/nonexistent'))/current
    if current and Path(args.isolated_display)==active:
        parser.error('Refusing the active WAYLAND_DISPLAY; select a disposable compositor')
    if '/run/user/' in os.environ.get('DBUS_SESSION_BUS_ADDRESS',''):
        parser.error('Use a fresh private dbus-run-session, not the desktop session bus')
    asyncio.run(asyncio.wait_for(test(args),90))
