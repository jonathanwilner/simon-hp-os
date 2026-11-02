#!/usr/bin/env python3
"""Own the writable Niri HDR include used by Goran's DMS extension."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

OUTPUT = "eDP-1"
DEFAULT_WHITE = 500
MIN_WHITE = 100
MAX_WHITE = 500
HEADER = "// Managed by goran-hdr. Change HDR through the DMS extension."


class ControlError(Exception):
    pass


def config_path():
    override = os.environ.get("GORAN_HDR_CONFIG")
    if override:
        return Path(override).absolute()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return config_home / "niri" / "hdr.kdl"


def white_value(value):
    if not re.fullmatch(r"[0-9]+", value):
        raise argparse.ArgumentTypeError("desktop white must be an integer from 100 to 500")
    value = int(value)
    if not MIN_WHITE <= value <= MAX_WHITE:
        raise argparse.ArgumentTypeError("desktop white must be from 100 to 500 cd/m²")
    return value


def state(enabled, white):
    return {"enabled": enabled, "reference_luminance": white, "output": OUTPUT}


def render(value):
    lines = [HEADER, f"// reference-luminance: {value['reference_luminance']}", f'output "{OUTPUT}" {{']
    if value["enabled"]:
        lines += ['    hdr mode="on" {', f"        reference-luminance {value['reference_luminance']}", "    }"]
    return "\n".join(lines + ["}", ""])


def read_state(path):
    if path.is_symlink():
        raise ControlError("HDR include must be a writable file, not a symlink")
    try:
        if path.stat().st_size > 16384:
            raise ControlError("HDR include is too large")
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ControlError("HDR include is missing; run goran-hdr init") from exc
    match = re.fullmatch(
        re.escape(HEADER) + r'\n// reference-luminance: ([0-9]+)\noutput "eDP-1" \{\n'
        r'(?:    hdr mode="on" \{\n        reference-luminance ([0-9]+)\n    \}\n)?\}\n',
        content,
    )
    if not match:
        raise ControlError("HDR include is not in the owned format; run goran-hdr reset to restore it")
    white = int(match[1])
    if not MIN_WHITE <= white <= MAX_WHITE or (match[2] is not None and int(match[2]) != white):
        raise ControlError("HDR include has an invalid desktop white value")
    return state(match[2] is not None, white)


def write_state(path, value):
    if path.is_symlink():
        raise ControlError("HDR include must be a writable file, not a symlink")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".hdr-candidate-", suffix=".kdl", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(render(value))
            handle.flush()
            os.fsync(handle.fileno())
        binary = os.environ.get("NIRI_BINARY", "niri")
        try:
            validation = subprocess.run([binary, "validate", "--config", str(temporary)],
                                        text=True, capture_output=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ControlError(f"Niri validation could not run: {exc}") from exc
        if validation.returncode:
            detail = (validation.stderr or validation.stdout).strip()[:1200]
            raise ControlError(f"Niri rejected the HDR configuration: {detail or 'validation failed'}")
        # The old include remains in place until the complete candidate has passed validation.
        os.replace(temporary, path)
        temporary = None
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "status", "reset"):
        commands.add_parser(command)
    set_parser = commands.add_parser("set")
    set_parser.add_argument("mode", choices=("on", "off"))
    set_parser.add_argument("white", nargs="?", type=white_value,
                            help="desktop white in cd/m²; preserve the saved value when omitted")
    arguments = parser.parse_args(argv)
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # A separate stable inode serializes writers even when the include is atomically replaced.
        lock_fd = os.open(path.with_name(path.name + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if arguments.command == "reset" or (arguments.command == "init" and not path.exists() and not path.is_symlink()):
                value = state(True, DEFAULT_WHITE)
                write_state(path, value)
            else:
                value = read_state(path)
                if arguments.command == "set":
                    value = state(arguments.mode == "on", arguments.white if arguments.white is not None else value["reference_luminance"])
                    write_state(path, value)
        print(json.dumps(value))
        return 0
    except (ControlError, OSError, UnicodeError) as exc:
        print(f"goran-hdr: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
