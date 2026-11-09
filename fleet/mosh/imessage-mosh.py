#!/usr/bin/env python3
"""Open a dedicated iMessage tmux session with native images over Mosh."""
import argparse
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import time


def descendants(parent):
    result = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / 'status').read_text()
            match = re.search(r'^PPid:\s+(\d+)', status, re.M)
            if match and int(match[1]) == parent:
                result.append(int(entry.name))
                result.extend(descendants(int(entry.name)))
        except (OSError, ValueError):
            pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host')
    parser.add_argument('--session', default='imessage-hd-' + secrets.token_hex(4))
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+', args.session) or args.host.startswith('-'):
        parser.error('invalid session or host')
    tty = os.ttyname(sys.stdin.fileno())
    ssh = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5', args.host]
    # Fail before opening the remote UI if the helper is not installed.
    subprocess.run(ssh + ['command -v ost-kitty-bridge >/dev/null'], check=True)
    print('Native image session:', args.session, flush=True)
    print('Resume with: ost-imessage-mosh', shlex.quote(args.host), '--session', args.session, flush=True)
    connection = subprocess.Popen(['mosh', args.host, '--', 'tmux', 'new-session', '-A', '-s', args.session, 'exec "$HOME/.local/bin/teams-cli" imessage'])
    bridge = None
    try:
        deadline = time.monotonic() + 30
        while connection.poll() is None and time.monotonic() < deadline:
            mosh_pid = None
            for pid in [connection.pid] + descendants(connection.pid):
                try:
                    if b'mosh-client' in (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')[0]:
                        mosh_pid = pid
                        break
                except OSError:
                    pass
            if mosh_pid:
                remote = 'tmux list-clients -t ' + shlex.quote(args.session) + ' -F ' + shlex.quote('#{client_pid} #{pane_id}')
                result = subprocess.run(ssh + [remote], capture_output=True, text=True)
                lines = result.stdout.strip().splitlines()
                if result.returncode == 0 and len(lines) == 1 and re.fullmatch(r'[0-9]+ %[0-9]+', lines[0]):
                    client_pid, pane = lines[0].split()
                    bridge = subprocess.Popen(['ost-kitty-bridge', '--host', args.host, '--pane', pane,
                                               '--client-pid', client_pid, '--tty', tty, '--mosh-pid', str(mosh_pid)])
                    break
            time.sleep(1)
        if bridge is None and connection.poll() is None:
            print('Native image helper unavailable; iMessage keeps its Mosh fallback.', file=sys.stderr)
        return connection.wait()
    finally:
        if bridge is not None:
            bridge.terminate()
            try:
                bridge.wait(timeout=8)
            except subprocess.TimeoutExpired:
                bridge.kill()


if __name__ == '__main__':
    sys.exit(main())
