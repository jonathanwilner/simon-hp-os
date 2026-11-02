import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('floating', Path(__file__).parents[1] / 'packaging/hp-os-toggle-floating-all.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FloatingTests(unittest.TestCase):
    def check_actions(self, windows, expected):
        with patch.object(module.subprocess, 'check_output', return_value=json.dumps(windows)), patch.object(module.subprocess, 'run') as run:
            run.return_value.returncode = 0
            module.toggle('niri')
            self.assertEqual([call.args[0][3:] for call in run.call_args_list], expected)

    def test_mixed_floats_tiled_windows(self):
        self.check_actions([{'id': 1, 'is_floating': False}, {'id': 2, 'is_floating': True}], [['move-window-to-floating', '--id', '1']])

    def test_all_floating_tiles_every_window(self):
        self.check_actions([{'id': 1, 'is_floating': True}, {'id': 2, 'is_floating': True}], [['move-window-to-tiling', '--id', '1'], ['move-window-to-tiling', '--id', '2']])

    def test_empty_session(self):
        self.check_actions([], [])


if __name__ == '__main__':
    unittest.main()
