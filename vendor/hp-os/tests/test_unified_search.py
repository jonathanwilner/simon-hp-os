import importlib.machinery
from pathlib import Path
import tempfile
import os
import base64
from types import SimpleNamespace
from unittest.mock import patch
import unittest

ROOT = Path(__file__).resolve().parents[1]
search = importlib.machinery.SourceFileLoader('hp_search', str(ROOT / 'packaging/hp-os-search')).load_module()

class LocalSearch(unittest.TestCase):
    def test_names_content_unicode_and_uri(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            docs = home / 'Documents'; docs.mkdir()
            (docs / '季度 report.txt').write_text('A unique search phrase')
            self.assertEqual(search.search(home, '季度')[0]['name'], '季度 report.txt')
            self.assertEqual(search.search(home, 'UNIQUE phrase')[0]['url'], (docs / '季度 report.txt').as_uri())
            self.assertEqual(search.search(home, 'missing'), [])
            self.assertEqual(search.search(home, ''), [])

    def test_bounds_and_hidden_symlink_exclusion(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d); docs = home / 'Documents'; docs.mkdir()
            (home / 'outside.txt').write_text('secret')
            (docs / 'linked.txt').symlink_to(home / 'outside.txt')
            (docs / '.hidden.txt').write_text('secret')
            os.mkfifo(docs / 'pipe.txt')
            (docs / 'huge.txt').write_text('secret' + ' ' * 131072)
            self.assertEqual(search.search(home, 'secret'), [])
            for i in range(12): (docs / f'match{i}.txt').write_text('hello')
            self.assertEqual(len(search.search(home, 'match')), 8)
            self.assertEqual(search.search(home, 'match', seconds=0), [])

class IndexedResults(unittest.TestCase):
    def test_base64_trailing_space_and_deleted_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'xapiandb').mkdir()
            file = root / '季度 report.pdf'; file.write_text('fixture')
            output = '1 results\n' + base64.b64encode(file.as_uri().encode()).decode() + ' \n'
            with patch.object(search, 'config_dir', return_value=root), patch.object(search.subprocess, 'run', return_value=SimpleNamespace(stdout=output)):
                self.assertEqual(search.indexed_search('report')[0]['url'], file.as_uri())
                file.unlink()
                self.assertEqual(search.indexed_search('report'), [])

class SmartSearch(unittest.TestCase):
    def test_remote_endpoint_rejected(self):
        with patch.dict(os.environ, {'HP_OS_SEARCH_AI_URL': 'https://example.com/v1'}):
            self.assertEqual(search.smart_search('tax report'), ([], 'Local endpoint required'))

    def test_local_expansion_and_unavailable_fallback(self):
        import io
        responses = [io.BytesIO(b'{"data":[{"id":"existing-qwen"}]}'),
            io.BytesIO(b'{"choices":[{"message":{"content":"[\\"invoice\\"]"}}]}')]
        item = {'name':'receipt.pdf', 'path':'/tmp/receipt.pdf', 'url':'file:///tmp/receipt.pdf'}
        with patch.dict(os.environ, {'HP_OS_SEARCH_AI_URL':'http://127.0.0.1:30000/v1'}), patch.object(search, 'urlopen', side_effect=responses) as request, patch.object(search, 'indexed_search', side_effect=lambda q, limit=8: [item] if q == 'invoice' else []):
            result, state = search.smart_search('bill')
            self.assertEqual(result, [item])
            self.assertIn('complete', state)
            sent = request.call_args.args[0].data.decode()
            self.assertIn('bill', sent)
            self.assertNotIn('receipt.pdf', sent)
        with patch.object(search, 'urlopen', side_effect=OSError('unavailable')):
            self.assertIn('unavailable', search.smart_search('bill')[1])

if __name__ == '__main__': unittest.main()
