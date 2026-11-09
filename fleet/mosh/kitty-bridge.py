#!/usr/bin/env python3
"""Authenticated, app-specific image uploads beside an existing Mosh connection.

Mosh carries Kitty Unicode placeholders. SSH carries validated PNGs, and this
helper writes only generated Kitty commands to the originating local terminal.
"""
import argparse
import base64
import fcntl
import io
import json
import os
from pathlib import Path
import re
import select
import shlex
import signal
import stat
import subprocess
import sys
import time

MAX_MANIFEST = 64 * 1024 * 1024
MAX_IMAGE = 20 * 1024 * 1024


def pane_number(value):
    if not re.fullmatch(r'%?[0-9]+', value):
        raise argparse.ArgumentTypeError('pane must be a tmux numeric pane ID')
    return value.lstrip('%')


def serve(args):
    root = Path('/run/user') / str(os.getuid()) / 'ost-kitty-bridge'
    root.mkdir(mode=0o700, exist_ok=True)
    directory = root / ('pane-' + args.pane)
    directory.mkdir(mode=0o700, exist_ok=True)
    for path in (root, directory):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('bridge runtime directory must be private and user-owned')
    lock = open(directory / 'helper.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    heartbeat = directory / 'heartbeat.json'
    manifest = directory / 'manifest.json'
    last = None
    try:
        while True:
            # The application checks this PID against the active tmux window.
            temporary = directory / 'heartbeat.tmp'
            temporary.write_text(json.dumps({'client_pid': args.client_pid}))
            temporary.chmod(0o600)
            temporary.replace(heartbeat)
            try:
                with open(manifest, 'rb') as source:
                    body = source.read(MAX_MANIFEST + 1)
                if len(body) > MAX_MANIFEST:
                    raise ValueError('manifest exceeds 64 MiB')
                value = json.loads(body)
                compact = json.dumps(value, separators=(',', ':')).encode()
                if compact != last:
                    sys.stdout.buffer.write(compact + b'\n')
                    sys.stdout.buffer.flush()
                    last = compact
            except FileNotFoundError:
                pass
            # SSH closes stdin on disconnect. Never leave a live heartbeat then.
            if select.select([sys.stdin.buffer], [], [], 2)[0]:
                if not os.read(sys.stdin.fileno(), 1):
                    break
    finally:
        heartbeat.unlink(missing_ok=True)


def validate_manifest(value):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 16_777_216
    if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('images'), list) or len(value['images']) > 24:
        raise ValueError('invalid manifest version or image count')
    result = {}
    for item in value['images']:
        if not isinstance(item, dict):
            raise ValueError('invalid image record')
        image_id, cols, rows = (item.get(key) for key in ('id', 'columns', 'rows'))
        if any(type(v) is not int for v in (image_id, cols, rows)) or not (1 <= image_id <= 0xffffff and 1 <= cols <= 64 and 1 <= rows <= 63):
            raise ValueError('invalid image ID or placement size')
        if image_id in result:
            raise ValueError('duplicate image ID')
        encoded = item.get('png_base64')
        if not isinstance(encoded, str) or len(encoded) > (MAX_IMAGE + 2) // 3 * 4:
            raise ValueError('PNG exceeds 20 MiB')
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_IMAGE or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('invalid PNG')
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.width * image.height > 16_777_216:
                raise ValueError('PNG geometry exceeds limit')
            image.verify()
        result[image_id] = (cols, rows, encoded)
    return result


def upload(tty, image_id, value):
    cols, rows, encoded = value
    chunks = [encoded[i:i + 4096] for i in range(0, len(encoded), 4096)]
    for index, chunk in enumerate(chunks):
        header = f'a=T,f=100,i={image_id},U=1,c={cols},r={rows},q=2,' if index == 0 else 'q=2,'
        tty.write(f'\033_G{header}m={int(index + 1 < len(chunks))};{chunk}\033\\'.encode('ascii'))


def remove(tty, ids):
    for image_id in ids:
        tty.write(f'\033_Ga=d,d=I,i={image_id},q=2\033\\'.encode('ascii'))


def client(args):
    tty_path = Path(args.tty)
    info = tty_path.stat()
    if not stat.S_ISCHR(info.st_mode) or info.st_uid != os.getuid() or not re.fullmatch(r'/dev/pts/[0-9]+', str(tty_path)):
        raise ValueError('TTY must be your local /dev/pts/N')
    process = Path('/proc') / str(args.mosh_pid)
    if process.stat().st_uid != os.getuid() or os.path.realpath(process / 'fd/0') != str(tty_path):
        raise ValueError('Mosh PID does not own this terminal')
    if 'mosh-client' not in (process / 'cmdline').read_bytes().split(b'\0')[0].decode():
        raise ValueError('PID is not a Mosh client')
    remote = shlex.join([args.remote_helper, '--serve', '--pane', args.pane, '--client-pid', str(args.client_pid)])
    command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2', args.host, remote]
    with open(tty_path, 'wb', buffering=0) as tty:
        uploaded = {}
        owned = set()
        connection = None
        try:
            while process.exists():
                connection = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                # Rehydrate after every SSH reconnection, even for identical IDs.
                uploaded = {}
                generation = None
                pending = bytearray()
                while process.exists() and connection.poll() is None:
                    if not select.select([connection.stdout], [], [], 1)[0]:
                        continue
                    block = os.read(connection.stdout.fileno(), 65536)
                    if not block:
                        break
                    pending.extend(block)
                    if len(pending) > MAX_MANIFEST:
                        raise ValueError('remote frame exceeds 64 MiB')
                    while b'\n' in pending:
                        line, _, remainder = pending.partition(b'\n')
                        pending = bytearray(remainder)
                        value = json.loads(line)
                        images = validate_manifest(value)
                        if value.get('generation') != generation:
                            remove(tty, uploaded)
                            uploaded = {}
                            generation = value.get('generation')
                        remove(tty, uploaded.keys() - images.keys())
                        for image_id, value in images.items():
                            if uploaded.get(image_id) != value:
                                upload(tty, image_id, value)
                                owned.add(image_id)
                        uploaded = images
                connection.stdin.close()
                connection.terminate()
                connection.wait(timeout=5)
                connection = None
                if process.exists():
                    time.sleep(2)
        finally:
            if connection is not None:
                connection.stdin.close()
                connection.terminate()
                try:
                    connection.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    connection.kill()
            remove(tty, owned)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--pane', required=True, type=pane_number)
    parser.add_argument('--client-pid', required=True, type=int)
    parser.add_argument('--host')
    parser.add_argument('--tty')
    parser.add_argument('--mosh-pid', type=int)
    parser.add_argument('--remote-helper', default='ost-kitty-bridge')
    args = parser.parse_args()
    if args.client_pid <= 0 or (not args.serve and not all((args.host, args.tty, args.mosh_pid))):
        parser.error('client mode requires --host, --tty and --mosh-pid')
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    os.umask(0o077)
    try:
        serve(args) if args.serve else client(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'ost-kitty-bridge: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
