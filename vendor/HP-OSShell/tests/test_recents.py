"""Exercise recent history with private temporary data and no desktop services."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'packaging/hp-os-recents.py'


class RecentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.data = self.home / 'data'
        self.data.mkdir()
        self.state = self.home / 'state'
        self.env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.data),
                        XDG_STATE_HOME=str(self.state))
        self.env.pop('INIR_STATE_DIR', None)

    def run_cli(self, *args, success=True):
        result = subprocess.run([sys.executable, str(HELPER), *args], env=self.env,
                                text=True, capture_output=True, timeout=10)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def listing(self, limit=20):
        result = json.loads(self.run_cli('list', '--limit', str(limit)).stdout)
        self.assertIsInstance(result['files'], list)
        self.assertIsInstance(result['apps'], list)
        return result

    def file(self, name):
        path = self.home / name
        path.write_text('fixture')
        return path

    def xbel(self, entries):
        bookmarks = ''.join('<bookmark href=%s modified=%s><title>ignored</title></bookmark>' %
                            (quoteattr(uri), quoteattr(date)) for uri, date in entries)
        (self.data / 'recently-used.xbel').write_text('<xbel>' + bookmarks + '</xbel>')

    def desktop_recent(self, name, url, modified, extra=''):
        directory = self.data / 'RecentDocuments'
        directory.mkdir(exist_ok=True)
        path = directory / (name + '.desktop')
        path.write_text('[Desktop Entry]\nType=Link\nName=' + name + '\nURL=' + url + '\n' + extra)
        os.utime(path, (modified, modified))

    def test_empty_and_malformed_inputs_are_safe(self):
        self.assertEqual(self.listing(), {'files': [], 'apps': []})
        (self.data / 'recently-used.xbel').write_text('<xbel><broken')
        history = self.state / 'hp-os' / 'start-menu-apps.json'
        history.parent.mkdir(parents=True)
        history.write_text('{not valid JSON')
        self.assertEqual(self.listing(), {'files': [], 'apps': []})
        self.run_cli('observe-app', 'org.kde.dolphin.desktop')
        self.assertEqual(self.listing()['apps'][0]['id'], 'org.kde.dolphin.desktop')

    def test_local_existing_regular_files_only_and_uri_decode(self):
        valid = self.file('report #1 中文.txt')
        directory = self.home / 'directory'
        directory.mkdir()
        missing = self.home / 'deleted.txt'
        self.xbel([(valid.as_uri(), '2026-01-03T00:00:00Z'),
                   (missing.as_uri(), '2026-01-06T00:00:00Z'),
                   (directory.as_uri(), '2026-01-05T00:00:00Z'),
                   ('https://example.test/remote.txt', '2026-01-04T00:00:00Z'),
                   ('file://remotehost' + str(valid), '2026-01-07T00:00:00Z')])
        files = self.listing()['files']
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['path'], str(valid))
        self.assertEqual(files[0]['name'], valid.name)
        self.assertEqual(files[0]['url'], valid.as_uri())
        self.assertTrue(files[0]['mime'])
        self.assertIn('modified', files[0])

    def test_deduplication_newest_order_and_limit_across_sources(self):
        first, second = self.file('first.txt'), self.file('second.txt')
        self.xbel([(first.as_uri(), '2026-01-01T00:00:00Z'),
                   (second.as_uri(), '2026-01-02T00:00:00Z')])
        self.desktop_recent('first', first.as_uri(), 1800000000)
        self.desktop_recent('second', second.as_uri(), 1700000000)
        files = self.listing()['files']
        self.assertEqual([item['path'] for item in files], [str(first), str(second)])
        self.assertEqual(len(self.listing(1)['files']), 1)
        first.unlink()
        self.assertEqual([item['path'] for item in self.listing()['files']], [str(second)])

    def test_desktop_commands_and_non_file_urls_are_never_executed(self):
        marker = self.home / 'executed'
        real = self.file('document.txt')
        command = 'Exec=/bin/sh -c "touch ' + str(marker) + '"\n'
        self.desktop_recent('valid', real.as_uri(), 1800000000, command)
        self.desktop_recent('malicious', '$(touch ' + str(marker) + ')', 1800000001, command)
        self.assertEqual([item['path'] for item in self.listing()['files']], [str(real)])
        self.assertFalse(marker.exists())

    def test_observation_persistence_deduplication_and_private_state(self):
        self.env['INIR_STATE_DIR'] = str(self.home / 'private')
        for app in ['org.kde.dolphin.desktop', 'org.kde.gwenview.desktop', 'org.kde.dolphin.desktop']:
            self.run_cli('observe-app', app)
        apps = self.listing()['apps']
        self.assertEqual([app['id'] for app in apps],
                         ['org.kde.dolphin.desktop', 'org.kde.gwenview.desktop'])
        self.assertTrue(all(isinstance(app['lastUsed'], (int, float)) for app in apps))
        history = self.home / 'private' / 'start-menu-apps.json'
        self.assertTrue(history.is_file())
        self.assertFalse((self.state / 'hp-os' / 'start-menu-apps.json').exists())
        self.assertEqual(len(self.listing(1)['apps']), 1)

    def test_history_rejects_nonfinite_values_and_caps_persistence(self):
        history = self.state / 'hp-os' / 'start-menu-apps.json'
        history.parent.mkdir(parents=True)
        entries = [{'id': f'app{i}.desktop', 'lastUsed': i + 1} for i in range(105)]
        entries += [{'id': 'nan.desktop', 'lastUsed': float('nan')},
                    {'id': 'infinity.desktop', 'lastUsed': float('inf')},
                    {'id': 'negative.desktop', 'lastUsed': -1},
                    {'id': '../bad.desktop', 'lastUsed': 500},
                    {'id': 'app104.desktop', 'lastUsed': 3}, None, 'invalid']
        history.write_text(json.dumps({'apps': entries}))
        apps = self.listing(1000)['apps']
        self.assertEqual(len(apps), 100)
        self.assertEqual(apps[0]['id'], 'app104.desktop')
        self.assertEqual(apps[-1]['id'], 'app5.desktop')
        self.run_cli('observe-app', 'new.desktop')
        saved = json.loads(history.read_text())['apps']
        self.assertEqual(len(saved), 100)
        self.assertEqual(saved[0]['id'], 'new.desktop')
        self.assertEqual(self.listing(0), {'files': [], 'apps': []})

    def test_invalid_app_ids_do_not_enter_history(self):
        marker = self.home / 'executed'
        for app in ['', '../escape.desktop', 'org app.desktop', 'x;touch ' + str(marker),
                    'x\n.desktop', 'x' * 256]:
            self.run_cli('observe-app', app, success=False)
        self.assertEqual(self.listing()['apps'], [])
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
