import importlib.util
import fcntl
import os
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import nom_dashboard_progress as progress
import nom_dashboard_feed as feed

spec = importlib.util.spec_from_file_location("publisher", Path(__file__).with_name("nom-dashboard-publish.py"))
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class ProgressTests(unittest.TestCase):
    def test_bounds_and_unknown_totals(self):
        self.assertEqual(progress.normalized({"completed": 12, "total": 10})["percent"], 100)
        self.assertEqual(progress.normalized({"completed": -2, "total": 10})["percent"], 0)
        for total in (0, -1, float("nan"), float("inf"), True, "10"):
            self.assertIsNone(progress.normalized({"completed": 1, "total": total}))

    def test_sparse_download_and_last_piece(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"models": [{"directory": "target", "files": [
                {"path": "model", "size": 250}, {"path": "config", "size": 10}]}]}))
            directory = root / "target"
            directory.mkdir()
            (directory / "config").write_bytes(b"x" * 10)
            partial = directory / "model.aria2.partial"
            with partial.open("wb") as stream:
                stream.truncate(250)  # Full logical length; only two pieces saved.
            control = Path(str(partial) + ".aria2")
            control.write_bytes(struct.pack(">HIIIQQI", 1, 0, 0, 100, 250, 0, 1) + b"\xa0")
            result = progress.download_progress(manifest, root)
            self.assertEqual(result, {"completed": 160, "total": 260, "unit": "bytes"})
            control.write_bytes(b"truncated")
            self.assertEqual(progress.download_progress(manifest, root)["completed"], 10)
            control.unlink()
            self.assertEqual(progress.download_progress(manifest, root)["completed"], 10)

    def test_bad_source_and_traversal(self):
        for malformed in ([], None, {"source": []}, {"source": 5}):
            self.assertIsNone(progress.resolve(malformed))
        self.assertIsNone(progress.resolve({"source": {"kind": "model-manifest", "manifest": "/missing", "root": "/tmp"}}))
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(json.dumps({"models": [{"directory": "../escape", "files": [{"path": "x", "size": 10}]}]}))
            with self.assertRaises(ValueError):
                progress.download_progress(manifest, tmp)

    def test_busy_sync_lock_skips_duplicate_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            with (state / ".sync.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                environment = dict(os.environ, NOM_DASHBOARD_STATE_DIR=str(state),
                                   NOM_DASHBOARD_PUBLIC_DIR=str(root / "public"))
                environment.pop("NOM_DASHBOARD_SYNC_LOCKED", None)
                subprocess.run(["bash", str(Path(__file__).with_name("nom-dashboard-sync.sh"))],
                               env=environment, check=True, timeout=5)
            self.assertFalse((root / "public").exists())

    def test_sync_aggregate_is_atomic_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "machines" / "first"
            directory.mkdir(parents=True)
            (directory / "manifest.json").write_text(json.dumps({"host": "first", "totals": {"running": 1}}))
            subprocess.run([sys.executable, str(Path(__file__).with_name("nom_dashboard_feed.py")), tmp], check=True)
            data = json.loads((root / "manifest.json").read_text())
            self.assertEqual(data["totals"]["running"], 1)
            self.assertTrue((root / "manifest.json").read_bytes().endswith(b"\n"))
            self.assertEqual(list(root.glob(".manifest-*.tmp")), [])
            self.assertEqual(json.loads((root / "dashboard/manifest.json").read_text())["totals"], data["totals"])

    def test_compact_feed_keeps_active_tasks_counts_and_progress(self):
        sessions = [{"safe_session": str(i), "status": "succeeded", "updated_at": f"{i:03d}",
                     "command": "x" * 10000} for i in range(100)]
        sessions[0].update(status="running", progress={"percent": 23.4})
        value = {"machines": [{"host": "host", "sessions": sessions, "totals": {"running": 1}}], "totals": {"running": 1}}
        compact = feed.compact_feed(value, recent_limit=5)
        machine = compact["machines"][0]
        self.assertEqual(machine["total_sessions"], 100)
        self.assertEqual(len(machine["sessions"]), 6)
        self.assertEqual(machine["sessions"][-1]["progress"]["percent"], 23.4)
        self.assertEqual(machine["totals"], {"running": 1})
        self.assertTrue(all(len(session["command"]) <= 160 for session in machine["sessions"]))

    def test_canonical_html_entry_uses_direct_asset_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run([sys.executable, str(Path(__file__).with_name("nom-dashboard-publish.py")),
                            "--state-dir", str(root / "state"), "--output-dir", str(root / "public"),
                            "--asset-dir", str(Path(__file__).parent / "web")], check=True)
            html = (root / "public/dashboard.html").read_text()
            self.assertIn('href="dashboard/styles.css"', html)
            self.assertIn('src="dashboard/app.js"', html)
            self.assertTrue((root / "public/dashboard/manifest.json").exists())

    def test_publish_phase_preserves_status_and_sidecars_are_not_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            (state / "install.log").write_text("working")
            (state / "install.json").write_text(json.dumps({"session": "install", "phase": "running"}))
            (state / "install.progress.json").write_text(json.dumps({"completed": 10, "total": 10, "scope": "phase", "label": "Download"}))
            result = publisher.collect_sessions(state, root / "public", "test", 1000)
            self.assertEqual(len(result["sessions"]), 1)
            self.assertEqual(result["sessions"][0]["status"], "running")
            self.assertEqual(result["sessions"][0]["progress"]["percent"], 100)
            (state / "install.status").write_text("1")
            result = publisher.collect_sessions(state, root / "public", "test", 1000)
            self.assertEqual(result["sessions"][0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
