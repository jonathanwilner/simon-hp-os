#!/usr/bin/env python3
import argparse
import json
import os
import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def atomic_write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def append_event(path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True))
        handle.write("\n")


def load_existing(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main():
    parser = argparse.ArgumentParser(description="Record nom-tmux build dashboard metadata.")
    parser.add_argument("--metadata-file", required=True)
    parser.add_argument("--events-file", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--safe-session", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--host", default=socket.gethostname().split(".")[0])
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--exit-code", default="")
    args = parser.parse_args()

    metadata_path = Path(args.metadata_file)
    event_path = Path(args.events_file)
    now = now_iso()
    existing = load_existing(metadata_path)
    started_at = existing.get("started_at") or now
    finished_at = existing.get("finished_at")
    exit_code = existing.get("exit_code")

    if args.exit_code != "":
        try:
            exit_code = int(args.exit_code)
        except ValueError:
            exit_code = args.exit_code
        finished_at = now

    record = {
        "version": 1,
        "host": args.host,
        "session": args.session,
        "safe_session": args.safe_session,
        "phase": args.phase,
        "cwd": args.cwd,
        "command": args.command,
        "log_file": args.log_file,
        "status_file": args.status_file,
        "metadata_file": str(metadata_path),
        "started_at": started_at,
        "updated_at": now,
        "finished_at": finished_at,
        "exit_code": exit_code,
    }

    event = {
        "time": now,
        "host": args.host,
        "session": args.session,
        "safe_session": args.safe_session,
        "phase": args.phase,
        "exit_code": exit_code,
    }

    atomic_write_json(metadata_path, record)
    append_event(event_path, event)


if __name__ == "__main__":
    main()
