#!/usr/bin/env python3
"""Inspect or install unchanged official fonts; no third-party download mirrors."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCE = json.loads((ROOT / 'official-source.json').read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path):
    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:
        raise RuntimeError('Install python-fonttools, or run: uv run --with fonttools python harmony-fonts.py ...') from exc
    with TTFont(path) as font:
        cmap = font.getBestCmap()
        family = font['name'].getDebugName(1)
        if not family or not family.startswith('HarmonyOS Sans'):
            raise ValueError(f'{path}: expected genuine HarmonyOS Sans family; found {family!r}')
        axes = [{'tag': a.axisTag, 'min': a.minValue, 'default': a.defaultValue, 'max': a.maxValue}
                for a in font['fvar'].axes] if 'fvar' in font else []
        known = {f['sha256'] for f in SOURCE['fonts']}
        sha = digest(path)
        return {'path': str(path), 'sha256': sha, 'matches_official_20260612': sha in known,
                'family': family, 'version': font['name'].getDebugName(5), 'axes': axes,
                'glyph_count': len(cmap),
                'english': all(ord(c) in cmap for c in 'HP-OS 0123456789'),
                'simplified_chinese': all(ord(c) in cmap for c in '简体中文通知控制中心'),
                'traditional_chinese': all(ord(c) in cmap for c in '繁體中文通知控制中心')}


def detect():
    # fc-match always returns a fallback, so inspect the actual family and bytes.
    found = {}
    for family in ('HarmonyOS Sans', 'HarmonyOS Sans SC', 'HarmonyOS Sans TC'):
        result = subprocess.run(['fc-match', '-f', '%{family}\n%{file}', family], check=True, text=True, capture_output=True)
        resolved_family, resolved_path = result.stdout.split('\n', 1)
        if family not in resolved_family.split(','):
            found[family] = {'status': 'MISSING', 'resolved_family': resolved_family}
            continue
        path = Path(resolved_path)
        if path.is_file():
            try:
                info = inspect(path)
                found[family] = info if info['family'] == family else {'status': 'MISSING', 'resolved_family': info['family']}
            except ValueError:
                found[family] = {'status': 'MISSING', 'resolved_file': str(path)}
        else:
            found[family] = {'status': 'MISSING'}
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--download-official', action='store_true', help='download the pinned package directly linked by the font publisher')
    source.add_argument('--source-dir', type=Path, help='directory of locally obtained official TTF files')
    source.add_argument('--detect', action='store_true', help='verify fontconfig-selected families and hashes')
    parser.add_argument('--license', type=Path, help='original license, required with --source-dir for installation')
    parser.add_argument('--install', action='store_true', help='install fonts; otherwise only inspect')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--destination', type=Path, default=Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'fonts/hp-os')
    args = parser.parse_args()
    if args.detect or (not args.source_dir and not args.download_official):
        report = detect()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if any(report[f].get('status') == 'MISSING' for f in ('HarmonyOS Sans', 'HarmonyOS Sans SC')) else 0
    with tempfile.TemporaryDirectory(prefix='hp-os-fonts-') as temporary:
        temp = Path(temporary)
        license_path = args.license
        source_dir = args.source_dir
        if args.download_official:
            archive = temp/'official.zip'
            ca_file = os.environ.get('SSL_CERT_FILE') or os.environ.get('NIX_SSL_CERT_FILE')
            if not ca_file and Path('/etc/ssl/certs/ca-certificates.crt').is_file():
                ca_file = '/etc/ssl/certs/ca-certificates.crt'
            context = ssl.create_default_context(cafile=ca_file)
            with urllib.request.urlopen(SOURCE['url'], context=context, timeout=60) as response, archive.open('wb') as output:
                shutil.copyfileobj(response, output)
            if digest(archive) != SOURCE['sha256']:
                raise ValueError('Official archive hash changed; review new assets and update provenance before installing')
            with zipfile.ZipFile(archive) as package:
                # Extract only known file names, flattening paths and rejecting unexpected fonts.
                for item in SOURCE['fonts']:
                    name = item['file']
                    target = temp/Path(name).name
                    target.write_bytes(package.read(name))
                    if digest(target) != item['sha256']:
                        raise ValueError(f'Font hash mismatch: {name}')
                license_path = temp/'LICENSE-update.txt'
                license_path.write_bytes(package.read('HarmonyOS Sans/LICENSE-update.txt'))
            source_dir = temp
        fonts = sorted(source_dir.rglob('*.ttf'))
        if not fonts:
            raise ValueError('No TTF files found')
        report = [inspect(p) for p in fonts]
        names = [p.name for p in fonts]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate font basenames; use one official release directory')
        required = {'HarmonyOS Sans', 'HarmonyOS Sans SC'}
        if not required.issubset({f['family'] for f in report}):
            raise ValueError('Both HarmonyOS Sans and HarmonyOS Sans SC are required')
        if args.install and not args.dry_run:
            if not license_path or not license_path.is_file():
                raise ValueError('Supply the original font license with --license')
            # Refuse to overwrite any different existing font. Rollback is removal of this directory.
            for p in fonts:
                target = args.destination/p.name
                if target.exists() and digest(target) != digest(p):
                    raise ValueError(f'Refusing overwrite: {target}. Choose a new destination.')
            args.destination.mkdir(parents=True, exist_ok=True)
            for p in fonts:
                shutil.copy2(p, args.destination/p.name)
            shutil.copy2(license_path, args.destination/'LICENSE.txt')
            (args.destination/'NOTICE.txt').write_text('HP-OS uses HarmonyOS Sans Fonts. Copyright 2021 Huawei Device Co., Ltd. See LICENSE.txt.\n')
            (args.destination/'provenance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
            subprocess.run(['fc-cache', '-f', str(args.destination)], check=True)
        print(json.dumps({'installed': args.install and not args.dry_run, 'destination': str(args.destination), 'fonts': report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
