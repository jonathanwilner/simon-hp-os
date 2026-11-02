"""Remote Office launchers must resolve to their original vendor artwork."""
import hashlib
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / 'packaging/files/data/icons/HP-OS'

class VendorIcons(unittest.TestCase):
    def test_remote_office_aliases_have_original_assets(self):
        manifest = json.loads((THEME / 'microsoft-sources.json').read_text())
        assets = {Path(row['file']).stem: row for row in manifest}
        for name in ['access', 'excel', 'onenote', 'outlook', 'powerpoint', 'publisher', 'word']:
            with self.subTest(application=name):
                row = assets['ms-' + name]
                path = THEME / row['file']
                data = path.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
                if path.suffix == '.svg':
                    svg = ET.fromstring(data)
                    self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
                    self.assertEqual(svg.attrib['viewBox'], '0 0 48 48')
                    self.assertTrue(row['url'].startswith('https://res.cdn.office.net/'))
                else:
                    self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                    self.assertEqual(struct.unpack('>II', data[16:24]), (256, 256))
                    self.assertIn('MSPUB.EXE', row['source'])

    def test_remote_desktop_clipboard_and_anyware_assets(self):
        manifest = json.loads((THEME / 'remote-launcher-sources.json').read_text())
        self.assertEqual({Path(row['file']).stem for row in manifest},
                         {'computer', 'video-display', 'edit-paste', 'hp-anyware'})
        for row in manifest:
            path = THEME / row['file']
            data = path.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
            if path.suffix == '.svg':
                svg = ET.fromstring(data)
                self.assertEqual(svg.attrib['viewBox'], '0 0 32 32')
                self.assertEqual(row['license'], 'MIT')
                self.assertNotIn(b'<filter', data)
            else:
                self.assertEqual(struct.unpack('>II', data[16:24]), (256, 256))
                self.assertTrue(row['url'].startswith('https://dl.anyware.hp.com/'))

    def test_cosmic_demo_has_upstream_appearance_artwork(self):
        row = json.loads((THEME / 'cosmic-sources.json').read_text())[0]
        data = (THEME / row['file']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
        self.assertEqual(ET.fromstring(data).attrib['viewBox'], '0 0 256 256')
        self.assertTrue((THEME / 'LICENSE.CosmicIcons').exists())

if __name__ == '__main__':
    unittest.main()
