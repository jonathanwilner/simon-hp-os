#!/usr/bin/env python3
"""Publish an atomic compact dashboard feed alongside full machine history."""
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

RECENT_LIMIT = 40
FIELDS = ('host', 'session', 'safe_session', 'status', 'exit_code', 'command',
          'cwd', 'started_at', 'updated_at', 'finished_at', 'log_url',
          'bytes_published', 'progress')


def atomic_json(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.manifest-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, separators=(',', ':') if compact else None,
                      indent=None if compact else 2, sort_keys=True)
            stream.write('\n')
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def compact_feed(data, recent_limit=RECENT_LIMIT):
    machines = []
    for original in data.get('machines', []):
        ordered = sorted(original.get('sessions', []),
                         key=lambda item: item.get('updated_at') or item.get('started_at') or '', reverse=True)
        # All running tasks stay visible, including tasks older than the recent window.
        recent = {item.get('safe_session') for item in ordered[:recent_limit]}
        selected = [item for item in ordered if item.get('safe_session') in recent or item.get('status') == 'running']
        sessions = []
        for item in selected:
            session = {key: item[key] for key in FIELDS if key in item}
            for key in ('command', 'cwd'):
                if key in session:
                    session[key] = str(session[key])[:160]
            sessions.append(session)
        machines.append({'host': original['host'], 'generated_at': original.get('generated_at'),
                         'totals': original.get('totals', {}), 'sessions': sessions,
                         'total_sessions': len(ordered)})
    return {'version': 1, 'generated_at': data.get('generated_at'),
            'totals': data.get('totals', {}), 'machines': machines, 'recent_limit': recent_limit}


def publish_dashboard(root, data):
    atomic_json(Path(root) / 'dashboard' / 'manifest.json', compact_feed(data), compact=True)


def aggregate(root):
    root = Path(root)
    machines = []
    for path in sorted((root / 'machines').glob('*/manifest.json')):
        try:
            machines.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            continue
    data = {'version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            'machines': machines,
            'totals': {status: sum(machine.get('totals', {}).get(status, 0) for machine in machines)
                       for status in ('running', 'failed', 'succeeded', 'unknown')}}
    atomic_json(root / 'manifest.json', data)
    publish_dashboard(root, data)
    return data


if __name__ == '__main__':
    aggregate(sys.argv[1])
