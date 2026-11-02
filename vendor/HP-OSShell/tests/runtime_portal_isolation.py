#!/usr/bin/env python3
"""Run PACKAGE/bin/hp-os in disposable Xvfb, runtime directory and bus.

Requires Xvfb and the installed graphics libraries. This checks portal
activation and cleanup, not interactive file selection or stream delivery.
"""
import os,sys,subprocess,time,tempfile,pathlib,signal,json
root=pathlib.Path(tempfile.mkdtemp(prefix='hp-portal-isolated-')); (root/'runtime').mkdir(mode=0o700); print('EVIDENCE',root,flush=True)
def cmd(args,env=None):
 env = env or dict(os.environ, XDG_RUNTIME_DIR="/run/user/"+str(os.getuid()))
 p=subprocess.run(args,env=env,text=True,capture_output=True,timeout=15);return {'exit':p.returncode,'out':p.stdout.strip(),'err':p.stderr.strip()}
before=cmd(['systemctl','--user','show-environment'])['out']; original=os.environ.copy(); processes=[]; result={}
try:
 r,w=os.pipe(); xvlog=open(root/'xvfb.log','w'); xv=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1280x800x24','-nolisten','tcp'],pass_fds=[w],stdout=xvlog,stderr=xvlog,start_new_session=True);processes.append(xv);os.close(w);display=os.read(r,20).decode().strip();os.close(r)
 env=original.copy()
 # The package or caller supplies graphics libraries; never borrow another session's environment.
 for k in ['WAYLAND_DISPLAY','WAYLAND_SOCKET','NIRI_SOCKET','DBUS_SESSION_BUS_ADDRESS','NOTIFY_SOCKET','HP_OS_RUNTIME','HP_OS_PACKAGING'] :env.pop(k,None)
 env.update(XDG_RUNTIME_DIR=str(root/'runtime'),DISPLAY=':'+display,XDG_CONFIG_HOME=str(root/'config'),XDG_STATE_HOME=str(root/'state'),XDG_CACHE_HOME=str(root/'cache'),XDG_DATA_HOME=str(root/'data'),INIR_CONFIG_DIR=str(root/'config/hp-os'),INIR_STATE_DIR=str(root/'state/hp-os'),INIR_CACHE_DIR=str(root/'cache/hp-os'),INIR_NIRI_CONFIG_DIR=str(root/'config/hp-os/niri'),INIR_SAFE_PREVIEW='1',LIBGL_ALWAYS_SOFTWARE='1',NIRI_DISABLE_SYSTEM_MANAGER_NOTIFY='1')
 log=open(root/'session.log','w'); proc=subprocess.Popen([sys.argv[1]+'/bin/hp-os','session'],env=env,stdout=log,stderr=log,start_new_session=True);processes.append(proc)
 private=None
 for i in range(45):
  time.sleep(1)
  for entry in pathlib.Path('/proc').glob('[0-9]*/environ'):
   try:
    raw=entry.read_bytes().split(b'\0'); pe=dict(x.decode(errors='replace').split('=',1) for x in raw if b'=' in x)
    if pe.get('INIR_CONFIG_DIR')==env['INIR_CONFIG_DIR'] and pe.get('WAYLAND_DISPLAY') and pe.get('DBUS_SESSION_BUS_ADDRESS'):
     private=pe;break
   except (OSError,ValueError):pass
  if private and i>=12:break
  if proc.poll() is not None:break
 result['session_alive']=proc.poll() is None
 if private:
  base=['gdbus','call','--session','--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus','--method','org.freedesktop.DBus.NameHasOwner']
  for name in ['org.freedesktop.Notifications','org.gnome.Mutter.ScreenCast','org.gnome.Mutter.DisplayConfig','org.gnome.Mutter.ServiceChannel']: result[name]=cmd(base+[name],private)
  result['service_channel_open']=cmd(['gdbus','call','--session','--dest','org.gnome.Mutter.ServiceChannel','--object-path','/org/gnome/Mutter/ServiceChannel','--method','org.gnome.Mutter.ServiceChannel.OpenWaylandServiceConnection','1'],private)
  result['document_mount']=cmd(['gdbus','call','--session','--dest','org.freedesktop.portal.Documents','--object-path','/org/freedesktop/portal/documents','--method','org.freedesktop.portal.Documents.GetMountPoint'],private)
  result['portal_introspection']=cmd(['gdbus','introspect','--session','--dest','org.freedesktop.portal.Desktop','--object-path','/org/freedesktop/portal/desktop'],private)
  result['network_read']=cmd(['gdbus','call','--system','--dest','org.freedesktop.NetworkManager','--object-path','/org/freedesktop/NetworkManager','--method','org.freedesktop.DBus.Properties.Get','org.freedesktop.NetworkManager','State'],private)
  result['upower_read']=cmd(['gdbus','call','--system','--dest','org.freedesktop.UPower','--object-path','/org/freedesktop/UPower','--method','org.freedesktop.UPower.EnumerateDevices'],private)
  result['private_bus']=private['DBUS_SESSION_BUS_ADDRESS']!=original.get('DBUS_SESSION_BUS_ADDRESS')
 else:result['private_env']='NOT FOUND'
finally:
 for p in reversed(processes):
  try:
   p.terminate()
   p.wait(timeout=8)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGKILL)
   p.wait()
  except ProcessLookupError:pass
 remaining=[]
 for entry in pathlib.Path('/proc').glob('[0-9]*/environ'):
  try:
   if ('INIR_CONFIG_DIR='+str(root/'config/hp-os')).encode() in entry.read_bytes():remaining.append(int(entry.parent.name))
  except OSError:pass
 result['owned_processes_after_logout']=remaining
 result['global_manager_environment_unchanged']=before==cmd(['systemctl','--user','show-environment'])['out']
 (root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
 print('ERROR_LINES',flush=True)
 if (root/'session.log').exists():
  for line in (root/'session.log').read_text(errors='replace').splitlines():
   if any(s in line.lower() for s in ['error','failed','warning']):print(line[:400])

sys.exit(0 if result.get("service_channel_open", {}).get("exit") == 0 and result.get("org.gnome.Mutter.ServiceChannel", {}).get("out") == "(true,)" and result.get("document_mount", {}).get("exit") == 0 and result.get("session_alive") and result.get("org.freedesktop.Notifications",{}).get("out")=="(true,)" and result.get("global_manager_environment_unchanged") and result.get("owned_processes_after_logout")==[] else 1)
