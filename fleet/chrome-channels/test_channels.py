import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parent

class ChannelIsolation(unittest.TestCase):
    def launch(self, channel, args=()):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "browser"
            fake.write_text('#!/usr/bin/env python3\nimport json,os,sys\nprint(json.dumps({"args":sys.argv[1:],"profile":os.getenv("GOOGLE_CHROME_PROFILE_DIR"),"debug":os.getenv("GOOGLE_CHROME_REMOTE_DEBUG_PORT")}))\n')
            fake.chmod(0o755)
            env = dict(os.environ, HOME=directory, XDG_CONFIG_HOME=directory + "/config", GOOGLE_CHROME_PROFILE_DIR="/sensitive/stable", GOOGLE_CHROME_REMOTE_DEBUG_PORT="9222")
            return subprocess.run(["bash", str(ROOT / "launch.sh"), channel, str(fake), *args], env=env, capture_output=True, text=True)

    def test_channels_separate_profiles_and_allow_profile_directory(self):
        for channel in ("beta", "dev", "canary"):
            result = self.launch(channel, ["--profile-directory=Profile 2", "https://example.invalid"])
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data["args"][0].endswith("/config/google-chrome-" + channel))
            self.assertEqual(data["args"][1], "--profile-directory=Profile 2")
            self.assertIsNone(data["profile"])
            self.assertIsNone(data["debug"])

    def test_profile_overrides_and_debug_flags_are_rejected(self):
        for args in (["--user-data-dir=/sensitive/stable"], ["--user-data-dir", "/sensitive/stable"], ["--remote-debugging-port=9222"], ["--remote-debugging-port=09222"], ["--remote-debugging-port", "9223"], ["--remote-debugging-pipe"], ["-user-data-dir=/sensitive/stable"], ["-remote-debugging-port=9222"]):
            result = self.launch("beta", args)
            self.assertEqual(result.returncode, 2, args)
            self.assertEqual(result.stdout, "")

    def test_argument_terminator_keeps_forced_profile_first(self):
        result = self.launch("dev", ["--", "https://example.invalid"])
        data = json.loads(result.stdout)
        self.assertTrue(data["args"][0].endswith("/config/google-chrome-dev"))
        self.assertEqual(data["args"][1], "--")

    def test_manifest_covers_native_fleet_architectures(self):
        manifest = json.loads((ROOT / "sources.json").read_text())
        self.assertEqual(set(manifest), {"stable", "beta", "dev", "canary"})
        for channel, release in manifest.items():
            self.assertEqual(set(release["platforms"]), {"x86_64-linux", "aarch64-linux"})
            for platform, source in release["platforms"].items():
                self.assertTrue(source["url"].startswith("https://dl.google.com/linux/chrome/deb/"))
                self.assertIn("google-chrome-" + release["dist"], source["url"])
                self.assertTrue(source["hash"].startswith("sha256-"))

if __name__ == "__main__":
    unittest.main()
