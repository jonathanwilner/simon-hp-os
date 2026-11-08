#!/usr/bin/env python3
"""Choose only an installed host driver for a detected GPU. Never install drivers."""
import json
import os
from pathlib import Path
import sys

def detect(root=Path('/sys')):
    devices = []
    for card in sorted(root.glob('class/drm/card[0-9]*')):
        if '-' in card.name:
            continue
        device = card / 'device'
        driver = (device / 'driver').resolve().name if (device / 'driver').exists() else ''
        vendor = (device / 'vendor').read_text().strip() if (device / 'vendor').exists() else ''
        compatible = (device / 'of_node/compatible').read_bytes().replace(b'\0', b',').decode(errors='replace') if (device / 'of_node/compatible').exists() else ''
        kind = 'nvidia' if driver == 'nvidia' or vendor == '0x10de' else 'qualcomm' if driver == 'msm' or 'qcom,' in compatible else 'other'
        devices.append(dict(card=card.name, driver=driver, vendor=vendor, kind=kind))
    return devices

def environment(devices, icd_dir=Path('/usr/share/vulkan/icd.d')):
    # Preserve explicit application choices and hybrid host selection. NVIDIA
    # uses the Ubuntu driver already matched to its kernel module.
    if os.environ.get('VK_DRIVER_FILES') or os.environ.get('VK_ICD_FILENAMES'):
        return {}
    kinds = {d['kind'] for d in devices}
    if kinds == {'qualcomm'}:
        candidates = sorted(icd_dir.glob('freedreno*.json'))
        candidates = [p for p in candidates if 'i686' not in p.name and 'x86_64' not in p.name]
        if candidates:
            return {'VK_DRIVER_FILES': ':'.join(map(str, candidates))}
    return {}

if __name__ == '__main__':
    devices = detect()
    env = environment(devices)
    if sys.argv[1:2] == ['--exec']:
        if len(sys.argv) < 3:
            raise SystemExit('Missing executable')
        os.environ.update(env)
        os.execvp(sys.argv[2], sys.argv[2:])
    else:
        report = {'devices': devices, 'environment': env, 'policy': 'host-native; Qualcomm prefers installed Freedreno Vulkan; NVIDIA only when detected'}
        print(json.dumps(report, indent=2))
