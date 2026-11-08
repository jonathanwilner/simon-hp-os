#!/usr/bin/env python3
"""Select a configured private Mosh endpoint using an actual UDP session."""
import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import secrets
import select
import shlex
import signal
import sys
import struct
import termios
import time


def command(endpoint, host, probe=False):
    ssh = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'ConnectionAttempts=1',
           '-o', 'ProxyCommand=none', '-o', 'ProxyJump=none',
           '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlias=' + host['hostKeyAlias']]
    if probe:
        ssh += ['-o', 'BatchMode=yes']
    target = (host.get('user', '') + '@' if host.get('user') else '') + endpoint
    return [os.environ.get('FLEET_MOSH_BINARY', 'mosh'), '--experimental-remote-ip=local', '-4', '-p', '60000:60019',
            '--ssh=' + shlex.join(ssh),
            '--server=env MOSH_SERVER_NETWORK_TMOUT=' + ('15' if probe else '604800') + ' mosh-server',
            target]


def probe(argv, timeout=12):
    marker = 'FLEET_MOSH_' + secrets.token_hex(12)
    # A controlling PTY keeps SSH and Mosh in their foreground process group.
    pid, fd = pty.fork()
    if pid == 0:
        fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 160, 0, 0))
        os.environ['TERM'] = 'xterm-256color'
        os.execvp(argv[0], argv + ['--', 'sh', '-c', 'printf "%s\\n" ' + marker + '; sleep 1'])
    data = b''
    status = None
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([fd], [], [], min(.2, max(0, deadline - time.monotonic())))
            if readable:
                try:
                    chunk = os.read(fd, 65536)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    chunk = b''
                if chunk:
                    data = (data + chunk)[-262144:]
                else:
                    _, status = os.waitpid(pid, 0)
                    break
            done, result = os.waitpid(pid, os.WNOHANG)
            if done:
                status = result
                break
    finally:
        if status is None:
            try:
                os.killpg(pid, signal.SIGTERM)
                time.sleep(.1)
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        os.close(fd)
    # Never print captured terminal output: it can include connection secrets.
    return status is not None and os.waitstatus_to_exitcode(status) == 0 and marker.encode() in data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', choices=['auto', 'private', 'tailscale'], default='auto')
    parser.add_argument('--check', action='store_true', help='test UDP and exit without opening a shell')
    parser.add_argument('--config', default=os.environ.get('FLEET_MOSH_CONFIG', str(Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'fleet-mosh/hosts.json')))
    parser.add_argument('host')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        hosts = json.loads(Path(args.config).read_text())
        host = hosts[args.host]
        paths = ['private', 'tailscale'] if args.path == 'auto' else [args.path]
        for path in paths:
            endpoint = host.get(path)
            if not endpoint:
                continue
            print(f'fleet-mosh: checking {path} ({endpoint})', file=sys.stderr)
            if probe(command(endpoint, host, probe=True)):
                print(f'fleet-mosh: UDP verified via {path} ({endpoint})', file=sys.stderr)
                if args.check:
                    return 0
                remote_command = args.command
                if remote_command[:1] == ['--']:
                    remote_command = remote_command[1:]
                argv = command(endpoint, host) + (['--'] + remote_command if remote_command else [])
                os.execvp(argv[0], argv)
            print(f'fleet-mosh: {path} probe failed; check DNS, SSH trust and UDP routing', file=sys.stderr)
        print('fleet-mosh: no verified path; use your existing SSH recovery connection', file=sys.stderr)
        return 1
    except (OSError, KeyError, ValueError) as exc:
        print(f'fleet-mosh: configuration or execution error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
