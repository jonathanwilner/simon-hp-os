import importlib.machinery
from pathlib import Path
import tempfile
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
            (docs / 'huge.txt').write_text('secret' + ' ' * 131072)
            self.assertEqual(search.search(home, 'secret'), [])
            for i in range(12): (docs / f'match{i}.txt').write_text('hello')
            self.assertEqual(len(search.search(home, 'match')), 8)
            self.assertEqual(search.search(home, 'match', seconds=0), [])

if __name__ == '__main__': unittest.main()
