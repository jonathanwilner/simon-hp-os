#!/usr/bin/env python3
"""Keep detached compositor children inside one Linux login lifetime."""
import ctypes
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def descendants():
    """Subreaper adoption retains ancestry even when Niri's children setsid()."""
    parents = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            # comm can contain spaces and parentheses. Fields after its final )
            # begin with state, then PPID.
            parents[int(path.parent.name)] = int(path.read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
    owned = {os.getpid()}
    while True:
        expanded = owned | {pid for pid, parent in parents.items() if parent in owned}
        if expanded == owned:
            return owned - {os.getpid()}
        owned = expanded


def signal_children(signum):
    for pid in descendants():
        try:
            # A pidfd prevents a PID reused after this lookup from being killed.
            fd = os.pidfd_open(pid)
            try:
                if pid in descendants():
                    signal.pidfd_send_signal(fd, signum)
            finally:
                os.close(fd)
        except ProcessLookupError:
            pass


def reap():
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                return
        except ChildProcessError:
            return


def main(argv):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Cannot supervise session descendants')
    class SessionStop(Exception):
        pass

    def stop(_signum, _frame):
        raise SessionStop()

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    try:
        child = subprocess.Popen(argv)
        rc = child.wait()
    except SessionStop:
        rc = 0
    finally:
        # Repeated logout signals must not interrupt bounded cleanup.
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        signal_children(signal.SIGTERM)
        deadline = time.monotonic() + 3
        while descendants() and time.monotonic() < deadline:
            reap()
            time.sleep(0.05)
        signal_children(signal.SIGKILL)
        deadline = time.monotonic() + 2
        while descendants() and time.monotonic() < deadline:
            reap()
            time.sleep(0.05)
        reap()
    return rc if rc >= 0 else 128 - rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
