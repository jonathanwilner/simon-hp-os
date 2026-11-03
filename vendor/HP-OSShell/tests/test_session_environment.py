"""Shell upgrades must not reload icon assets from an older Nix generation."""
import os
from pathlib import Path
import subprocess
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'packaging/session-environment.sh'


class SessionEnvironmentTests(unittest.TestCase):
    def clean(self, directories, packaging='/nix/store/current-hp-os-0.1.0/share/hp-os/packaging'):
        return subprocess.check_output(
            ['bash', '-c', 'source "$1"; hpos_clean_data_dirs "$2"; printf %s "$XDG_DATA_DIRS"',
             'test', str(HELPER), packaging],
            env={**os.environ, 'XDG_DATA_DIRS': directories}, text=True)

    def test_upgrade_keeps_current_assets_and_unrelated_desktops(self):
        current = '/nix/store/current-hp-os-0.1.0'
        old = '/nix/store/previous-hp-os-0.1.0'
        suffixes = ['/share/hp-os/packaging/files/data', '/share/hp-os', '/share']
        wanted = [current + suffix for suffix in suffixes] + ['/home/me/.local/share', '/usr/share']
        inherited = wanted[:3] + [old + suffix for suffix in suffixes] + wanted[3:] + [wanted[0]]
        self.assertEqual(self.clean(':'.join(inherited)), ':'.join(wanted))

    def test_source_install_preserves_search_path(self):
        directories = '/tmp/custom-theme:/usr/share'
        self.assertEqual(self.clean(directories, '/tmp/source/packaging'), directories)

    def test_empty_value_retains_standard_defaults(self):
        self.assertEqual(self.clean(''), '/usr/local/share:/usr/share')


if __name__ == '__main__':
    unittest.main()
