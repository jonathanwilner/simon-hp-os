#!/usr/bin/env python3
"""Explicit task/phase counters and conservative aria2 download accounting."""
import argparse
import json
import math
import os
from pathlib import Path
import struct
import tempfile
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalized(value):
    if not isinstance(value, dict):
        return None
    completed, total = value.get("completed"), value.get("total")
    if isinstance(completed, bool) or isinstance(total, bool):
        return None
    if not isinstance(completed, (int, float)) or not isinstance(total, (int, float)):
        return None
    if not math.isfinite(completed) or not math.isfinite(total) or total <= 0:
        return None
    completed = max(0, min(completed, total))
    return {"completed": completed, "total": total,
            "percent": completed / total * 100,
            "unit": value.get("unit", "items"),
            "label": value.get("label", "Task progress"),
            "scope": value.get("scope", "task"),
            "updated_at": value.get("updated_at")}


def aria2_completed(control, expected_size):
    """Read v1 control file's saved complete-piece bitmap; ignore in-flight blocks.

    Layout: aria2 src/DefaultBtProgressInfoFile.cc save(). File length alone
    overcounts sparse parallel downloads. Unknown/truncated state counts zero.
    """
    try:
        with control.open("rb") as stream:
            header = stream.read(10)
            version, extension, hash_length = struct.unpack(">HII", header)
            if version != 1 or extension != 0 or hash_length != 0:
                return 0
            piece_size, total, uploaded, bitmap_length = struct.unpack(">IQQI", stream.read(24))
            if not piece_size or total != expected_size:
                return 0
            pieces = (total + piece_size - 1) // piece_size
            if bitmap_length != (pieces + 7) // 8 or bitmap_length > 16_000_000:
                return 0
            bitmap = stream.read(bitmap_length)
            if len(bitmap) != bitmap_length:
                return 0
            return sum(min(piece_size, total - i * piece_size)
                       for i in range(pieces) if bitmap[i // 8] & (128 >> (i % 8)))
    except (OSError, struct.error):
        return 0


def download_progress(manifest_path, root):
    manifest = json.loads(Path(manifest_path).read_text())
    completed = total = 0
    for model in manifest["models"]:
        for entry in model["files"]:
            size = entry["size"]
            if not isinstance(size, int) or size <= 0:
                raise ValueError("Manifest file size must be a positive integer")
            relative = Path(model["directory"]) / entry["path"]
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Manifest paths must stay within the download root")
            path = Path(root) / relative
            total += size
            try:
                if path.stat().st_size == size:
                    completed += size
                    continue
            except FileNotFoundError:
                pass
            partial = path.with_suffix(path.suffix + ".aria2.partial")
            if partial.exists():
                completed += aria2_completed(Path(str(partial) + ".aria2"), size)
    return {"completed": completed, "total": total, "unit": "bytes"}


def resolve(value):
    if not isinstance(value, dict):
        return None
    source = value.get("source") or {}
    if not isinstance(source, dict):
        return None
    if source.get("kind") == "model-manifest":
        try:
            value = {**value, **download_progress(value["source"]["manifest"], value["source"]["root"]),
                     "updated_at": now_iso()}
        except (OSError, ValueError, KeyError, TypeError):
            return None
    return normalized(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=os.environ.get("NOM_DASHBOARD_PROGRESS_FILE"))
    parser.add_argument("--completed", type=float)
    parser.add_argument("--total", type=float)
    parser.add_argument("--unit", default="items")
    parser.add_argument("--label", default="Task progress")
    parser.add_argument("--scope", choices=["task", "phase"], default="task")
    parser.add_argument("--download-manifest")
    parser.add_argument("--download-root")
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    if not args.file:
        parser.error("--file or NOM_DASHBOARD_PROGRESS_FILE is required")
    path = Path(args.file)
    if args.clear:
        path.unlink(missing_ok=True)
        return
    value = {"label": args.label, "scope": args.scope, "unit": args.unit, "updated_at": now_iso()}
    if args.download_manifest and args.download_root:
        value["source"] = {"kind": "model-manifest", "manifest": str(Path(args.download_manifest).resolve()),
                           "root": str(Path(args.download_root).resolve())}
    elif args.completed is not None and args.total is not None:
        value.update(completed=args.completed, total=args.total)
    else:
        parser.error("Provide counters or both download paths")
    if resolve(value) is None:
        parser.error("Progress requires readable input and a finite positive total")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".progress-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, allow_nan=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
