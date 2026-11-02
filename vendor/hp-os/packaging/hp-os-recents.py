#!@python@
"""Read desktop recent files and maintain private HP-OS application history."""
import argparse
import configparser
from datetime import datetime
import fcntl
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

MAX_BYTES = 8 * 1024 * 1024
APP_ID = re.compile(r"[A-Za-z0-9_.-]{1,255}\Z")


def state_path():
    base = Path(os.environ.get("INIR_STATE_DIR", str(Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "hp-os")))
    return base / "start-menu-apps.json"


def timestamp(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        try:
            number = datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (ValueError, OverflowError, OSError):
            return 0.0
    return number if math.isfinite(number) and number >= 0 else 0.0


def read_apps(path):
    try:
        if path.stat().st_size > MAX_BYTES:
            return []
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    entries = data.get("apps", []) if isinstance(data, dict) else []
    if not isinstance(entries, list):
        return []
    result = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        app_id = entry.get("id")
        used = timestamp(entry.get("lastUsed"))
        if isinstance(app_id, str) and APP_ID.fullmatch(app_id) and used:
            result[app_id] = max(result.get(app_id, 0), used)
    return [{"id": key, "lastUsed": value} for key, value in sorted(result.items(), key=lambda item: (-item[1], item[0]))[:100]]


def observe_app(app_id):
    if not APP_ID.fullmatch(app_id):
        raise ValueError("Invalid desktop application ID")
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        apps = [entry for entry in read_apps(path) if entry["id"] != app_id]
        apps.insert(0, {"id": app_id, "lastUsed": time.time()})
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                json.dump({"version": 1, "apps": apps[:100]}, output, allow_nan=False)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


def local_file(url, modified, mime=""):
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "file" or parsed.netloc not in ("", "localhost") or parsed.query or parsed.fragment:
            return None
        path = Path(unquote(parsed.path))
        if not path.is_absolute() or not path.is_file():
            return None
        return {"url": path.as_uri(), "path": str(path), "name": path.name,
                "mime": mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "modified": timestamp(modified)}
    except (OSError, ValueError):
        return None


def recent_files(limit):
    data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    entries = []
    xbel = data_home / "recently-used.xbel"
    try:
        if xbel.stat().st_size <= MAX_BYTES:
            tree = ET.fromstring(xbel.read_bytes())
            for bookmark in tree.iter("bookmark"):
                modified = max((timestamp(bookmark.get(key)) for key in ("modified", "visited", "added")), default=0)
                mime = next((node.get("type", "") for node in bookmark.iter() if node.tag.rsplit("}", 1)[-1] == "mime-type"), "")
                entry = local_file(bookmark.get("href", ""), modified, mime)
                if entry:
                    entries.append(entry)
    except (OSError, ET.ParseError, ValueError):
        pass
    recent_dir = data_home / "RecentDocuments"
    try:
        candidates = []
        for path in recent_dir.glob("*.desktop"):
            try:
                stat = path.stat()
                if stat.st_size <= MAX_BYTES:
                    candidates.append((stat.st_mtime, path))
            except OSError:
                continue
        for modified, path in sorted(candidates, reverse=True)[:400]:
            config = configparser.ConfigParser(interpolation=None, strict=False)
            config.optionxform = str
            try:
                config.read(path, encoding="utf-8")
                group = config["Desktop Entry"]
                if group.get("Type") != "Link":
                    continue
                url = group.get("URL", group.get("URL[$e]", ""))
                # KDE's expanded form commonly uses HOME. No shell execution.
                url = url.replace("${HOME}", str(Path.home())).replace("$HOME", str(Path.home()))
                entry = local_file(url, modified, group.get("MimeType", "").rstrip(";"))
                if entry:
                    entries.append(entry)
            except (OSError, UnicodeError, configparser.Error, KeyError, ValueError):
                continue
    except OSError:
        pass
    unique = {}
    for entry in entries:
        key = os.path.realpath(entry["path"])
        if key not in unique or entry["modified"] > unique[key]["modified"]:
            unique[key] = entry
    return sorted(unique.values(), key=lambda entry: (-entry["modified"], entry["path"]))[:limit]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--limit", type=int, default=8)
    observer = commands.add_parser("observe-app")
    observer.add_argument("id")
    args = parser.parse_args()
    if args.command == "observe-app":
        try:
            observe_app(args.id)
        except (ValueError, OSError) as error:
            parser.exit(1, str(error) + "\n")
    else:
        limit = max(0, min(args.limit, 100))
        print(json.dumps({"files": recent_files(limit), "apps": read_apps(state_path())[:limit]}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
