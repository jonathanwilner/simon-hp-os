#!/usr/bin/env python3
"""Keep untrusted image manifests out of the terminal command stream."""
import base64
import importlib.util
import io
from pathlib import Path
import unittest
from PIL import Image

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).with_name('kitty-bridge.py'))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class ManifestTests(unittest.TestCase):
    def image(self, **overrides):
        data = io.BytesIO()
        Image.new('RGB', (4, 4), 'red').save(data, format='PNG')
        return dict(id=42, columns=8, rows=6, png_base64=base64.b64encode(data.getvalue()).decode(), **overrides)

    def test_valid_png_generates_only_fixed_protocol(self):
        value = bridge.validate_manifest({'version': 1, 'images': [self.image()]})
        stream = io.BytesIO()
        bridge.upload(stream, 42, value[42])
        self.assertTrue(stream.getvalue().startswith(b'\033_Ga=T,f=100,i=42,U=1,c=8,r=6,q=2,m=0;'))

    def test_rejects_escape_in_data(self):
        item = self.image()
        item['png_base64'] = '\033]52;c;payload\a'
        with self.assertRaises(ValueError):
            bridge.validate_manifest({'version': 1, 'images': [item]})

    def test_rejects_invalid_geometry_and_ids(self):
        for key, value in [('id', 0), ('id', 0x1000000), ('id', True), ('columns', 65), ('rows', 64)]:
            item = self.image()
            item[key] = value
            with self.assertRaises(ValueError):
                bridge.validate_manifest({'version': 1, 'images': [item]})

    def test_rejects_duplicates_and_non_png(self):
        item = self.image()
        with self.assertRaises(ValueError):
            bridge.validate_manifest({'version': 1, 'images': [item, item]})
        item['png_base64'] = base64.b64encode(b'not a png').decode()
        with self.assertRaises(ValueError):
            bridge.validate_manifest({'version': 1, 'images': [item]})


if __name__ == '__main__':
    unittest.main()
