#!/usr/bin/env python3
"""Apply HP-OS VISUAL_SPEC tokens to native COSMIC themes, without resetting apps.

Seed missing fields from the installed vendor schema (including future fields).
Only the explicit presentation keys below are managed. Mode and app preferences
remain owned by their existing publishers. Writes are atomic and idempotent.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile

ACCENT = '#0A59F7'
PALETTES = {
    'Light': dict(canvas='#F1F3F5', primary='#FFFFFF', secondary='#E8ECF1',
                  text='#18212B', hover='#E0E5ED', pressed='#CFD7E2',
                  selected='#DCE8FF', blue=ACCENT, divider='#C5CCD6'),
    'Dark': dict(canvas='#121316', primary='#1C1E23', secondary='#272A31',
                 text='#F1F3F5', hover='#343944', pressed='#454C59',
                 selected='#20365D', blue='#8DB4FF', divider='#484F5B'),
}

class Color(str):
    pass


def ron(value, version):
    if isinstance(value, Color):
        rgba = value.lstrip('#')
        if len(rgba) == 6:
            rgba += 'FF'
        if version == 2:
            return json.dumps('#' + rgba)
        return '(' + ', '.join(f'{key}: {int(rgba[i:i+2],16)/255:.9f}'
                              for key, i in zip(('red','green','blue','alpha'),range(0,8,2))) + ',)'
    if isinstance(value, dict):
        return '(' + ', '.join(f'{key}: {ron(item, version)}' for key,item in value.items()) + ',)'
    if isinstance(value, tuple):
        return '(' + ', '.join(ron(item, version) for item in value) + ',)'
    return json.dumps(value)


def component(p, base=None, solid=False, transparent=False):
    background = base or p['secondary']
    foreground = '#FFFFFF' if solid else p['text']
    return {key: Color(value) for key,value in dict(
        base=background + ('00' if transparent else ''),
        hover='#084CD5' if solid else p['hover'],
        pressed='#0640B3' if solid else p['pressed'],
        selected=ACCENT if solid else p['selected'],
        selected_text='#FFFFFF' if solid else p['blue'], focus=p['blue'],
        divider=p['divider'], on=foreground, disabled=background+'80',
        on_disabled=foreground+'80', border=background if solid else p['divider'],
        disabled_border=p['divider']+'80').items()}


def theme_values(mode, version):
    p = PALETTES[mode]
    values = {'name': f'HP-OS {mode}'}
    for key, surface in [('background','canvas'), ('primary','primary'), ('secondary','secondary')]:
        values[key] = dict(base=Color(p[surface]), component=component(p),
                           divider=Color(p['divider']), on=Color(p['text']),
                           small_widget=Color(p['hover']))
    values['accent'] = component(p, ACCENT, solid=True)
    values['accent_button'] = component(p, ACCENT, solid=True)
    values['button'] = component(p)
    for key in ('icon_button','text_button','list_button','link_button'):
        values[key] = component(p, p['primary'], transparent=True)
    values['link_button']['on'] = Color(p['blue'])
    values['corner_radii'] = {key: (float(size),)*4 for key,size in
                              [('radius_0',0),('radius_xs',8),('radius_s',12),
                               ('radius_m',20),('radius_l',28),('radius_xl',160)]}
    result = {key: ron(value, version)+'\n' for key,value in values.items()}
    result['frosted_maximized_apps'] = 'false\n'
    result['accent_text'] = 'Some(' + ron(Color(p['blue']),version) + ')\n'
    return result


def atomic_write(path, data):
    if path.exists() and path.read_text() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.'+path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return True


def apply(defaults, config):
    changed = 0
    for mode in PALETTES:
        for version in (1,2):
            relative = Path(f'com.system76.CosmicTheme.{mode}') / f'v{version}'
            source, target = defaults / relative, config / 'cosmic' / relative
            if not source.is_dir():
                continue  # Older COSMIC releases may only supply v1.
            for entry in sorted(source.iterdir()):
                if entry.is_file() and not (target / entry.name).exists():
                    changed += atomic_write(target / entry.name, entry.read_text())
            for key,data in theme_values(mode,version).items():
                changed += atomic_write(target / key,data)
    font = '(family: "HarmonyOS Sans", weight: Normal, stretch: Normal, style: Normal,)\n'
    changed += atomic_write(config/'cosmic/com.system76.CosmicTk/v1/interface_font',font)
    return changed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--defaults',required=True,type=Path)
    parser.add_argument('--config',type=Path,default=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config')))
    args=parser.parse_args()
    for mode in PALETTES:
        if not (args.defaults/f'com.system76.CosmicTheme.{mode}/v1').is_dir():
            parser.error(f'Missing vendor {mode} v1 theme in {args.defaults}')
    print(f'HP-OS COSMIC theme: {apply(args.defaults,args.config)} files updated')

if __name__ == '__main__':
    main()
