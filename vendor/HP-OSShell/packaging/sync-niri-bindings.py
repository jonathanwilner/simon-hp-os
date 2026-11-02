#!/usr/bin/env python3
"""Synchronize only Niri bindings; reject syntax we cannot safely interpret."""
import argparse
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


@dataclass
class Token:
    value: str
    start: int
    end: int
    quoted: bool = False


def tokens(text):
    out, i = [], 0
    while i < len(text):
        start = i
        if text[i] in ' \t\r':
            i += 1
            continue
        if text.startswith('//', i):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
            continue
        if text.startswith('/*', i):
            depth, i = 1, i + 2
            while depth and i < len(text):
                if text.startswith('/*', i): depth, i = depth + 1, i + 2
                elif text.startswith('*/', i): depth, i = depth - 1, i + 2
                else: i += 1
            if depth: raise ValueError('Unterminated block comment')
            continue
        if text[i] == '\\':
            continuation = re.match(r'\\[ \t\r]*(?://[^\n]*)?\n', text[i:])
            if not continuation: raise ValueError('Invalid KDL line continuation')
            i += continuation.end()
            continue
        if text.startswith('/-', i):
            out.append(Token('/-', i, i + 2))
            i += 2
            continue
        raw = re.match(r'(?:r(#{0,})|(#+))"', text[i:])
        if raw:
            hashes = raw.group(1) if raw.group(1) is not None else raw.group(2)
            content = i + raw.end()
            end = text.find('"' + hashes, content)
            if end < 0: raise ValueError('Unterminated KDL raw string')
            i = end + 1 + len(hashes)
            out.append(Token(text[content:end], start, i, True))
            continue
        if text[i] == '"':
            i += 1
            while i < len(text):
                if text[i] == '\\': i += 2
                elif text[i] == '"':
                    i += 1
                    break
                else: i += 1
            else: raise ValueError('Unterminated quoted string')
            value = json.loads(text[start:i])
        elif text[i] in '{};\n=':
            value, i = text[i], i + 1
        else:
            while i < len(text) and text[i] not in ' \t\r\n{};="':
                if text.startswith('//', i) or text.startswith('/*', i) or text.startswith('/-', i): break
                i += 1
            if i == start: raise ValueError('Unsupported KDL token')
            value = text[start:i]
        out.append(Token(value, start, i, text[start] == '"'))
    return out


@dataclass
class Node:
    head: list
    children: list
    start: int
    end: int


def nodes(text):
    ts = tokens(text)
    def delimiter(token, values):
        return not token.quoted and token.value in values
    def parse(i, nested=False):
        result = []
        while i < len(ts):
            if delimiter(ts[i], (';', '\n')):
                i += 1
                continue
            if delimiter(ts[i], ('}',)):
                if not nested: raise ValueError('Unexpected closing brace')
                return result, i + 1
            disabled = delimiter(ts[i], ('/-',))
            if disabled:
                i += 1
                while i < len(ts) and delimiter(ts[i], ('\n',)): i += 1
                if i == len(ts): raise ValueError('Missing disabled node')
            start, head, children = ts[i].start, [], []
            while i < len(ts) and not delimiter(ts[i], ('{', '}', ';', '\n')):
                if delimiter(ts[i], ('/-',)):
                    # An entry comment removes one argument or key=value pair.
                    i += 1
                    if i == len(ts) or delimiter(ts[i], ('{', '}', ';', '\n', '/-')):
                        raise ValueError('Unsupported disabled KDL entry')
                    i += 1
                    if i < len(ts) and delimiter(ts[i], ('=',)):
                        i += 1
                        if i == len(ts) or delimiter(ts[i], ('{', '}', ';', '\n', '/-', '=')):
                            raise ValueError('Missing disabled property value')
                        i += 1
                    continue
                head.append(ts[i]); i += 1
            if not head: raise ValueError('Missing KDL node name')
            end = head[-1].end
            if i < len(ts) and delimiter(ts[i], ('{',)):
                children, i = parse(i + 1, True)
                end = ts[i - 1].end
                if i < len(ts) and not delimiter(ts[i], (';', '\n', '}')):
                    raise ValueError('Missing node separator')
            if not disabled: result.append(Node(head, children, start, end))
        if nested: raise ValueError('Unclosed block')
        return result, i
    return parse(0)[0]


