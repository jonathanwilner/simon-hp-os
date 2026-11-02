"""Exercise persistence and rejection through the real CLI with a mock Niri."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("hdr-control.py")


class HdrControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.config = self.directory / "niri" / "hdr.kdl"
        self.log = self.directory / "validation.log"
        self.niri = self.directory / "niri-mock"
        self.niri.write_text(f'''#!{sys.executable}
import os, pathlib, sys, time
assert sys.argv[1:3] == ["validate", "--config"]
candidate = pathlib.Path(sys.argv[3])
assert candidate.exists()
with open(os.environ["VALIDATION_LOG"], "a") as log:
    log.write("start\\n")
time.sleep(float(os.environ.get("VALIDATION_DELAY", "0")))
with open(os.environ["VALIDATION_LOG"], "a") as log:
    log.write("end\\n")
if os.environ.get("REJECT") == "1":
    print("unsupported HDR syntax", file=sys.stderr)
    sys.exit(1)
''')
        self.niri.chmod(0o700)
        self.environment = dict(os.environ, GORAN_HDR_CONFIG=str(self.config),
                                NIRI_BINARY=str(self.niri), VALIDATION_LOG=str(self.log))

    def run_cli(self, *arguments, succeeds=True, **environment):
        result = subprocess.run([sys.executable, str(SCRIPT), *arguments],
                                env=dict(self.environment, **environment), text=True, capture_output=True)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr)
        return result

    def test_init_seeds_and_preserves_existing_preference(self):
        self.assertEqual(self.run_cli("init"), {"enabled": True, "reference_luminance": 500, "output": "eDP-1"})
        self.run_cli("set", "on", "350")
        before = self.config.read_bytes()
        log = self.log.read_bytes()
        self.assertEqual(self.run_cli("init")["reference_luminance"], 350)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.log.read_bytes(), log)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_off_preserves_white_across_cli_processes(self):
        self.run_cli("init")
        self.run_cli("set", "on", "325")
        self.assertFalse(self.run_cli("set", "off")["enabled"])
        self.assertNotIn('hdr mode=', self.config.read_text())
        self.assertEqual(self.run_cli("status")["reference_luminance"], 325)
        self.assertEqual(self.run_cli("set", "on")["reference_luminance"], 325)

    def test_off_can_set_saved_white(self):
        self.run_cli("init")
        self.run_cli("set", "off", "200")
        self.assertEqual(self.run_cli("set", "on")["reference_luminance"], 200)

    def test_reset_restores_default_and_recovers_malformed_file(self):
        self.run_cli("init")
        self.config.write_text("unknown external configuration\n")
        self.run_cli("status", succeeds=False)
        self.assertEqual(self.run_cli("reset")["reference_luminance"], 500)
        self.assertTrue(self.run_cli("status")["enabled"])

    def test_validation_rejection_preserves_previous_file(self):
        self.run_cli("init")
        before = self.config.read_bytes()
        result = self.run_cli("set", "off", "200", succeeds=False, REJECT="1")
        self.assertIn("unsupported HDR syntax", result.stderr)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(list(self.config.parent.glob(".hdr-candidate-*")), [])

    def test_init_validation_failure_does_not_create_include(self):
        self.run_cli("init", succeeds=False, REJECT="1")
        self.assertFalse(self.config.exists())

    def test_missing_niri_preserves_previous_file(self):
        self.run_cli("init")
        before = self.config.read_bytes()
        self.run_cli("set", "off", succeeds=False, NIRI_BINARY=str(self.directory / "absent"))
        self.assertEqual(self.config.read_bytes(), before)

    def test_invalid_input_does_not_change_file_or_validate(self):
        self.run_cli("init")
        before, log = self.config.read_bytes(), self.log.read_bytes()
        for arguments in [("set", "on", "99"), ("set", "on", "501"), ("set", "on", "2.5"),
                          ("set", "on", '500}\noutput "DP-1" {}'), ("set", "bad"),
                          ("set", "on", "200", str(self.directory / "other.kdl"))]:
            with self.subTest(arguments=arguments):
                self.run_cli(*arguments, succeeds=False)
                self.assertEqual(self.config.read_bytes(), before)
                self.assertEqual(self.log.read_bytes(), log)

    def test_foreign_content_rejected_without_change(self):
        self.run_cli("init")
        self.config.write_text(self.config.read_text() + 'output "DP-1" {}\n')
        before = self.config.read_bytes()
        self.run_cli("status", succeeds=False)
        self.run_cli("init", succeeds=False)
        self.run_cli("set", "off", succeeds=False)
        self.assertEqual(self.config.read_bytes(), before)

    def test_main_config_is_untouched(self):
        self.config.parent.mkdir()
        main = self.config.with_name("config.kdl")
        original = 'include "hdr.kdl" optional=true\ninput { keyboard {} }\n'
        main.write_text(original)
        self.run_cli("init")
        self.run_cli("set", "off")
        self.run_cli("reset")
        self.assertEqual(main.read_text(), original)

    def test_symlink_rejected_without_modifying_target(self):
        self.config.parent.mkdir()
        target = self.directory / "other.kdl"
        target.write_text("do not change")
        self.config.symlink_to(target)
        for command in ("init", "status", "reset"):
            self.run_cli(command, succeeds=False)
        self.assertEqual(target.read_text(), "do not change")
        self.assertTrue(self.config.is_symlink())

    def test_concurrent_writers_serialize_validation(self):
        self.run_cli("init")
        self.log.write_text("")
        processes = [subprocess.Popen([sys.executable, str(SCRIPT), "set", "on", str(white)],
                                     env=dict(self.environment, VALIDATION_DELAY="0.03"),
                                     text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for white in (200, 300, 400, 500)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout)["output"], "eDP-1")
        self.assertEqual(self.log.read_text(), "start\nend\n" * 4)
        self.assertIn(self.run_cli("status")["reference_luminance"], (200, 300, 400, 500))


if __name__ == "__main__":
    unittest.main()
