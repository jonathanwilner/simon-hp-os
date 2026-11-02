#!/usr/bin/env python3
"""Real Qt text-input acceptance. Requires a disposable focused compositor.
Usage: XDG_RUNTIME_DIR=... WAYLAND_DISPLAY=wayland-N python test_wayland.py PACKAGE
Uses synthetic fixtures only. Never run on the user's live compositor.
"""
import json, os, pathlib, socket, subprocess, sys, tempfile, time
package=pathlib.Path(sys.argv[1]); root=pathlib.Path(tempfile.mkdtemp(prefix='hp-os-acceptance-')); os.chmod(root,0o700)
env=dict(os.environ,QT_QPA_PLATFORM='wayland',QT_IM_MODULE='wayland',XDG_DATA_HOME=str(root/'data'))
for key in ('QT_PLUGIN_PATH','QML2_IMPORT_PATH','QT_QPA_PLATFORMTHEME'): env.pop(key,None)
env['QT_STYLE_OVERRIDE']='Fusion'
processes=[]
def connect(path):
    end=time.monotonic()+20
    while time.monotonic()<end:
        try:
            s=socket.socket(socket.AF_UNIX);s.connect(str(path));s.settimeout(20);return s,s.makefile('rb')
        except (FileNotFoundError,ConnectionRefusedError):time.sleep(.1)
    raise RuntimeError('fixture socket did not start')
def send(s,**obj):s.sendall(json.dumps(obj).encode()+b'\n')
def read(f):return json.loads(f.readline())
def state_until(f,predicate):
    end=time.monotonic()+20
    while time.monotonic()<end:
        x=read(f)
        if x.get('type')=='error':raise AssertionError(x['code'])
        if predicate(x):return x
    raise AssertionError('state timeout')
try:
    processes.append(subprocess.Popen([str(package/'bin/hp-os-input-backend'),'--socket',str(root/'input.sock')],env=env))
    bs,bf=connect(root/'input.sock');read(bf)
    processes.append(subprocess.Popen([str(package/'libexec/hp-os-input-test-client'),str(root/'client.sock')],env=env))
    cs,cf=connect(root/'client.sock')
    state_until(bf,lambda x:x.get('active') and not x.get('secure'))
    def check(field,value):
        time.sleep(.2);send(cs,op='status');assert read(cf)[field]==value,field
    send(bs,op='text',text='Hello 世界🙂');check('normal','Hello 世界🙂')
    send(bs,op='key',key='BackSpace');check('normal','Hello 世界')
    send(cs,op='clear');read(cf)
    send(bs,op='text',text='keyboa');x=state_until(bf,lambda x:'keyboard' in x.get('candidates',[]))
    send(bs,op='candidate',index=x['candidates'].index('keyboard'));check('normal','keyboard')
    send(cs,op='clear');read(cf)
    send(bs,op='language',language='zh_CN');state_until(bf,lambda x:x.get('rimeReady'))
    send(bs,op='text',text='nihao');x=state_until(bf,lambda x:'你好' in x.get('candidates',[]))
    send(bs,op='manual',enabled=False);same=read(bf);assert same['preedit']==x['preedit'] and same['candidates']==x['candidates']
    send(bs,op='candidate',index=x['candidates'].index('你好'));check('normal','你好')
    send(bs,op='text',text='ni');state_until(bf,lambda x:bool(x.get('preedit')))
    send(cs,op='password');read(cf)
    x=state_until(bf,lambda x:x.get('secure'));assert not x['candidates'] and not x['preedit']
    send(bs,op='text',text='secret123');check('password','secret123')
    send(cs,op='normal');read(cf);x=state_until(bf,lambda x:x.get('active') and not x.get('secure'));assert not x['preedit']
    send(bs,op='language',language='en_US');state_until(bf,lambda x:x.get('language')=='en_US')
    send(bs,op='gesture',keys=list('hello'),points=[]);x=state_until(bf,lambda x:'hello' in x.get('candidates',[]))
    send(bs,op='candidate',index=x['candidates'].index('hello'));check('normal','你好hello')
    send(cs,op='raw');read(cf);state_until(bf,lambda x:not x.get('active'))
    send(bs,op='manual',enabled=True);state_until(bf,lambda x:x.get('manual'))
    send(bs,op='text',text='Ab🙂');check('raw','Ab🙂')
    print('PASS: raw Unicode/emoji, dictionary gesture decode, Qt Unicode/emoji, BackSpace, real Rime candidate commit, password bypass, focus reset')
finally:
    for p in reversed(processes):p.terminate()
    for p in processes:
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()
