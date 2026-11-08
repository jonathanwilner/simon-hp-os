#!/usr/bin/env python3
"""Keep GPU policy scoped to detected hardware and preserve caller choices."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import gpu

class GPUSelection(unittest.TestCase):
    def test_driver_detection_and_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / 'class/drm/card0/device'
            driver = root / 'bus/platform/drivers/msm'
            driver.mkdir(parents=True)
            device.mkdir(parents=True)
            (device / 'driver').symlink_to(driver)
            icds = root / 'icds'
            icds.mkdir()
            freedreno = icds / 'freedreno_icd.aarch64.json'
            freedreno.touch()
            (icds / 'nvidia_icd.json').touch()
            with patch.dict(os.environ, {}, clear=True):
                devices = gpu.detect(root)
                self.assertEqual(devices[0]['kind'], 'qualcomm')
                self.assertEqual(gpu.environment(devices, icds), {'VK_DRIVER_FILES': str(freedreno)})
                self.assertEqual(gpu.environment([{'kind': 'nvidia'}], icds), {})
                self.assertEqual(gpu.environment([{'kind': 'nvidia'}, {'kind': 'qualcomm'}], icds), {})
                self.assertEqual(gpu.environment([], icds), {})
            with patch.dict(os.environ, {'VK_DRIVER_FILES': '/chosen.json'}):
                self.assertEqual(gpu.environment(devices, icds), {})
    def test_pci_nvidia(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / 'class/drm/card0/device'
            device.mkdir(parents=True)
            (device / 'vendor').write_text('0x10de\n')
            self.assertEqual(gpu.detect(root)[0]['kind'], 'nvidia')

if __name__ == '__main__':
    unittest.main()
