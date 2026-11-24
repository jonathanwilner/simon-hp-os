"""Apply Chromium's website darkening to app windows that follow desktop appearance."""
import itertools
import json
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

import websocket


# The shared fleet web-app wrapper uses this loopback-only existing Chrome.
ORIGIN = "127.0.0.1:9222"
http = build_opener(ProxyHandler({}))
request_ids = itertools.count(1)
WINDOW_MODE = """({
  app: ["minimal-ui", "standalone", "window-controls-overlay", "tabbed"].some(
    mode => matchMedia("(display-mode:" + mode + ")").matches),
  fullscreen: matchMedia("(display-mode:fullscreen)").matches,
  dark: matchMedia("(prefers-color-scheme:dark)").matches
})"""


# Chrome preinstalls these apps without desktop shortcuts. Several use normal
# browser tabs by default, where CSS display-mode alone cannot identify them.
CHROME_PREINSTALLED_SCOPES = (
    "https://docs.google.com/document/",
    "https://docs.google.com/spreadsheets/",
    "https://docs.google.com/presentation/",
    "https://chat.google.com/",
    "https://drive.google.com/",
    "https://www.youtube.com/",
)


class Target:
    def __init__(self, target_id):
        self.socket = websocket.create_connection(
            f"ws://{ORIGIN}/devtools/page/{target_id}", suppress_origin=True, timeout=2)
        self.dark = None

    def call(self, method, params):
        serial = next(request_ids)
        self.socket.send(json.dumps({"id": serial, "method": method, "params": params}))
        while True:
            response = json.loads(self.socket.recv())
            if response.get("id") == serial:
                if "error" in response:
                    raise RuntimeError(response["error"]["message"])
                return response["result"]

    def set_mode(self, dark):
        if self.dark != dark:
            # Chrome can cache the launch-time GTK preference on Linux.
            self.call("Emulation.setEmulatedMedia", {"features": [
                {"name": "prefers-color-scheme", "value": "dark" if dark else "light"}]})
            # Blink also darkens web content without native dark styling.
            self.call("Emulation.setAutoDarkModeOverride", {"enabled": dark})
            self.dark = dark

    def close(self):
        self.socket.close(timeout=0)


class Appearance:
    def __init__(self):
        self.sessions = {}
        self.ordinary = {}

    def release(self, target_id):
        target = self.sessions.pop(target_id, None)
        if target:
            target.close()

    def refresh(self, targets, desktop_dark):
        now = time.monotonic()
        by_id = {t["id"]: t for t in targets if re.fullmatch(r"[a-fA-F0-9]{32}", t.get("id", ""))}
        self.ordinary = {key: value for key, value in self.ordinary.items()
                         if key in by_id and value[1] > now and value[0] == by_id[key]["url"]}
        app_modes = {}
        for tid, info in by_id.items():
            if info["type"] != "page" or not info["url"].startswith(("https://", "http://")):
                continue
            if tid in self.ordinary:
                continue
            try:
                target = self.session(tid)
                result = target.call("Runtime.evaluate", {
                    "expression": WINDOW_MODE, "returnByValue": True})["result"].get("value", {})
                preinstalled = info["url"].startswith(CHROME_PREINSTALLED_SCOPES)
                if preinstalled or result.get("app") or (result.get("fullscreen") and target.dark is not None):
                    dark = desktop_dark if desktop_dark is not None else result["dark"]
                    target.set_mode(dark)
                    app_modes[tid] = dark
                else:
                    self.ordinary[tid] = (info["url"], now + 30)
            except (OSError, ValueError, RuntimeError, websocket.WebSocketException):
                self.release(tid)

        # Office editors, Gmail panes and similar cross-origin frames have
        # independent renderers. Resolve their ancestry before applying a mode.
        pending = {tid: info["parentId"] for tid, info in by_id.items()
                   if info["type"] == "iframe" and info.get("parentId")}
        while pending:
            children = [(tid, app_modes[parent]) for tid, parent in pending.items() if parent in app_modes]
            if not children:
                break
            for tid, dark in children:
                del pending[tid]
                app_modes[tid] = dark
                try:
                    self.session(tid).set_mode(dark)
                except (OSError, ValueError, RuntimeError, websocket.WebSocketException):
                    self.release(tid)
        for tid in self.sessions.keys() - app_modes.keys():
            self.release(tid)

    def session(self, target_id):
        if target_id not in self.sessions:
            self.sessions[target_id] = Target(target_id)
        return self.sessions[target_id]


def portal_scheme(gdbus):
    try:
        value = subprocess.check_output([
            gdbus, "call", "--session", "--dest", "org.freedesktop.portal.Desktop",
            "--object-path", "/org/freedesktop/portal/desktop", "--method",
            "org.freedesktop.portal.Settings.Read", "org.freedesktop.appearance",
            "color-scheme"], stderr=subprocess.DEVNULL, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"uint32 ([012])", value)
    return match.group(1) == "1" if match else None


def main():
    appearance = Appearance()
    while True:
        try:
            with http.open(f"http://{ORIGIN}/json/list", timeout=2) as response:
                targets = json.load(response)
        except (OSError, URLError, ValueError):
            targets = []
        appearance.refresh(targets, portal_scheme(sys.argv[1]) if targets else None)
        time.sleep(5 if targets else 15)


if __name__ == "__main__":
    main()
