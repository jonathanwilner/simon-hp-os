#!/usr/bin/env python3
"""Compose upstream adaptive icons as SVG, retaining original embedded image bytes.

OHOS 7 arkui_ace_engine/interfaces/inner_api/drawable_descriptor/
drawable_descriptor.cpp: CompositeIconNotAdaptive crops 288px inputs to 192px;
CompositeIconAdaptive scales other foregrounds to fit their background.
The clip path is the original global_system_resources ohos_icon_mask_svg path.
"""
import base64
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).parent / 'files/data/icons/HP-OS'
ORIGINALS = BASE / 'originals'
mask = ET.parse(ORIGINALS / 'ohos-icon-mask.svg').find('.//{http://www.w3.org/2000/svg}path').attrib['d']


def image(name, x, y, size):
    mime = 'image/webp' if name.endswith('.webp') else 'image/png'
    data = base64.b64encode((ORIGINALS / name).read_bytes()).decode()
    return f'<image x="{x}" y="{y}" width="{size}" height="{size}" xlink:href="data:{mime};base64,{data}"/>'


for name, background, foreground, cropped in [
    ('settings', 'settings-background.webp', 'settings-foreground.png', True),
    ('photos', 'photos-ohos_gallery_background.webp', 'photos-ohos_gallery_op.png', False),
    ('network', 'ic_shortcut_background.png', 'ic_shortcut_wifi_foreground.png', False),
    ('bluetooth', 'ic_shortcut_background.png', 'ic_shortcut_bluetooth_foreground.png', False),
]:
    # Normalized to the upstream SVG mask's 54x54 coordinate system.
    # Settings crops 48px from each side of its 288px inputs (192px output).
    offset, size = (-13.5, 81) if cropped else (0, 54)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           'width="192" height="192" viewBox="0 0 54 54">'
           f'<defs><clipPath id="mask"><path d="{mask}"/></clipPath></defs>'
           '<g clip-path="url(#mask)">'
           + image(background, offset, offset, size)
           + image(foreground, offset, offset, size)
           + '</g></svg>\n')
    compositions = BASE / 'compositions'
    compositions.mkdir(exist_ok=True)
    source = compositions / f'{name}.svg'
    source.write_text(svg)
    # Qt SVG does not apply these clipPaths. Render with librsvg once so all
    # desktop consumers receive the exact same alpha-masked pixels.
    subprocess.run(['magick', '-background', 'none', 'RSVG:' + str(source),
                    '-strip', str(BASE / '256x256' / f'{name}.png')], check=True)
