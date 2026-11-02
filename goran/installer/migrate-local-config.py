#!/usr/bin/env python3
"""Import reviewed-scope local deltas without copying legacy Git history.

Exit 2 means manual review is required; no destination files are changed.
The JSON report contains paths and reasons, never file contents. The legacy
checkout is always retained. Imported changes stay local and uncommitted.
"""
import argparse
import json
import pathlib
import re
import subprocess
import tempfile


def git(repo, *args, check=True):
    return subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check)


def mapped(path):
    if path.startswith(('HarmonyShell/', 'HP-OSShell/')):
        path = 'vendor/HP-OSShell/' + path.split('/', 1)[1]
    path = path.replace('harmonyos-theme', 'hp-os-theme')
    path = path.replace('cosmic-harmony-theme', 'cosmic-hp-os-theme')
    path = path.replace('/harmonyos.nix', '/hp-os-theme.nix')
    path = path.replace('/harmonyos-', '/hp-os-').replace('/harmonyos.json', '/hp-os.json')
    path = path.replace('/60-harmonyos-sans.conf', '/60-hp-os-sans.conf')
    path = path.replace('pkgs/hp-os-search-qwen/', 'pkgs/hp-os-search-iq/')
    path = path.replace('goran/desktop/search-qwen.nix', 'goran/desktop/search-iq.nix')
    return path


def relevant(path):
    return path.startswith(('goran/', 'HarmonyShell/', 'HP-OSShell/', 'pkgs/'))


def private(path, data):
    # Conservative review gate, not a claim that arbitrary code is secret-free.
    return (bool(re.search(r'(^|/)(secrets?|credentials?|\.env)([./]|$)|\.(age|pem|key)$', path, re.I))
            or bool(re.search(rb'-----BEGIN .*PRIVATE KEY-----|(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{15,}|AKIA[A-Z0-9]{16}', data)))


def migrate(source, dest, explicit_base=None):
    source, dest = pathlib.Path(source).resolve(), pathlib.Path(dest).resolve()
    if source == dest or source in dest.parents or dest in source.parents:
        raise ValueError('Source and destination must be independent checkouts')
    for repo in (source, dest):
        if pathlib.Path(git(repo, 'rev-parse', '--show-toplevel').stdout.decode().strip()).resolve() != repo:
            raise ValueError('Use checkout root paths')
    if explicit_base:
        base = git(source, 'rev-parse', '--verify', explicit_base + '^{commit}').stdout.decode().strip()
        if git(source, 'merge-base', '--is-ancestor', base, 'HEAD', check=False).returncode:
            raise ValueError('--legacy-base must be an ancestor of legacy HEAD')
    else:
        upstream = git(source, 'rev-parse', '--verify', '@{upstream}', check=False)
        if upstream.returncode:
            raise ValueError('No reliable upstream baseline; provide --legacy-base COMMIT')
        base = git(source, 'merge-base', 'HEAD', upstream.stdout.decode().strip()).stdout.decode().strip()
    paths = set(git(source, 'diff', '--name-only', '-z', base, '--').stdout.decode().split('\0'))
    paths.update(git(source, 'ls-files', '--others', '--exclude-standard', '-z').stdout.decode().split('\0'))
    report = {'source': str(source), 'destination': str(dest), 'base': base,
              'merged': [], 'retained_in_legacy': [], 'blocked': []}
    plans = []
    for path in sorted(paths - {''}):
        target = mapped(path)
        old = git(source, 'show', base + ':' + path, check=False)
        src, dst = source / path, dest / target
        if not relevant(path):
            report['retained_in_legacy'].append(path)
            continue
        reason = None
        if src.is_symlink() or dst.is_symlink() or not src.is_file():
            reason = 'Deletion, symlink, or non-regular file requires review'
        elif not src.resolve().is_relative_to(source):
            reason = 'Legacy path escapes checkout'
        elif not dst.resolve().is_relative_to(dest):
            reason = 'Destination escapes checkout'
        elif old.returncode or not dst.is_file():
            reason = 'New or unmapped relevant file requires explicit review'
        elif (git(source, 'ls-tree', base, '--', path).stdout.split()[0] == b'100755') != bool(src.stat().st_mode & 0o111):
            reason = 'Executable mode customization requires review'
        elif git(dest, 'ls-files', '--error-unmatch', '--', target, check=False).returncode:
            reason = 'Destination is untracked; requires review'
        else:
            local, incoming = src.read_bytes(), dst.read_bytes()
            if private(path, local) or private(path, old.stdout):
                reason = 'Potential private material requires review'
            elif b'\0' in local + incoming + old.stdout:
                reason = 'Binary customization requires review'
            else:
                with tempfile.TemporaryDirectory(prefix='hp-os-merge-') as tmp:
                    files = [pathlib.Path(tmp) / name for name in ('public', 'base', 'legacy')]
                    for f, data in zip(files, (incoming, old.stdout, local)):
                        f.write_bytes(data)
                    result = subprocess.run(['git', 'merge-file', '-p', *map(str, files)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode:
                    reason = 'Three-way conflict; manually merge legacy changes into ' + target
                else:
                    plans.append((dst, result.stdout))
                    report['merged'].append({'from': path, 'to': target})
        if reason:
            report['blocked'].append({'path': path, 'target': target, 'reason': reason})
    if not report['blocked']:
        for path, data in plans:
            path.write_bytes(data)
    report['applied'] = not report['blocked']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from', dest='source', required=True)
    parser.add_argument('--to', dest='destination', required=True)
    parser.add_argument('--legacy-base')
    parser.add_argument('--report', type=pathlib.Path)
    args = parser.parse_args()
    try:
        report = migrate(args.source, args.destination, args.legacy_base)
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        report = {'applied': False, 'error': str(exc)}
    output = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output)
    print(output, end='')
    return 0 if report['applied'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