def signature(text):
    return [(t.quoted, t.value) for t in tokens(text) if t.quoted or t.value not in (';', '\n')]


def key(node):
    parts = node.head[0].value.split('+')
    return '+'.join(sorted(x.casefold() for x in parts[:-1]) + [parts[-1].casefold()])


def adapt(text):
    """Translate recognized DMS IPC actions, preserving every other command."""
    binding = nodes(text)[0]
    edits = []
    for action in binding.children:
        values = [t.value for t in action.head]
        if values[0] == 'spawn' and len(values) >= 2:
            executable = Path(values[1]).name
            if executable == 'vnc-safe-spawn':
                if len(values) < 3 or values[2].startswith('-'):
                    raise ValueError('Unsupported vnc-safe-spawn arguments')
                # Preserve the exact underlying app and arguments; this wrapper
                # is specific to the regular session and may not be installed.
                values = ['spawn', *values[2:]]
                executable = Path(values[1]).name
                edits.append((action.start, action.end, 'spawn ' + ' '.join(json.dumps(v) for v in values[1:])))
            if executable in ('lock-screen', 'niri-shutdown'):
                if len(values) != 2: raise ValueError('Unsupported session helper arguments')
                replacement = 'quit' if executable == 'niri-shutdown' else 'spawn "hp-os" "ipc" "lock" "activate"'
                if edits and edits[-1][:2] == (action.start, action.end): edits.pop()
                edits.append((action.start, action.end, replacement))
                continue
        dms = any(Path(v).name in ('dms', 'dms-shell') or re.search(r'\bdms(?:-shell)?\s', v) for v in values)
        if not dms: continue
        if values[0] != 'spawn' or len(values) < 2 or Path(values[1]).name not in ('dms', 'dms-shell'):
            raise ValueError('Unsupported DMS shell command in binding')
        mapping = {
            ('ipc', 'call', 'spotlight', 'toggle'): ('overview', 'toggle'),
            ('ipc', 'call', 'lock', 'lock'): ('lock', 'activate'),
            ('ipc', 'call', 'lock', 'activate'): ('lock', 'activate'),
            ('ipc', 'call', 'wallhaven', 'toggle'): ('wallpaperSelector', 'toggle'),
            ('ipc', 'call', 'wallhavenCarousel', 'discover'): ('wallpaperSelector', 'toggle'),
        }
        command = mapping.get(tuple(values[2:]))
        if command is None: raise ValueError('Unknown DMS IPC action: ' + repr(values[2:]))
        replacement = 'spawn ' + ' '.join(json.dumps(v) for v in ('hp-os', 'ipc', *command))
        if edits and edits[-1][:2] == (action.start, action.end): edits.pop()
        edits.append((action.start, action.end, replacement))
    for start, end, replacement in reversed(edits): text = text[:start] + replacement + text[end:]
    return text.replace('DMS Launcher', 'HP-OS Launcher') if edits else text


def bindings(path, stack=(), adapt_shell=False):
    path = path.expanduser().absolute()
    identity = path.resolve()
    if identity in stack: raise ValueError('Include cycle: ' + str(path))
    text = path.read_text()
    result = {}
    for node in nodes(text):
        name = node.head[0].value
        if name == 'include':
            args = [t.value for t in node.head[1:]]
            optional = False
            if len(args) == 4 and args[:3] == ['optional', '=', 'true']:
                optional, args = True, args[3:]
            elif len(args) == 4 and args[1:] == ['optional', '=', 'true']:
                optional, args = True, args[:1]
            if len(args) != 1 or node.children: raise ValueError('Unsupported include')
            included = Path(args[0]).expanduser()
            if not included.is_absolute(): included = path.parent / included
            if optional and not included.exists(): continue
            added = bindings(included, (*stack, identity), adapt_shell)
        elif name == 'binds':
            if len(node.head) != 1: raise ValueError('Unsupported binds header')
            added = {}
            for binding in node.children:
                k = key(binding)
                if k in added: raise ValueError('Duplicate binding: ' + k)
                value = text[binding.start:binding.end]
                added[k] = adapt(value) if adapt_shell else value
        else:
            continue
        if result.keys() & added.keys(): raise ValueError('Duplicate binding across blocks/includes in ' + str(path) + ': ' + ', '.join(sorted(result.keys() & added.keys())))
        result.update(added)
    return result


