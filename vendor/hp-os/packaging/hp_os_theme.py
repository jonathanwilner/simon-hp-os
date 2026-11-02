"""Shared native application appearance files."""
import os
from pathlib import Path
import tempfile

def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        stream.write(text)
        temporary = stream.name
    os.replace(temporary, path)


def set_kde_color_scheme(path, scheme):
    # KConfig files can contain nested groups, localized keys, and bare flags.
    # Update only this key so those values and comments survive unchanged.
    lines = path.read_text().splitlines(keepends=True) if path.exists() else []
    start = next((i for i, line in enumerate(lines)
                  if line.strip() == '[General]'), None)
    if start is None:
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        lines.extend(['[General]\n', f'ColorScheme={scheme}\n'])
    else:
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].lstrip().startswith('[')), len(lines))
        keys = [i for i in range(start + 1, end)
                if lines[i].partition('=')[0].strip() == 'ColorScheme']
        if keys:
            for i in keys:
                lines[i] = f'ColorScheme={scheme}\n'
        else:
            if end and not lines[end - 1].endswith('\n'):
                lines[end - 1] += '\n'
            lines.insert(end, f'ColorScheme={scheme}\n')
    atomic_write(path, ''.join(lines))


def apply_files_palette(path, assets, mode):
    source = assets / ('kdeglobals-dark' if mode == 'dark' else 'kdeglobals')
    groups = {}
    group = ''
    for line in source.read_text().splitlines(keepends=True):
        if line.startswith('['):
            group = line.strip()
        if group.startswith(('[Colors:', '[ColorEffects:')) or group == '[WM]':
            groups.setdefault(group, []).append(line)
    lines = []
    group = ''
    for line in path.read_text().splitlines(keepends=True):
        if line.startswith('['):
            group = line.strip()
        if group not in groups:
            lines.append(line)
    text = ''.join(lines)
    if text and not text.endswith('\n'):
        text += '\n'
    atomic_write(path, text + ''.join(''.join(lines) for lines in groups.values()))
    set_kde_color_scheme(path, 'HP-OS-Files-Dark' if mode == 'dark' else 'HP-OS-Files')
