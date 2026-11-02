#!/usr/bin/env python3
"""Opt-in Wayland clipboard agent. No clipboard content is logged."""
import argparse, hashlib, json, pathlib, subprocess, time, urllib.request
from urllib.parse import urlsplit

class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward native credentials to a login page or another host."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def validate_config(config):
    endpoint = urlsplit(config.get("url", ""))
    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError("Relay URL must not contain credentials, query, or fragment")
    if endpoint.scheme != "https" and not (endpoint.scheme == "http" and endpoint.hostname in ("127.0.0.1", "localhost", "::1")):
        raise ValueError("Relay requires HTTPS or a loopback SSH tunnel")
    if not endpoint.hostname:
        raise ValueError("Relay URL requires a hostname")
    for key in ("device_id", "device_name", "token_file"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError("Missing configuration: " + key)
    token = pathlib.Path(config["token_file"]).expanduser()
    if token.stat().st_mode & 0o077:
        raise ValueError("Token file must be private: chmod 600")
    if not token.read_text().strip():
        raise ValueError("Token file is empty")

class Agent:
    def __init__(self, config):
        self.config = config
        self.last_hash = None
        self.remote_id = None
        self.initialized = False
        self.written_deliveries = set()
    @staticmethod
    def digest(text):
        return hashlib.sha256(text.encode()).hexdigest()
    def api(self, method, path, body=None):
        token = pathlib.Path(self.config['token_file']).expanduser().read_text().strip()
        req = urllib.request.Request(self.config['url'].rstrip('/') + '/api/v1' + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'Relay/0.1'}, method=method)
        with urllib.request.build_opener(NoRedirect).open(req, timeout=5) as response:
            return json.load(response)
    def read(self):
        p = subprocess.run(['wl-paste', '--no-newline', '--type', 'text'], capture_output=True, timeout=3)
        return p.stdout.decode('utf-8') if p.returncode == 0 else None
    def write(self, text):
        subprocess.run(['wl-copy', '--type', 'text/plain;charset=utf-8'], input=text.encode(), check=True, timeout=3)
        self.last_hash = self.digest(text)
    def emacs_owned(self, text):
        """Share a content-free origin marker with the Emacs exporter."""
        marker = pathlib.Path(self.config.get('emacs_origin_file', '~/.cache/relay/emacs-clipboard-origin.json')).expanduser()
        try:
            value = json.loads(marker.read_text())
            return 0 <= time.time() - value['time'] < 60 and value['hash'] == self.digest(text)
        except (OSError, ValueError, KeyError, TypeError):
            return False
    def tick(self):
        c = self.config
        paused = pathlib.Path(c.get('pause_file', '~/.cache/relay/paused')).expanduser().exists()
        self.api('POST', '/devices', {'id': c['device_id'], 'name': c['device_name'], 'platform': 'linux', 'paused': paused})
        if paused:
            self.initialized = False
            return
        current = self.read()
        entries = self.api('GET', '/entries?limit=1')['entries']
        latest = entries[0] if entries else None
        if not self.initialized:
            self.last_hash = self.digest(current) if current is not None else None
            self.remote_id = (latest['id'], latest['updated_at']) if latest else None
            self.initialized = True
        elif current is not None and self.digest(current) != self.last_hash:
            if not self.emacs_owned(current):
                self.api('POST', '/entries', {'text': current, 'device_id': c['device_id'], 'device_name': c['device_name'], 'app': 'Wayland'})
            self.last_hash = self.digest(current)
            # A local copy wins over an older remote entry observed in this poll.
            self.remote_id = (latest['id'], latest['updated_at']) if latest else None
        elif c.get('auto_receive', False) and latest:
            key = (latest['id'], latest['updated_at'])
            if key != self.remote_id and latest['device_id'] != c['device_id'] and not latest['text'].startswith('relay-encrypted:'):
                self.write(latest['text'])
            self.remote_id = key
        from urllib.parse import quote
        for delivery in self.api('GET', '/deliveries?device_id=' + quote(c['device_id'], safe=''))['deliveries']:
            if delivery['entry']['text'].startswith('relay-encrypted:'):
                self.api('POST', '/deliveries/' + quote(delivery['id'], safe='') + '/fail', {'device_id': c['device_id'], 'reason': 'Encrypted entries require a compatible Android client'})
                continue
            if delivery['id'] not in self.written_deliveries:
                self.write(delivery['entry']['text'])
                self.written_deliveries.add(delivery['id'])
            self.api('POST', '/deliveries/' + quote(delivery['id'], safe='') + '/ack', {'device_id': c['device_id']})
            self.written_deliveries.discard(delivery['id'])

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    args = p.parse_args()
    config = json.loads(pathlib.Path(args.config).expanduser().read_text())
    if not config.get('enabled', False):
        p.error('Agent disabled: set enabled=true explicitly in your private configuration')
    try:
        validate_config(config)
    except (OSError, ValueError) as error:
        p.error(str(error))
    agent = Agent(config)
    while True:
        try:
            agent.tick()
        except (OSError, ValueError, subprocess.SubprocessError):
            print('Relay sync unavailable; retrying. Clipboard content was not logged.', flush=True)
        time.sleep(max(1, config.get('interval', 3)))
if __name__ == '__main__':
    main()
