#!/usr/bin/env python3
"""Compare three quality profiles with explicit close IPC in a private test session."""
import argparse
import json
import os
from pathlib import Path
import time
from runtime_acceptance import command, measure_idle


def descendants(pid):
    parents = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit(): continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')',1)[1].split()
            parents[int(entry.name)] = int(fields[1])
        except (OSError, ValueError, IndexError): pass
    result, frontier = set(), {pid}
    while frontier:
        found = {child for child, parent in parents.items() if parent in frontier} - result
        result.update(found)
        frontier = found
    return sorted(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['qs','runtime','config','output']: p.add_argument('--'+key,required=True)
    p.add_argument('--pid',type=int,required=True)
    args = p.parse_args()
    if os.environ.get('INIR_SAFE_PREVIEW') != '1': p.error('private INIR_SAFE_PREVIEW=1 session required')
    original = json.loads(Path(args.config).read_text()).get('hpos',{}).get('quality','balanced')
    def ipc(target, method, *values): return command([args.qs,'-p',args.runtime,'ipc','call',target,method,*values])
    results = {'scope':'controlled panels-closed nested 4K scale2, not native idle','profiles':[], 'close_commands':[]}
    for target in ['hpos','controlPanel','sidebarRight','sidebarLeft','search','overview','taskview','mediaControls','session','cheatsheet']:
        ipc(target,'close')
        results['close_commands'].append(target+'.close')
    # Shared settings has open/toggle, but no close. Establish open then toggle closed.
    ipc('settings','open')
    time.sleep(.5)
    ipc('settings','toggle')
    results['close_commands'].append('settings.open then settings.toggle')
    time.sleep(2)
    windows_before = json.loads(command(['niri','msg','-j','windows']))
    shell_windows = [w for w in windows_before if w.get('pid') == args.pid]
    if shell_windows: raise RuntimeError('shell floating windows remain: '+repr(shell_windows))
    results['windows_before'] = windows_before
    try:
        for quality in ['balanced','performance','full']:
            ipc('hpos','set','quality',json.dumps(quality))
            time.sleep(2)
            persisted = json.loads(Path(args.config).read_text()).get('hpos',{}).get('quality')
            if persisted != quality: raise AssertionError('quality did not persist')
            before = descendants(args.pid)
            sample = measure_idle(args.pid,20)
            after = descendants(args.pid)
            sample.update({'quality':quality,'descendant_count_before':len(before),'descendant_count_after':len(after)})
            results['profiles'].append(sample)
            print(json.dumps(sample),flush=True)
    finally:
        ipc('hpos','set','quality',json.dumps(original))
        time.sleep(.3)
        results['restored_quality'] = json.loads(Path(args.config).read_text()).get('hpos',{}).get('quality')
        results['windows_after'] = json.loads(command(['niri','msg','-j','windows']))
        Path(args.output).write_text(json.dumps(results,indent=2)+'\n')
    return 0


if __name__ == '__main__': raise SystemExit(main())
