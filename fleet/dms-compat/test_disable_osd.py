import importlib.util
import pathlib
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("disable_osd", pathlib.Path(__file__).with_name("disable-osd.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PatchTest(unittest.TestCase):
    def test_disables_only_osd(self):
        source = '''Loader {
        id: osdSurfacesLoader
        active: root.osdSurfacesLoaded
        sourceComponent: VolumeOSD {}
    }
    Loader { id: lockScreenLoader; active: root.locked }
'''
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "DMSShell.qml"
            path.write_text(source)
            module.patch(directory)
            self.assertEqual(path.read_text(), source.replace(
                "active: root.osdSurfacesLoaded", "active: false /* HP-OS owns hotkey feedback */"))

    def test_unknown_revision_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "DMSShell.qml"
            path.write_text("Loader { id: lockScreenLoader }")
            with self.assertRaises(RuntimeError):
                module.patch(directory)
            self.assertEqual(path.read_text(), "Loader { id: lockScreenLoader }")


if __name__ == "__main__":
    unittest.main()
