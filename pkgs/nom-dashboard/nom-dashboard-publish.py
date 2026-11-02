#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from nom_dashboard_progress import resolve as resolve_progress
from nom_dashboard_feed import publish_dashboard


ANSI_RE = re.compile(rb"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|P[^\x1b]*(?:\x1b\\))")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SECRET_REPLACEMENTS = [
    (re.compile(r"(/run/agenix/)[A-Za-z0-9_.@/+:-]+"), r"\1REDACTED"),
    (re.compile(r"(?i)(token|secret|password|pass|key)=([^ \n\r\t]+)"), r"\1=REDACTED"),
    (re.compile(r"(?i)(--(?:token|password|secret|key)\s+)([^ \n\r\t]+)"), r"\1REDACTED"),
]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_name(value):
    safe = re.sub(r"[^A-Za-z0-9_.@+-]+", "_", value.strip())
    return safe[:160] or "session"


def atomic_write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def atomic_write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_tail(path, max_bytes):
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(max(0, size - max_bytes))
                data = handle.read()
                marker = f"[dashboard] showing last {max_bytes} bytes of {size} bytes\n".encode()
                data = marker + data
            else:
                data = handle.read()
    except FileNotFoundError:
        return ""

    data = ANSI_RE.sub(b"", data)
    text = data.decode("utf-8", errors="replace")
    text = CONTROL_RE.sub("", text)
    for pattern, replacement in SECRET_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def parse_log_preamble(path):
    details = {}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(12):
                line = handle.readline()
                if not line:
                    break
                clean = ANSI_RE.sub(b"", line.encode("utf-8", "replace")).decode("utf-8", "replace")
                if clean.startswith("[nom-tmux] session="):
                    details["session"] = clean.split("=", 1)[1].strip()
                elif clean.startswith("[nom-tmux] cwd="):
                    details["cwd"] = clean.split("=", 1)[1].strip()
                elif clean.startswith("[nom-tmux] command="):
                    details["command"] = clean.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return details


def infer_status(state_dir, safe, metadata, log_path):
    status_path = Path(metadata.get("status_file") or state_dir / f"{safe}.status")
    exit_code = metadata.get("exit_code")
    if status_path.exists():
        raw = status_path.read_text(encoding="utf-8", errors="replace").strip()
        if exit_code is None:
            try:
                exit_code = int(raw)
            except ValueError:
                exit_code = raw
        return ("succeeded" if exit_code == 0 else "failed", exit_code)
    if metadata.get("phase") == "finished":
        return ("succeeded" if exit_code == 0 else "failed", exit_code)
    if log_path.exists():
        return ("running", None)
    return ("unknown", exit_code)


