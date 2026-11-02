import importlib.util
from pathlib import Path
import tempfile
import tarfile
import unittest

spec = importlib.util.spec_from_file_location('snapshot', Path(__file__).resolve().parents[1] / 'snapshot-managed-files.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

class Snapshot(unittest.TestCase):
    def test_force_file_symlink_and_unrelated_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); home=root/'home'; managed=root/'managed'
            home.mkdir();managed.mkdir()
            (home/'settings').write_text('my live settings')
            (home/'untouched').write_text('unrelated data')
            (root/'external').mkdir();(root/'external/large-data').write_text('outside target')
            (home/'linked').symlink_to(root/'external',target_is_directory=True)
            (managed/'settings').symlink_to('/nix/store/example')
            (managed/'linked').mkdir();(managed/'linked/managed').symlink_to('/nix/store/example')
            output=root/'snapshot'
            self.assertEqual(module.snapshot(home,managed,output),2)
            with tarfile.open(output/'live-files.tar') as tar:
                self.assertEqual(set(tar.getnames()),{'settings','linked'})
                self.assertEqual(tar.extractfile('settings').read(),b'my live settings')
                self.assertTrue(tar.getmember('linked').issym())
                self.assertEqual(tar.getmember('linked').linkname,str(root/'external'))
            self.assertEqual(output.stat().st_mode & 0o777,0o700)
            self.assertEqual((output/'live-files.tar').stat().st_mode & 0o777,0o600)
            self.assertEqual((home/'untouched').read_text(),'unrelated data')

if __name__ == '__main__': unittest.main()
