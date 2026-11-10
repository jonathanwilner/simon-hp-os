#!/usr/bin/env python3
"""Control only the caller's HP-OS shell; refresh owned shells after upgrades."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time


def discover(proc=Path('/proc'), uid=None):
    """Read live process identity, never infer ownership from a package path alone."""
    uid = os.getuid() if uid is None else uid
    found = []
    for path in proc.iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid != uid:
                continue
            env = dict(item.split('=', 1) for item in path.joinpath('environ').read_bytes().decode().split('\0') if '=' in item)
            args = path.joinpath('cmdline').read_bytes().decode().strip('\0').split('\0')
            if not args or Path(args[0]).name not in ('qs', 'quickshell', '.quickshell-wrapped'):
                continue
            runtime = args[args.index('-p') + 1] if '-p' in args else args[args.index('--path') + 1]
            # This marker is inherited by the shell from the HP-OS launcher.
            if env.get('INIR_RUNTIME_DIR') != runtime or not env.get('INIR_CONFIG_DIR', '').endswith('/hp-os'):
                continue
            start = path.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]
            found.append(dict(pid=int(path.name), runtime=runtime, env=env, args=args, start=start))
        except (OSError, ValueError, IndexError, UnicodeError):
            continue
    return found


def select(instances, env):
    for key in ('WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS'):
        if env.get(key):
            instances = [p for p in instances if p['env'].get(key) == env[key]]
    if len(instances) > 1:
        raise RuntimeError('Multiple HP-OS sessions match. Set WAYLAND_DISPLAY and DBUS_SESSION_BUS_ADDRESS.')
    return instances[0] if instances else None


def alive(instance):
    try:
        stat = Path(f"/proc/{instance['pid']}/stat").read_text().rsplit(')', 1)[1].split()
        return stat[0] != 'Z' and stat[19] == instance['start']
    except OSError:
        return False


def wait_for(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.1)
    return False


def launch_env(instance, runtime):
    env = dict(instance['env'])
    # Keep the private bus, compositor socket and user configuration. The new
    # wrapper provides its own Qt paths, tools and data directories.
    for key in ('QML2_IMPORT_PATH', 'QML_IMPORT_PATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'HP_OS_PACKAGING'):
        env.pop(key, None)
    env['HP_OS_RUNTIME'] = runtime
    for key in ('INIR_RUNTIME_DIR', 'INIR_SYSTEM_RUNTIME_DIR', 'INIR_FALLBACK_SYSTEM_RUNTIME_DIR'):
        env[key] = runtime
    return env


def notification_free(env):
    result = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus', '--object-path', '/org/freedesktop/DBus', '--method', 'org.freedesktop.DBus.NameHasOwner', 'org.freedesktop.Notifications'], env=env, capture_output=True, text=True, timeout=5)
    return result.returncode == 0 and 'false' in result.stdout


def refresh(instance, runtime, runner, force=False):
    if (instance['runtime'] == runtime and not force) or instance['env'].get('HP_OS_OWNED_SESSION') != '1':
        return
    if not Path(runtime, 'shell.qml').is_file():
        raise RuntimeError(f'Missing replacement runtime: {runtime}')
    lock = subprocess.run(['qs', 'ipc', '--pid', str(instance['pid']), 'call', 'lock', 'status'], env=instance['env'], capture_output=True, text=True, timeout=5)
    if lock.returncode != 0 or lock.stdout.strip() != 'unlocked':
        print(f"HP-OS refresh deferred for {instance['pid']}: lock is {lock.stdout.strip() or 'unknown'}")
        return
    # Fail before stopping anything if this host cannot verify its private bus.
    subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus', '--object-path', '/org/freedesktop/DBus', '--method', 'org.freedesktop.DBus.NameHasOwner', 'org.freedesktop.Notifications'], env=instance['env'], check=True, stdout=subprocess.DEVNULL, timeout=5)
    if not alive(instance):
        return
    subprocess.run(['qs', 'kill', '--pid', str(instance['pid'])], env=instance['env'], check=True, timeout=5)
    if not wait_for(lambda: not alive(instance)):
        raise RuntimeError(f"HP-OS shell {instance['pid']} did not stop")
    env = launch_env(instance, runtime)
    state = Path(env.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'hp-os'
    state.mkdir(parents=True, exist_ok=True)
    logpath = state / 'runtime-refresh.log'
    with logpath.open('ab') as log:
        if not wait_for(lambda: notification_free(env)):
            # A notification owner is still present. Preserve the safety guard;
            # never terminate a server belonging to another desktop.
            # Recovery observes the same notification guard. Leave the
            # compositor intact and record the recovery launch in the log.
            if wait_for(lambda: notification_free(instance['env'])):
                subprocess.Popen(instance['args'], env=instance['env'], stdout=log, stderr=log, start_new_session=True)
            raise RuntimeError(f'Private notification bus remained occupied; previous runtime restored when bus permitted. See {logpath}')
        child = subprocess.Popen([runner, 'run'], env=env, stdout=log, stderr=log, start_new_session=True)
        if wait_for(lambda: child.poll() is not None or subprocess.run(['qs', 'ipc', '--pid', str(child.pid), 'show'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2).returncode == 0):
            if child.poll() is None:
                print(f"HP-OS refreshed {instance['pid']} -> {child.pid}: {runtime}")
                return
        # The compositor and applications are still alive. Restore the exact
        # previous shell command if the replacement cannot start.
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        if wait_for(lambda: notification_free(instance['env'])):
            subprocess.Popen(instance['args'], env=instance['env'], stdout=log, stderr=log, start_new_session=True)
        raise RuntimeError(f'New HP-OS shell failed; previous runtime restored when bus permitted. See {logpath}')


def main():
    command, runtime, runner, *args = sys.argv[1:]
    instances = discover()
    if command in ('refresh', 'restart'):
        # Home Manager activation may have another desktop's environment. Scan
        # only explicitly owned HP-OS sessions and use each private environment.
        lockdir = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
        with (lockdir / 'hp-os-runtime-refresh.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            selected = discover() if command == 'refresh' else [select(discover(), os.environ)]
            for instance in selected:
                if instance:
                    refresh(instance, runtime, runner, force=command == 'restart')
        return
    instance = select(instances, os.environ)
    selection = ['--pid', str(instance['pid'])] if instance else ['-p', runtime]
    env = instance['env'] if instance else os.environ
    operation = {'ipc': ['ipc', *selection, 'call', *args], 'settings': ['ipc', *selection, 'call', 'settings', 'toggle'], 'stop': ['kill', *selection], 'logs': ['log', *selection, *args]}[command]
    os.execvpe('qs', ['qs', *operation], env)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f'HP-OS: {exc}', file=sys.stderr)
        sys.exit(1)