def atomic(path, data, mode=0o600):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def sync(source, target, baseline, niri='niri'):
    if not source.exists() or not target.exists():
        print('Skipping bindings sync: source or target does not exist')
        return
    # Serialize competing session-start and Home Manager hooks.
    with target.with_suffix(target.suffix + '.bindings.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = target.read_text()
        target_nodes = nodes(original)
        blocks = [n for n in target_nodes if n.head[0].value == 'binds']
        current = bindings(target)
        inline = {key(b) for block in blocks for b in block.children}
        if set(current) != inline:
            raise ValueError('HP-OS target has bindings in includes; refusing to modify included files')
        defaults = bindings(baseline)
        state_path = target.with_suffix(target.suffix + '.bindings-state.json')
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        if state is not None and (not isinstance(state, dict) or state.get('version') != 1
                                  or not isinstance(state.get('managed'), dict)
                                  or not all(isinstance(k, str) and isinstance(v, str) for k, v in state['managed'].items())):
            raise ValueError('Unsupported sync state')
        previous = state['managed'] if state else defaults
        imported = bindings(source, adapt_shell=True)
        # Native bindings win over packaged defaults. Retain nonconflicting
        # defaults and intentional user modifications/additions in HP-OS.
        merged = {k: v for k, v in defaults.items() if k not in imported}
        merged.update(imported)
        custom = {k: v for k, v in current.items()
                  if k not in previous or signature(v) != signature(previous[k])}
        removed = set(previous) - set(current) if state else set()
        for k in removed: merged.pop(k, None)
        managed = dict(merged)
        merged.update(custom)
        block = 'binds {\n' + ''.join('    ' + v.strip() + '\n' for v in merged.values()) + '}'
        candidate = original
        for node in reversed(blocks): candidate = candidate[:node.start] + candidate[node.end:]
        candidate = candidate.rstrip() + '\n\n' + block + '\n'
        # Stabilize whitespace after removing an earlier generated block.
        if len(blocks) == 1:
            node = blocks[0]
            candidate = original[:node.start] + block + original[node.end:]
        fd, tmp = tempfile.mkstemp(prefix='.bindings-candidate-', suffix='.kdl', dir=target.parent)
        os.close(fd)
        try:
            Path(tmp).write_text(candidate)
            subprocess.run([niri, 'validate', '--config', tmp], check=True, capture_output=True, text=True)
        finally:
            Path(tmp).unlink(missing_ok=True)
        if candidate != original:
            backup = target.with_suffix(target.suffix + '.before-bindings-sync')
            if not backup.exists(): shutil.copy2(target, backup)
            atomic(target, candidate, target.stat().st_mode & 0o777)
        # Exclude custom overrides from managed baseline so later syncs preserve
        # them. A failed validation never changes either file.
        state_text = json.dumps({'version': 1, 'managed': managed}, indent=2) + '\n'
        if not state_path.exists() or state_path.read_text() != state_text:
            atomic(state_path, state_text)
        print('Synchronized', len(merged), 'bindings into', target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'target', 'baseline'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--niri', default='niri')
    args = parser.parse_args()
    try: sync(args.source, args.target, args.baseline, args.niri)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        parser.exit(1, 'Bindings sync failed: ' + detail + '\n')


if __name__ == '__main__': main()
