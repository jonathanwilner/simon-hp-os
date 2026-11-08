#!/usr/bin/env python3
"""Validated, transactional local identity setup. No Apple login credentials."""
import argparse
import contextlib
import datetime as dt
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time

UPSTREAM = '@upstream@'
OMDROP = '@omdrop@/bin/omdrop'
HELPER = '@helper@'
sys.path.insert(0, UPSTREAM + '/bin')
FILES = ('certificate.pem', 'key.pem', 'validation_record.cms')
MAX_FILE = 65536

class SetupError(Exception):
    pass

def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise SetupError('Identity directory must be a real directory owned by this user.')
    path.chmod(0o700)

def read_private(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
                raise SetupError('Identity files must be regular files smaller than 64 KiB.')
            return stream.read(MAX_FILE + 1)
    except OSError:
        raise SetupError('Cannot read the required identity files. Select the folder containing all three files.') from None

def write_private(path, data):
    fd, tmp = tempfile.mkstemp(prefix='.identity-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def iso(timestamp):
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat().replace('+00:00', 'Z')

def validate(data):
    import identity
    import contacts
    problem = identity.check_apple(*(data[name] for name in FILES))
    if problem:
        raise SetupError('Apple identity validation failed: ' + problem + '.')
    record = contacts.verify_record(data[FILES[2]])
    if not record or not record.get('expires') or not math.isfinite(record['expires']):
        raise SetupError('The validation record has no usable expiration date.')
    result = subprocess.run(['openssl', 'x509', '-noout', '-enddate'],
                            input=data[FILES[0]], capture_output=True, timeout=15)
    try:
        certificate_end = dt.datetime.strptime(result.stdout.decode().strip().split('=', 1)[1],
                                               '%b %d %H:%M:%S %Y %Z').replace(tzinfo=dt.timezone.utc).timestamp()
    except (ValueError, IndexError):
        raise SetupError('Cannot read the Apple certificate expiration date.') from None
    expiry = min(certificate_end, record['expires'])
    if expiry <= time.time():
        raise SetupError('The Apple identity has expired. Import a renewed identity.')
    return {'certificate_expires': iso(certificate_end), 'record_expires': iso(record['expires']),
            'expires_epoch': expiry}

class Setup:
    def __init__(self, home=None):
        self.home = Path(home or Path.home())
        self.keys = self.home / '.omdrop/keys'
        self.config = Path(os.environ.get('XDG_CONFIG_HOME', self.home / '.config')) / 'omdrop'
        self.settings = self.config / 'settings'
        self.state = Path(os.environ.get('XDG_STATE_HOME', self.home / '.local/state')) / 'omdrop-identity'
        self.runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid()))) / 'omdrop'

    def settings_data(self):
        return self.settings.read_bytes() if self.settings.exists() else b''

    def source(self):
        values = dict(line.split('=', 1) for line in self.settings_data().decode().splitlines() if '=' in line)
        return values.get('identity_source', 'disk')

    def upstream_status(self):
        try:
            result = subprocess.run([OMDROP, 'status', '--json'], capture_output=True, timeout=15)
            if result.returncode: raise ValueError()
            value = json.loads(result.stdout)
            if not isinstance(value, dict) or not isinstance(value.get('receiving'), bool): raise ValueError()
            return value
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise SetupError('Cannot check AirDrop activity. Try again after OM Drop is available.') from None

    def active_source(self):
        try:
            lines = (self.runtime / 'window').read_text().splitlines()
            return dict(line.split('=', 1) for line in lines if '=' in line).get('source')
        except OSError:
            return None

    def status(self, force=False):
        value = dict(configured=False, valid=False, state='missing', message='Import an Apple identity to enable Apple Account recognition.',
                     certificate_expires=None, record_expires=None, days_remaining=None,
                     source=self.source(), active_source=self.active_source())
        present = [p for p in FILES if (self.keys / p).exists()]
        if not present: return value
        value['configured'] = len(present) == 3
        if len(present) == 2 and 'validation_record.cms' not in present:
            import identity
            try:
                cert, key = (read_private(self.keys / name) for name in FILES[:2])
                if identity.is_self_signed(cert) and identity.key_matches(cert, key):
                    value['message'] = 'Standard AirDrop identity is available. Import an Apple identity for Apple Account recognition.'
                    return value
            except SetupError:
                pass
        if len(present) != 3:
            value.update(state='incomplete', message='The Apple identity is incomplete. Import all three files together.')
            return value
        try:
            data = {name: read_private(self.keys / name) for name in FILES}
            # Hashing prevents stale validity even when a replacement preserves timestamps.
            import hashlib
            fingerprint = hashlib.sha256(b''.join(data.values())).hexdigest()
            cached = {}
            try: cached = json.loads((self.state / 'validation-cache.json').read_text())
            except (OSError, ValueError): pass
            if not isinstance(cached, dict) or not isinstance(cached.get('checked'), (int, float)) or not isinstance(cached.get('details'), dict): cached = {}
            if cached and (not isinstance(cached['details'].get('expires_epoch'), (int, float)) or not math.isfinite(cached['details']['expires_epoch']) or not all(isinstance(cached['details'].get(k), str) for k in ('certificate_expires', 'record_expires'))): cached = {}
            if not force and cached.get('fingerprint') == fingerprint and time.time() - cached.get('checked', 0) < 60:
                details = cached['details']
            else:
                details = validate(data)
                private_dir(self.state)
                write_private(self.state / 'validation-cache.json', json.dumps(dict(fingerprint=fingerprint, checked=time.time(), details=details)).encode())
            expiry = details['expires_epoch']
            days = max(0, math.ceil((expiry - time.time()) / 86400))
            value.update(certificate_expires=details['certificate_expires'], record_expires=details['record_expires'], days_remaining=days)
            if expiry <= time.time():
                value.update(state='expired', message='The Apple identity has expired. Import a renewed identity.')
            else:
                value.update(valid=True, state='expiring' if days <= 7 else 'valid',
                             message='Apple identity is valid.' if days > 7 else 'Apple identity expires soon. Import a renewed identity from its owner.')
        except (SetupError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            value.update(state='expired' if isinstance(error, SetupError) and 'expired' in str(error) else 'invalid', message=str(error) if isinstance(error, SetupError) else 'Unable to validate the installed Apple identity.')
        return value

    @contextlib.contextmanager
    def locked(self):
        private_dir(self.runtime)
        fd = os.open(self.runtime / 'identity.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise SetupError('AirDrop is starting or stopping. Try again when it finishes.') from None
            yield
        finally: os.close(fd)

    def idle(self):
        status = self.upstream_status()
        if status.get('receiving') or status.get('sending') or status.get('transfer_active'):
            raise SetupError('Stop receiving and finish any transfers before changing the Apple identity. Your current identity is unchanged.')
        # CLI sends mark a file independently of the receive flag.
        if (self.runtime / 'sends').is_dir() and any((self.runtime / 'sends').iterdir()):
            raise SetupError('Finish the current AirDrop transfer before changing the identity.')

    def switch(self, source, data=None):
        if data is not None: validate(data)
        with self.locked():
            self.idle()
            private_dir(self.keys)
            private_dir(self.config)
            private_dir(self.state)
            before = {name: read_private(self.keys / name) if (self.keys / name).exists() else None for name in FILES} if data is not None else {}
            old_settings = self.settings_data()
            had_settings = self.settings.exists()
            backup = Path(tempfile.mkdtemp(prefix='backup-', dir=self.state))
            for name, contents in before.items():
                if contents is not None: write_private(backup / name, contents)
            write_private(backup / 'settings', old_settings)
            try:
                if data is not None:
                    for name in FILES: write_private(self.keys / name, data[name])
                lines = [line for line in old_settings.decode().splitlines() if not line.startswith('identity_source=')]
                lines.append('identity_source=' + source)
                write_private(self.settings, ('\n'.join(lines) + '\n').encode())
                if data is not None: validate({name: read_private(self.keys / name) for name in FILES})
            except Exception:
                recovery_failed = False
                for name, contents in before.items():
                    try:
                        if contents is None: (self.keys / name).unlink(missing_ok=True)
                        else: write_private(self.keys / name, contents)
                    except OSError:
                        recovery_failed = True
                try:
                    if had_settings: write_private(self.settings, old_settings)
                    else: self.settings.unlink(missing_ok=True)
                except OSError:
                    recovery_failed = True
                if recovery_failed:
                    raise SetupError('Identity setup and recovery failed. Keep receiving off. Restore the private backup at ' + str(backup) + '.') from None
                raise SetupError('Identity setup failed. The previous identity and settings were restored.') from None
        return {'ok': True, 'message': 'Apple identity imported. Enable AirDrop to use it.' if data else 'Self-signed identity selected. Enable AirDrop to use it.', 'status': self.status(force=True)}

    def import_directory(self, directory):
        data = {name: read_private(Path(directory).expanduser() / name) for name in FILES}
        return self.switch('disk', data)

    def export_helper(self, parent):
        dest = Path(parent).expanduser() / 'omdrop-mac-helper'
        if not dest.parent.is_dir() or dest.exists() or dest.is_symlink():
            raise SetupError('Choose an existing folder without an omdrop-mac-helper subfolder.')
        shutil.copytree(HELPER, dest)
        return {'ok': True, 'message': 'Mac helper saved in omdrop-mac-helper. Read README before running it on the identity owner’s Mac.', 'status': self.status()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'check', 'import', 'use-self-signed', 'export-helper'])
    parser.add_argument('directory', nargs='?')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--notify', action='store_true', help='Notify when a selected Apple identity needs renewal or repair.')
    args = parser.parse_args()
    setup = Setup()
    try:
        if args.command in ('status', 'check'):
            result = setup.status(force=args.command == 'check')
            code = 0 if args.command == 'status' or result['valid'] else 1
            if args.notify and (result['source'] != 'disk' or result['state'] == 'missing'):
                code = 0
            if args.notify and result['source'] == 'disk' and result['state'] != 'missing' and (not result['valid'] or result['state'] == 'expiring'):
                subprocess.run(['notify-send', '--app-name=OM Drop', 'Apple identity needs attention', result['message']], capture_output=True, timeout=10)
        elif args.command == 'use-self-signed': result, code = setup.switch('self-signed'), 0
        elif not args.directory: raise SetupError('Choose the identity or destination folder first.')
        elif args.command == 'import': result, code = setup.import_directory(args.directory), 0
        else: result, code = setup.export_helper(args.directory), 0
    except (SetupError, OSError, subprocess.TimeoutExpired) as error:
        result = {'ok': False, 'message': str(error) if isinstance(error, SetupError) else 'Identity setup could not finish. Check identity status before retrying.'}
        try: result['status'] = setup.status()
        except Exception: pass
        code = 1
    print(json.dumps(result) if args.json else result['message'])
    return code

if __name__ == '__main__':
    raise SystemExit(main())
