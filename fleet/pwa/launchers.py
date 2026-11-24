"""Repair Chrome-generated Exec commands where the desktop session lacks Nix PATH."""
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


def desktop_quote(path):
    # Exec quoting is not shell quoting. The Desktop Entry value parser
    # consumes one level of backslash escaping before tokenizing the command.
    escaped = re.sub(r'(["`\\$])', r'\\\1', str(path)).replace("\\", "\\\\")
    return f'"{escaped}"'


def repair(directory, chrome, wrapper, profile):
    if not chrome.is_file():
        return
    prefix = re.compile(r'^Exec=(?:"google-chrome-stable"|google-chrome-stable|'
                        + re.escape(desktop_quote(chrome)) + r')(?=\s)', re.MULTILINE)
    for launcher in directory.glob("chrome-*.desktop"):
        if launcher.is_symlink():
            continue
        try:
            original = launcher.read_text()
            commands = [s for s in original.splitlines() if s.startswith("Exec=")]
            if not any(re.search(r' --app(?:-id)?=', cmd) for cmd in commands):
                continue
            # Preserve separate profiles. For the fleet profile, reuse the
            # desktop browser wrapper so a PWA can also launch Chrome cold.
            managed_argument = "--user-data-dir=" + str(profile)
            managed = any(re.search(r'(?:^|\s)' + re.escape(arg) + r'(?=\s|$)', cmd)
                          for cmd in commands for arg in (managed_argument, desktop_quote(managed_argument)))
            executable = wrapper if managed else chrome
            updated = prefix.sub(lambda _: "Exec=" + desktop_quote(executable), original)
            if updated == original:
                continue
            with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as out:
                temporary = Path(out.name)
                try:
                    out.write(updated)
                    out.flush()
                    os.chmod(temporary, stat.S_IMODE(launcher.stat().st_mode))
                    if launcher.read_text() == original:
                        os.replace(temporary, launcher)
                finally:
                    temporary.unlink(missing_ok=True)
        except FileNotFoundError:
            # Chrome can remove or replace a shortcut during its own updates.
            continue


if __name__ == "__main__":
    repair(*(Path(arg) for arg in sys.argv[1:]))
