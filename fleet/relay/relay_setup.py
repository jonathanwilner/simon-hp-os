#!/usr/bin/env python3
"""Relay desktop enrollment. Credentials remain in private runtime files."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import urllib.request
from urllib.parse import parse_qs, urlsplit
from relay_agent import NoRedirect, validate_config

ORIGIN = 'https://clipboard-api.thewilners.com'


def private_write(path, text):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.relay-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def api(origin, path, body, token=None):
    headers = {'Content-Type': 'application/json', 'User-Agent': 'Relay/0.2'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(origin + '/api/v1' + path, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        return json.load(response)


def invite_code(link):
    parsed = urlsplit(link.strip())
    if (parsed.scheme, parsed.netloc, parsed.path) != ('https', 'clipboard-api.thewilners.com', '/'):
        raise ValueError('Use a Relay setup link from clipboard-api.thewilners.com.')
    code = parse_qs(parsed.fragment).get('invite', [''])[0]
    if not code or len(code) > 256:
        raise ValueError('The setup link does not contain an invitation.')
    return code


def enroll(path, link=None, request=api):
    """Never replace an enrolled device, even when two launchers race."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lockfd = os.open(path.parent / '.setup.lock', os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lockfd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            config = json.loads(path.read_text())
            validate_config(config)
            return config
        body = {'device_name': socket.gethostname(), 'platform': 'linux'}
        endpoint = '/enroll'
        if link:
            body['code'] = invite_code(link)
            endpoint = '/join'
        result = request(ORIGIN, endpoint, body)
        for key in ('device_id', 'token', 'management_token'):
            if not isinstance(result.get(key), str) or not result[key]:
                raise ValueError('The enrollment response is incomplete.')
        token_file = path.parent / 'device-token'
        manager_file = path.parent / 'management-token'
        private_write(token_file, result['token'])
        private_write(manager_file, result['management_token'])
        config = {'url': ORIGIN, 'device_id': result['device_id'], 'device_name': body['device_name'],
                  'token_file': str(token_file), 'management_token_file': str(manager_file),
                  'enabled': True, 'auto_receive': False}
        private_write(path, json.dumps(config, indent=2) + '\n')
        return config


def start_service():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
    # HP-OS may use a private session bus. The service still belongs to the user manager.
    values = []
    for name in ('WAYLAND_DISPLAY', 'DISPLAY', 'XDG_CURRENT_DESKTOP'):
        value = os.environ.get(name)
        if value is not None:
            values.append(name + '="' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '') + '"')
    private_write(runtime / 'relay-clipboard.env', '\n'.join(values) + '\n')
    env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'bus'))
    subprocess.run(['systemctl', '--user', 'restart', 'relay-clipboard.service'], env=env, check=True, timeout=20)


def dialog(*args):
    process = subprocess.run(['zenity', *args], capture_output=True, text=True)
    return process.stdout.strip() if process.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--history', action='store_true', help='Open history without changing sync state')
    parser.add_argument('--join', help='Join an existing account using its setup URL')
    args = parser.parse_args()
    path = Path(args.config).expanduser()
    try:
        link = args.join
        if not path.exists() and not link:
            choice = dialog('--list', '--title=Relay', '--text=Sync future clipboard copies. Your current clipboard stays private. Create an account, or join your existing account.', '--column=Setup', 'Create my Relay account', 'Join an existing account', '--width=520', '--height=260')
            if choice is None:
                return
            if choice.startswith('Join'):
                link = dialog('--entry', '--title=Join Relay', '--text=Paste the setup URL from your other device:')
                if not link:
                    return
        config = enroll(path, link)
        if not config.get('enabled'):
            dialog('--info', '--title=Relay', '--text=Relay is disabled in your existing configuration. Your enrollment has been preserved.')
            return
        if not args.history:
            start_service()
        manager_file = config.get('management_token_file') or config.get('token_file')
        if manager_file:
            manager = Path(manager_file).expanduser()
            if manager.stat().st_mode & 0o077:
                raise ValueError('Management token must have private permissions (0600).')
            url = config['url'].rstrip('/') + '/#account=' + manager.read_text().strip()
        else:
            url = config['url'].rstrip('/') + '/'
        subprocess.run(['xdg-open', url], check=True, timeout=20)
    except (OSError, ValueError, subprocess.SubprocessError):
        dialog('--error', '--title=Relay setup', '--text=Relay could not finish setup. Check your connection and private configuration, then open Relay again. Existing enrollment is preserved.')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
