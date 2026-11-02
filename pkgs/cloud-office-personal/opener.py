#!/usr/bin/env python3
"""Open documents in the signed-in user's own OneDrive and Microsoft 365."""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

EXTENSIONS = set('doc docx docm dot dotx dotm xls xlsx xlsm xlt xltx xltm xlsb ppt pptx pptm pot potx potm pps ppsx ppsm rtf odt ods odp csv'.split())
SCOPES = ['Files.ReadWrite']
MAX_BYTES = 250 * 1024 * 1024


def state_dir():
    path = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'cloud-office-personal'
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def save(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.office-')
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(value, output)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def token(state, interactive=False):
    import msal
    settings = state / 'account.json'
    if not settings.exists():
        raise ValueError('Run cloud-office-open --configure CLIENT_ID, then --login. See the Simon application setup guide.')
    cfg = json.loads(settings.read_text())
    cache = msal.SerializableTokenCache()
    cache_path = state / 'tokens.json'
    if cache_path.exists():
        cache.deserialize(cache_path.read_text())
    app = msal.PublicClientApplication(cfg['client_id'], authority='https://login.microsoftonline.com/' + cfg['tenant'], token_cache=cache)
    accounts = [a for a in app.get_accounts() if a['home_account_id'] == cfg.get('account_id')]
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    if interactive:
        result = app.acquire_token_interactive(SCOPES, prompt='select_account', timeout=300)
    if cache.has_state_changed:
        save(cache_path, json.loads(cache.serialize()))
    if not result or 'access_token' not in result:
        raise ValueError('Microsoft sign-in is required. Run cloud-office-open --login. Your organization may require administrator consent.')
    if interactive:
        claims = result.get('id_token_claims', {})
        accounts = [a for a in app.get_accounts() if a.get('local_account_id') == claims.get('oid') or a.get('username', '').lower() == claims.get('preferred_username', '').lower()]
        if len(accounts) != 1:
            raise ValueError('Could not select one Microsoft account. Configure again and sign in to one account.')
        cfg['account_id'] = accounts[0]['home_account_id']
        save(settings, cfg)
    return result['access_token']


def cloud_url(value):
    u = urlsplit(value)
    host = (u.hostname or '').lower()
    return u.scheme == 'https' and not u.username and not u.password and (host.endswith('.sharepoint.com') or host in {'onedrive.live.com', '1drv.ms', 'office.live.com', 'word.cloud.microsoft', 'excel.cloud.microsoft', 'powerpoint.cloud.microsoft'})


def web_url(value):
    if not cloud_url(value):
        raise ValueError('Microsoft did not return an accepted HTTPS Office document URL.')
    u = urlsplit(value)
    return urlunsplit(u._replace(query=urlencode([(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k.lower() != 'web'] + [('web', '1')])))


def graph(access_token, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request('https://graph.microsoft.com/v1.0' + path, data=data, method=method,
                      headers={'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def folder(access_token, parent, name):
    path = '/me/drive/items/' + quote(parent, safe='')
    try:
        item = graph(access_token, 'GET', path + ':/' + quote(name, safe=''))
    except HTTPError as error:
        if error.code != 404:
            raise
        try:
            item = graph(access_token, 'POST', path + '/children', {'name': name, 'folder': {}, '@microsoft.graph.conflictBehavior': 'fail'})
        except HTTPError as conflict:
            if conflict.code != 409:
                raise
            item = graph(access_token, 'GET', path + ':/' + quote(name, safe=''))
    if 'folder' not in item:
        raise ValueError('The OneDrive upload folder name is occupied by a file.')
    return item['id']


def checked_path(value):
    u = urlsplit(value)
    if u.scheme == 'file' and u.netloc in ('', 'localhost'):
        path = Path(unquote(u.path))
    elif not u.scheme:
        path = Path(value).expanduser()
    else:
        raise ValueError('Download the document locally first, or open its Microsoft 365 HTTPS link.')
    if path.suffix.lower().lstrip('.') not in EXTENSIONS or not path.is_file():
        raise ValueError('Select an existing Office document.')
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError('The document must be between 1 byte and 250 MB.')
    return path


def upload(access_token, path):
    # Content-addressed folders preserve browser edits when the local original is reopened.
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    root = graph(access_token, 'GET', '/me/drive/root')['id']
    parent = folder(access_token, folder(access_token, root, 'HP-OS Office'), digest)
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', path.name).strip(' .')
    item_path = '/me/drive/items/' + quote(parent, safe='') + ':/' + quote(name, safe='')
    try:
        return web_url(graph(access_token, 'GET', item_path)['webUrl'])
    except HTTPError as error:
        if error.code != 404:
            raise
    # Upload sessions have explicit fail-on-conflict semantics. Never overwrite cloud edits.
    try:
        session = graph(access_token, 'POST', item_path + ':/createUploadSession', {'item': {'@microsoft.graph.conflictBehavior': 'fail', 'name': name}})
        upload_url = session['uploadUrl']
        if urlsplit(upload_url).scheme != 'https':
            raise ValueError('Microsoft returned an invalid upload session URL.')
        size = path.stat().st_size
        with path.open('rb') as source:
            offset = 0
            while chunk := source.read(10 * 1024 * 1024):
                request = Request(upload_url, data=chunk, method='PUT', headers={
                    'Content-Length': str(len(chunk)), 'Content-Range': f'bytes {offset}-{offset + len(chunk) - 1}/{size}',
                    'Content-Type': 'application/octet-stream'})
                with urlopen(request, timeout=120) as response:
                    item = json.load(response)
                offset += len(chunk)
        return web_url(item['webUrl'])
    except HTTPError as conflict:
        if conflict.code != 409:
            raise
        return web_url(graph(access_token, 'GET', item_path)['webUrl'])


def document_app(url):
    u = urlsplit(url)
    name = dict(parse_qsl(u.query)).get('file', unquote(u.path))
    suffix = Path(name).suffix.lower().lstrip('.')
    for app, extensions in {
        'word': 'doc docx docm dot dotx dotm rtf odt',
        'excel': 'xls xlsx xlsm xlt xltx xltm xlsb ods csv',
        'powerpoint': 'ppt pptx pptm pot potx potm pps ppsx ppsm odp',
    }.items():
        if suffix in extensions.split():
            return app
    match = re.match(r'/:(w|x|p):/', u.path)
    return {'w': 'word', 'x': 'excel', 'p': 'powerpoint'}.get(match.group(1)) if match else None


def register_document_icon(url):
    """Match Chromium's URL-derived Wayland ID to the existing Office icon."""
    app = document_app(url)
    if not app:
        return url
    u = urlsplit(url)
    # SharePoint's typed routes keep Word/Excel/PowerPoint IDs separate even
    # when all three use the same Doc.aspx endpoint. The query stays intact.
    if (u.hostname or '').endswith('.sharepoint.com') and not re.match(r'/:[a-z]:/', u.path):
        kind = {'word': 'w', 'excel': 'x', 'powerpoint': 'p'}[app]
        u = u._replace(path='/:' + kind + ':/r' + u.path)
        url = urlunsplit(u)
    app_name = (u.hostname or '') + '_' + u.path
    app_id = 'chrome-' + re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', app_name).strip('_') + '-Default'
    applications = Path.home() / '.local/share/applications'
    original = applications / ('microsoft365-' + app + '.desktop')
    if not original.exists() or len(app_id.encode()) > 240:
        return url
    desktop = configparser.ConfigParser(interpolation=None)
    desktop.optionxform = str
    desktop.read(original)
    desktop['Desktop Entry']['StartupWMClass'] = app_id
    desktop['Desktop Entry']['NoDisplay'] = 'true'
    destination = applications / (app_id + '.desktop')
    temporary = destination.with_suffix('.desktop.new')
    with temporary.open('w') as stream:
        desktop.write(stream, space_around_delimiters=False)
    temporary.replace(destination)
    return url


def launch(url):
    launcher = Path.home() / '.local/bin/chrome-live-control'
    subprocess.run([str(launcher), '--app=' + register_document_icon(web_url(url))], check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--configure', metavar='CLIENT_ID')
    actions.add_argument('--login', action='store_true')
    parser.add_argument('--tenant', default='common')
    parser.add_argument('targets', nargs='*')
    args = parser.parse_args(argv)
    if not (args.configure or args.login or args.targets):
        parser.error('provide document paths/URLs, --configure CLIENT_ID, or --login')
    try:
        state = state_dir()
        with (state / 'lock').open('a+') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            if args.configure:
                import uuid
                uuid.UUID(args.configure)
                if not re.fullmatch(r'[a-zA-Z0-9.-]+', args.tenant):
                    raise ValueError('Tenant must be a tenant ID, domain, common, organizations or consumers.')
                save(state / 'account.json', {'client_id': args.configure, 'tenant': args.tenant})
                (state / 'tokens.json').unlink(missing_ok=True)
                print('Configuration saved. Run cloud-office-open --login and sign in with your own Microsoft account.')
                return 0
            if args.login:
                token(state, interactive=True)
                print('Your Microsoft account is connected.')
                return 0
            for target in args.targets:
                target = re.sub(r'^ms-(?:word|excel|powerpoint):(?:ofe|ofv)\|u\|', '', target, flags=re.I)
                url = web_url(target) if cloud_url(target) else upload(token(state), checked_path(target))
                launch(url)
        return 0
    except Exception as error:
        message = str(error) if isinstance(error, ValueError) else 'Office could not open the document. Check Microsoft sign-in, permissions and network access.'
        print('cloud-office-open: ' + message, file=sys.stderr)
        subprocess.run(['notify-send', 'Cloud Office', message], check=False)
        return 1


if __name__ == '__main__':
    sys.exit(main())
