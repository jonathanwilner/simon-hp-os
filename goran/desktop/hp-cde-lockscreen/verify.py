#!/usr/bin/env python3
"""Verify visual-only transformation against supplied, unmodified DMS components."""
import importlib.util
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('visuals', Path(__file__).with_name('dms-hp-cde-lock.py'))
visuals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(visuals)


def handlers(text):
    result = []
    for match in re.finditer(r'(?:\bfunction\s+\w+\s*\([^)]*\)|\bon\w+\s*:)\s*\{', text):
        i, depth, quote = match.end(), 1, None
        while depth:
            char = text[i]
            if quote:
                if char == '\\':
                    i += 1
                elif char == quote:
                    quote = None
            elif char in "\"'`":
                quote = char
            elif char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
            i += 1
        result.append(text[match.start():i])
    return result


for path in sys.argv[1:]:
    original = Path(path).read_text()
    patched = visuals.transform(original)
    assert handlers(original) == handlers(patched), 'Authentication/input handler changed'
    assert re.findall(r'\bid:\s*(\w+)', original) == [
        value for value in re.findall(r'\bid:\s*(\w+)', patched)
        if value not in {'cdePanel', 'cdePasswordPanel', 'cdeLogoPanel'}
    ], 'Existing component ID changed'
    assert visuals.transform(patched) == patched
    try:
        visuals.transform(original + '\n// Unknown upstream revision\n')
    except ValueError:
        pass
    else:
        raise AssertionError('Unknown revision accepted')
    print(f'PASS {path}: {len(handlers(original))} handlers unchanged; IDs preserved; idempotence and revision guard pass')
if len(sys.argv) < 2:
    raise SystemExit('Supply one or more original LockScreenContent.qml paths')
