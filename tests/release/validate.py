#!/usr/bin/env python3
"""Evaluate complete fleet wiring and build every changed exported derivation."""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
def run(*args, **kw):
    return subprocess.check_output(args, text=True, **kw)
def evaluate(source, system):
    expression = 'import '+str(ROOT/'tests/release/evaluate.nix')+' { source = '+json.dumps(str(source))+'; system = '+json.dumps(system)+'; }'
    return json.loads(run('nix','eval','--impure','--json','--expr',expression))
def launcher_test(text):
    with tempfile.TemporaryDirectory() as tmp:
        p=pathlib.Path(tmp)
        stub=p/'systemd-run'
        stub.write_text('#!'+shutil.which('bash')+'\n[[ " $* " == *" --scope "* ]] || exit 23\nwhile [[ "$1" != -- ]]; do shift; done\nshift\nexec "$@"\n')
        stub.chmod(0o755)
        script=p/'launch'
        text=re.sub(r'/nix/store/[^ /]+/bin/systemd-run',str(stub),text)
        text=re.sub(r'/nix/store/[^ /]+/bin/date', shutil.which('date'),text)
        text=re.sub(r'^#!.*', '#!'+shutil.which('bash'),text,count=1)
        script.write_text(text); script.chmod(0o755)
        env=dict(os.environ,WAYLAND_DISPLAY='wayland-ci',DISPLAY=':42')
        command=['bash','-c','printf "%s:%s" "$WAYLAND_DISPLAY" "$DISPLAY"']
        assert run(str(script),*command,env=env)=='wayland-ci::42'
        env['HP_OS_OWNED_SESSION']='1'
        stub.write_text('#!'+shutil.which('bash')+'\nexit 99\n')
        assert run(str(script),*command,env=env)=='wayland-ci::42'
def main():
    system=sys.argv[1]
    if system not in ('x86_64-linux','aarch64-linux'): raise ValueError('Unsupported system')
    current=evaluate(ROOT,system)
    launcher_test(current['launcher'])
    baseline={}
    stable=run('git','ls-remote','origin','refs/heads/fleet-stable').strip()
    if stable:
        revision=stable.split()[0]
        subprocess.run(['git','fetch','origin',revision],check=True)
        with tempfile.TemporaryDirectory() as tmp:
            checkout=pathlib.Path(tmp)/'baseline'
            subprocess.run(['git','worktree','add','--detach',str(checkout),revision],check=True)
            try: baseline=evaluate(checkout,system)
            finally: subprocess.run(['git','worktree','remove','--force',str(checkout)],check=True)
    changed=[name for name,drv in current['packages'].items() if baseline.get('packages',{}).get(name)!=drv]
    changed_home = {name: drv for name, drv in current['homePackages'].items() if baseline.get('homePackages',{}).get(name) != drv}
    exported_drvs = {current['packages'][name] for name in changed}
    home_drvs = sorted(set(changed_home.values()) - exported_drvs)
    print(json.dumps({'system':system,'changedPackages':changed,'changedHomePackages':list(changed_home),'baseline':stable},indent=2),flush=True)
    targets=[f'.#packages.{system}.{name}' for name in changed]
    targets += [drv+'^*' for drv in home_drvs]
    targets += [f'.#checks.{system}.{name}' for name in current['checks']]
    if targets: subprocess.run(['nix','build','--no-link',*targets],check=True)
    (pathlib.Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / ('fleet-validation-'+system+'.json')).write_text(json.dumps({'system':system,'revision':run('git','rev-parse','HEAD').strip(),'changedPackages':changed,'changedHomePackages':list(changed_home),'launcher':'passed','evaluation':'passed','build':'passed'},indent=2))
if __name__=='__main__': main()