def collect_sessions(state_dir, output_dir, host, max_log_bytes):
    state_dir = Path(state_dir).expanduser()
    machine_dir = Path(output_dir) / "machines" / host
    logs_dir = machine_dir / "logs"
    sessions_dir = machine_dir / "sessions"
    logs_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    candidates = {}
    for log_path in state_dir.glob("*.log"):
        candidates[log_path.stem] = log_path
    for meta_path in state_dir.glob("*.json"):
        if meta_path.name.endswith((".events.jsonl", ".progress.json")):
            continue
        candidates.setdefault(meta_path.stem, state_dir / f"{meta_path.stem}.log")

    sessions = []
    for safe, log_path in sorted(candidates.items()):
        meta_path = state_dir / f"{safe}.json"
        metadata = load_json(meta_path)
        preamble = parse_log_preamble(log_path)
        session_name = metadata.get("session") or preamble.get("session") or safe
        safe_session = metadata.get("safe_session") or safe_name(session_name)
        command = metadata.get("command") or preamble.get("command") or ""
        cwd = metadata.get("cwd") or preamble.get("cwd") or ""
        status, exit_code = infer_status(state_dir, safe, metadata, log_path)
        updated_ts = max(
            [p.stat().st_mtime for p in [log_path, meta_path] if p.exists()] or [datetime.now().timestamp()]
        )
        updated_at = datetime.fromtimestamp(updated_ts, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        log_text = read_tail(log_path, max_log_bytes)
        log_name = f"{safe_session}.txt"
        atomic_write_text(logs_dir / log_name, log_text)

        record = {
            "host": host,
            "session": session_name,
            "safe_session": safe_session,
            "status": status,
            "exit_code": exit_code,
            "command": command,
            "cwd": cwd,
            "started_at": metadata.get("started_at"),
            "updated_at": metadata.get("updated_at") or updated_at,
            "finished_at": metadata.get("finished_at"),
            "log_url": f"machines/{host}/logs/{log_name}",
            "bytes_published": len(log_text.encode("utf-8")),
        }
        progress = resolve_progress(load_json(state_dir / f"{safe}.progress.json"))
        if progress:
            record["progress"] = progress
        atomic_write_json(sessions_dir / f"{safe_session}.json", record)
        sessions.append(record)

    sessions.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    machine_manifest = {
        "version": 1,
        "host": host,
        "generated_at": now_iso(),
        "sessions": sessions,
        "totals": {
            "running": sum(1 for item in sessions if item["status"] == "running"),
            "failed": sum(1 for item in sessions if item["status"] == "failed"),
            "succeeded": sum(1 for item in sessions if item["status"] == "succeeded"),
            "unknown": sum(1 for item in sessions if item["status"] == "unknown"),
        },
    }
    atomic_write_json(machine_dir / "manifest.json", machine_manifest)
    return machine_manifest


def copy_assets(asset_dir, output_dir):
    if not asset_dir:
        return
    asset_dir = Path(asset_dir)
    output_dir = Path(output_dir)
    for name in ["index.html", "app.js", "styles.css"]:
        src = asset_dir / name
        if src.exists():
            shutil.copyfile(src, output_dir / name)


def aggregate(output_dir):
    output_dir = Path(output_dir)
    machines = []
    for manifest_path in sorted((output_dir / "machines").glob("*/manifest.json")):
        manifest = load_json(manifest_path)
        if manifest:
            machines.append(manifest)
    root = {
        "version": 1,
        "generated_at": now_iso(),
        "machines": machines,
        "totals": {
            "running": sum(m.get("totals", {}).get("running", 0) for m in machines),
            "failed": sum(m.get("totals", {}).get("failed", 0) for m in machines),
            "succeeded": sum(m.get("totals", {}).get("succeeded", 0) for m in machines),
            "unknown": sum(m.get("totals", {}).get("unknown", 0) for m in machines),
        },
    }
    atomic_write_json(output_dir / "manifest.json", root)
    publish_dashboard(output_dir, root)


def main():
    parser = argparse.ArgumentParser(description="Publish nom-tmux state as a static dashboard feed.")
    parser.add_argument("--state-dir", default=str(Path.home() / ".local/state/nixos-intc/nom-tmux"))
    parser.add_argument("--output-dir", default=str(Path.home() / ".local/state/nixos-intc/nom-dashboard/public"))
    parser.add_argument("--host", default=socket.gethostname().split(".")[0])
    parser.add_argument("--max-log-bytes", type=int, default=600_000)
    parser.add_argument("--asset-dir", default="")
    parser.add_argument("--aggregate-only", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    copy_assets(args.asset_dir, output_dir)
    global_dashboard = output_dir / "dashboard"
    global_dashboard.mkdir(parents=True, exist_ok=True)
    copy_assets(args.asset_dir, global_dashboard)
    entry = global_dashboard / "index.html"
    if entry.exists():
        atomic_write_text(output_dir / "dashboard.html", entry.read_text()
                          .replace('href="styles.css"', 'href="dashboard/styles.css"')
                          .replace('src="app.js"', 'src="dashboard/app.js"'))
    # Machine-local previews survive a central host running an older publisher.
    if not args.aggregate_only:
        preview = output_dir / "machines" / args.host / "dashboard"
        preview.mkdir(parents=True, exist_ok=True)
        copy_assets(args.asset_dir, preview)
    if not args.aggregate_only:
        collect_sessions(args.state_dir, output_dir, args.host, args.max_log_bytes)
    aggregate(output_dir)


if __name__ == "__main__":
    main()
