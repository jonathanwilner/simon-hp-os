#!/usr/bin/env python3
import importlib.util
import pathlib
import os
import json
import subprocess
import shutil
import tempfile
import unittest
import sys
import signal
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("installer", ROOT / "packaging/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.runtime = self.base / "runtime"
        (self.runtime / "modules/hpos").mkdir(parents=True)
        (self.runtime / "shell.qml").write_text("ShellRoot {}")
        (self.runtime / "modules/hpos/HposPanels.qml").write_text("Item {}")
        self.prefix = self.base / "installed"

    def test_dry_run_creates_nothing(self):
        result = installer.install(self.runtime, self.prefix, True)
        self.assertTrue(result["dry_run"])
        self.assertFalse(self.prefix.exists())

    def test_install_and_replacement_preserve_previous_version(self):
        installer.install(self.runtime, self.prefix)
        self.assertTrue((self.prefix / "bin/hp-os").stat().st_mode & 0o111)
        self.assertNotIn("@runtime@", (self.prefix / "bin/hp-os").read_text())
        settings = (self.prefix / "share/applications/hp-os-settings.desktop").read_text()
        self.assertIn(f"Exec={self.prefix}/bin/hp-os settings", settings)
        (self.prefix / "keep").write_text("previous installation")
        result = installer.install(self.runtime, self.prefix)
        self.assertEqual((pathlib.Path(result["backup"]) / "keep").read_text(), "previous installation")
        self.assertFalse((self.prefix / "keep").exists())

    def test_invalid_runtime_rejected(self):
        (self.runtime / "shell.qml").unlink()
        with self.assertRaises(ValueError):
            installer.install(self.runtime, self.prefix)
        self.assertFalse(self.prefix.exists())

class RunnerIsolationTests(unittest.TestCase):
    def test_commands_target_only_selected_quickshell_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = pathlib.Path(temporary)
            binary = base / "qs"
            binary.write_text('#!' + shutil.which('bash') + '\nprintf "%s\\n" "$@" > "$COMMAND_LOG"\n')
            binary.chmod(0o755)
            env = dict(os.environ, PATH=str(base) + ":" + os.environ["PATH"], COMMAND_LOG=str(base / "args"), HP_OS_RUNTIME=str(base / "runtime"))
            expected = {"stop": ["kill", "-p", str(base / "runtime")], "settings": ["ipc", "-p", str(base / "runtime"), "call", "settings", "toggle"], "logs": ["log", "-p", str(base / "runtime")]}
            for command, arguments in expected.items():
                subprocess.run(["bash", str(ROOT / "packaging/hp-os"), command], env=env, check=True)
                self.assertEqual((base / "args").read_text().splitlines(), arguments)

    def test_starting_session_inside_wayland_is_rejected(self):
        env = dict(os.environ, WAYLAND_DISPLAY="wayland-existing")
        result = subprocess.run(["bash", str(ROOT / "packaging/hp-os"), "session"], env=env, capture_output=True)
        self.assertEqual(result.returncode, 1)

    def test_hp_os_session_uses_private_bus_and_owned_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = pathlib.Path(temporary)
            binary = base / "dbus-run-session"
            binary.write_text('#!' + shutil.which('bash') + '\nprintf "%s\\n" "$@" > "$COMMAND_LOG"\nprintf "%s\\n" "$XDG_CURRENT_DESKTOP" "$XDG_SESSION_DESKTOP" "${NIRI_SOCKET-unset}" > "$SESSION_LOG"\n')
            binary.chmod(0o755)
            owned = base / "hp-os-niri"
            existing = base / "niri/config.kdl"
            existing.parent.mkdir()
            existing.write_text('spawn-at-startup "dms"\n')
            env = dict(os.environ, PATH=str(base) + ":" + os.environ["PATH"],
                       HOME=str(base), XDG_CONFIG_HOME=str(base / "config"),
                       COMMAND_LOG=str(base / "args"), SESSION_LOG=str(base / "env"),
                       INIR_NIRI_CONFIG_DIR=str(owned), HP_OS_PACKAGING=str(ROOT / "packaging"),
                       NIRI_SOCKET="existing-session-socket")
            env.pop("WAYLAND_DISPLAY", None)
            packaged_config = base / "dbus/share/dbus-1/session.conf"
            packaged_config.parent.mkdir(parents=True)
            packaged_config.write_text("<busconfig/>")
            runner = base / "hp-os"
            host_config = base / "etc/dbus-1/session.conf"
            runner.write_text((ROOT / "packaging/hp-os").read_text().replace("@dbusSessionConfig@", str(packaged_config)).replace("/etc/dbus-1/session.conf", str(host_config)))
            runner.chmod(0o755)
            subprocess.run(["bash", str(runner), "session"], env=env, check=True)
            self.assertEqual((base / "args").read_text().splitlines(), ["--config-file=" + str(packaged_config), "--", "niri", "--config", str(owned / "config.kdl")])
            self.assertIn("'@dbusSessionConfig@' '${pkgs.dbus}/share/dbus-1/session.conf'", (ROOT / "packaging/package.nix").read_text())
            # NixOS host config takes precedence, avoiding a duplicate listener.
            host_config.parent.mkdir(parents=True)
            host_config.write_text("<busconfig/>")
            runner.chmod(0o755)
            subprocess.run(["bash", str(runner), "session"], env=env, check=True)
            self.assertEqual((base / "args").read_text().splitlines()[0], "--config-file=" + str(host_config))
            self.assertEqual((base / "env").read_text().splitlines(), ["HP-OS:niri", "hp-os", "unset"])
            self.assertEqual(existing.read_text(), 'spawn-at-startup "dms"\n')
            self.assertNotIn('"dms"', (owned / "config.kdl").read_text())
            (owned / "config.kdl").write_text("// existing HP-OS preferences\n")
            subprocess.run(["bash", str(ROOT / "packaging/hp-os"), "session"], env=env, check=True)
            self.assertEqual((owned / "config.kdl").read_text(), "// existing HP-OS preferences\n")

    def test_private_bus_activation_environment_precedes_shell_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = pathlib.Path(temporary)
            runtime = base / "runtime"
            runtime.mkdir()
            (runtime / "shell.qml").write_text("ShellRoot {}")
            log = base / "calls"
            for command in ["dbus-update-activation-environment", "qs", "gdbus"]:
                binary = base / command
                binary.write_text('#!' + shutil.which('bash') + '\nprintf "%s" "' + command + '" >> "$CALL_LOG"\nprintf " <%s>" "$@" >> "$CALL_LOG"\nprintf "\\n" >> "$CALL_LOG"\n')
                if command == "qs":
                    binary.write_text(binary.read_text() + 'printf "%s" "$QS_ICON_THEME" > "$THEME_LOG"\n')
                binary.chmod(0o755)
            env = dict(os.environ, THEME_LOG=str(base / "theme"), PATH=str(base) + ":" + os.environ["PATH"], CALL_LOG=str(log),
                       HP_OS_PACKAGING=str(ROOT / "packaging"), HP_OS_RUNTIME=str(runtime),
                       INIR_CONFIG_DIR=str(base / "config"), INIR_STATE_DIR=str(base / "state"),
                       INIR_CACHE_DIR=str(base / "cache"), HP_OS_OWNED_SESSION="1", DISPLAY=":test")
            subprocess.run(["bash", str(ROOT / "packaging/hp-os"), "run"], env=env, check=True)
            self.assertEqual((base / "theme").read_text(), env.get("QS_ICON_THEME") or "HP-OS")
            lines = log.read_text().splitlines()
            self.assertEqual(lines[0], "dbus-update-activation-environment <WAYLAND_DISPLAY> <XDG_CURRENT_DESKTOP> <XDG_SESSION_DESKTOP> <XDG_SESSION_TYPE> <XDG_RUNTIME_DIR> <NIRI_SOCKET> <DISPLAY>")
            self.assertTrue(lines[-1].startswith("qs "))
            self.assertNotIn("--systemd", log.read_text())
            log.write_text("")
            env.pop("HP_OS_OWNED_SESSION")
            env["QS_ICON_THEME"] = "ExplicitTheme"
            subprocess.run(["bash", str(ROOT / "packaging/hp-os"), "run"], env=env, check=True)
            self.assertNotIn("dbus-update-activation-environment", log.read_text())
            self.assertEqual((base / "theme").read_text(), "ExplicitTheme")

    def test_login_entry_has_hp_os_name(self):
        entry = (ROOT / "packaging/hp-os.desktop").read_text()
        self.assertIn("\nName=HP-OS\n", entry)
        self.assertIn("\nExec=@exec@ session\n", entry)

    def test_first_run_wallpaper_path_and_existing_config_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = pathlib.Path(temporary) / "config.json"
            wallpaper = str(pathlib.Path(temporary) / "wallpaper with spaces.svg")
            command = ["python3", str(ROOT / "packaging/initialize-config.py"), str(ROOT / "packaging/default-config.json"), str(target), wallpaper]
            env = dict(os.environ, INIR_STATE_DIR=str(pathlib.Path(temporary) / "state"))
            subprocess.run(command, env=env, check=True)
            self.assertEqual(json.loads(target.read_text())["background"]["wallpaperPath"], wallpaper)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            target.write_text('{"user": "preferences"}')
            subprocess.run(command, env=env, check=True)
            self.assertEqual(json.loads(target.read_text()), {"user": "preferences"})

    def test_version_metadata_replaces_broken_updater_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            version = directory / "version.json"
            version.write_text("")
            user_config = directory / "config.json"
            user_config.write_text('{"custom":true}')
            subprocess.run(["python3", str(ROOT / "packaging/write-version.py"), temporary], check=True)
            metadata = json.loads(version.read_text())
            self.assertEqual(metadata["version"], "0.1.0")
            self.assertEqual(metadata["upstreamVersion"], "2.33.0")
            self.assertEqual(metadata["updateStrategy"], "package-manager")
            self.assertEqual(metadata["installSource"], "HP-OS")
            self.assertEqual(version.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(user_config.read_text()), {"custom": True})
            self.assertEqual(sorted(p.name for p in directory.iterdir()), ["config.json", "version.json"])

    def test_fresh_config_enables_real_family_panels(self):
        settings = json.loads((ROOT / "packaging/default-config.json").read_text())
        self.assertEqual(settings["panelFamily"], "hpos")
        self.assertIn("irisBar", settings["enabledPanels"])
        self.assertIn("irisNotificationPopup", settings["enabledPanels"])
        self.assertFalse(settings["appearance"]["typography"]["syncWithSystem"])


class SessionLifetimeTests(unittest.TestCase):
    def check_lifetime(self, terminate):
        with tempfile.TemporaryDirectory() as directory:
            pidfile = pathlib.Path(directory) / "detached.pid"
            # Simulate Niri starting a detached shell which ignores TERM.
            sleeper = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)"
            parent = ("import subprocess,sys,time,pathlib; "
                      "p=subprocess.Popen([sys.executable,'-c',sys.argv[2]],start_new_session=True); "
                      "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); "
                      "time.sleep(60 if sys.argv[3]=='wait' else .3)")
            sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
            supervisor = subprocess.Popen([sys.executable, str(ROOT / "packaging/session-supervisor.py"),
                                           sys.executable, "-c", parent, str(pidfile), sleeper,
                                           "wait" if terminate else "exit"])
            detached = None
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertTrue(pidfile.exists(), "compositor child did not start")
                detached = int(pidfile.read_text())
                if terminate:
                    time.sleep(.2)
                    supervisor.terminate()
                self.assertEqual(supervisor.wait(timeout=10), 0)
                self.assertFalse(pathlib.Path(f"/proc/{detached}").exists(), "detached shell was not reaped")
                self.assertIsNone(sentinel.poll(), "unrelated desktop process was stopped")
            finally:
                if supervisor.poll() is None:
                    supervisor.kill()
                supervisor.wait()
                sentinel.terminate()
                sentinel.wait()
                if detached and pathlib.Path(f"/proc/{detached}").exists():
                    os.kill(detached, signal.SIGKILL)

    def test_compositor_exit_reaps_detached_children(self):
        self.check_lifetime(False)

    def test_session_termination_reaps_detached_children(self):
        self.check_lifetime(True)

if __name__ == "__main__":
    unittest.main()
