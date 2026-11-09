#!/usr/bin/env python3
"""Deterministic logo-led motion studies; brand assets remain in the private kit."""
import argparse
import functools
import json
import math
import os
import pathlib
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DURATION = 1920, 1080, 60, 12
KIT = pathlib.Path(os.environ.get('HP_BRAND_ASSETS', '/home/jonathan/src/pdf-ppt-kit/assets'))
OUT = pathlib.Path(os.environ.get('HP_MOTION_OUTPUT', pathlib.Path.home() / 'Videos/hp-logo-motion-v2'))
VARIANTS = [
    ('01-orbital-aperture', 'Orbital aperture', (65, 133, 235), .85, .0),
    ('02-prism-fold', 'Prism fold', (106, 151, 222), .95, .06),
    ('03-ion-vortex', 'Ion vortex', (86, 153, 169), 1.10, .24),
    ('04-silver-slipstream', 'Silver slipstream', (177, 199, 221), .68, .0),
    ('05-blue-supernova', 'Blue supernova', (37, 104, 235), 1.20, -.09),
]


def sat(x):
    return max(0.0, min(1.0, x))


def ease(x):
    """Quintic smootherstep: zero velocity and acceleration at each endpoint."""
    x = sat(x)
    return x*x*x*(x*(6*x-15)+10)


def ramp_integral(t, start, duration):
    """Exact integral of the quintic speed ramp, continuous through both joins."""
    x = (t-start)/duration
    if x <= 0:
        return 0.0
    if x >= 1:
        return duration*(x-.5)
    return duration*(x**6-3*x**5+2.5*x**4)


def travel(t, density):
    boost = .36*density
    return .045*t + boost*ramp_integral(t, 6.6, 2.6) - (boost+.020)*ramp_integral(t, 9.2, 2.6)


def mix(a, b, t):
    return a+(b-a)*t


@functools.lru_cache(maxsize=24)
def font(size, medium=False):
    weight = 'Medium' if medium else 'Regular'
    return ImageFont.truetype(str(KIT/f'fonts/ttf/HPFormaDJROffice-{weight}.ttf'), size)


logo = Image.open(KIT/'logos/logo_HP_Electric_Blue_keyline.png').convert('RGBA')
# The approved logo is used intact. No split ring, stroke morph, recolor or glow.
@functools.lru_cache(maxsize=160)
def logo_size(size):
    return logo.resize((size, size), Image.Resampling.LANCZOS)


def place_logo(layer, x, y, size, opacity):
    asset = logo_size(round(size)).copy()
    if opacity < 1:
        asset.putalpha(asset.getchannel('A').point(lambda a: round(a*sat(opacity))))
    layer.alpha_composite(asset, (round(x-size/2), round(y-size/2)))


def text(draw, xy, value, size, color, anchor='mm', medium=False):
    draw.text(xy, value, font=font(size, medium), fill=color, anchor=anchor)


rng = np.random.default_rng(821)
stars = np.column_stack([rng.uniform(-2.8, 2.8, 1100), rng.uniform(-1.7, 1.7, 1100),
                         rng.uniform(.03, 1, 1100), rng.uniform(.3, 1, 1100)])
yy, xx = np.mgrid[:H, :W]
radius = np.sqrt(((xx-W/2)/(W/2))**2+((yy-H*.45)/(H*.65))**2)
# Offline-generated color field, independent of private image assets.
bg = np.zeros((H, W, 3), dtype=np.uint8)
for channel, value in enumerate((2, 6, 15)):
    bg[:, :, channel] = value + np.uint8(np.exp(-radius*2.2)*(2, 4, 7)[channel])
BACKGROUND = Image.fromarray(bg)
del bg, xx, yy


def frame(t, variant):
    slug, title, accent, density, twist = VARIANTS[variant]
    launch = ease((t-6.6)/2.6)
    settle = ease((t-9.2)/2.6)
    ui = ease((t-2.5)/1.1)*(1-ease((t-6.65)/1.1))
    im = BACKGROUND.copy()
    d = ImageDraw.Draw(im)
    depth = travel(t, density)
    angle = twist*depth*.48
    sx = stars[:, 0]*math.cos(angle)-stars[:, 1]*math.sin(angle)
    sy = stars[:, 0]*math.sin(angle)+stars[:, 1]*math.cos(angle)
    z = (stars[:, 2]-depth)%1+.07
    cx, cy = W/2, H*.46
    px, py = cx+sx/z*390, cy+sy/z*390
    tail = .005 + .105*launch*(1-.75*settle)*density
    qx, qy = cx+sx/(z+tail)*390, cy+sy/(z+tail)*390
    for k in range(round(620*density)):
        x, y = px[k], py[k]
        if not (-50 < x < W+50 and -50 < y < H+50):
            continue
        # Distant stars fade in at recycling; central UI stays calm.
        far_fade = ease((1.07-z[k])/.15)
        near_fade = ease((z[k]-.07)/.05)
        center = min(1, ((x-cx)/440)**2+((y-560)/340)**2)
        quiet = 1-ui*(1-center)*.86
        b = stars[k, 3]*(.7+.34*launch)*min(1, .6/z[k])*far_fade*near_fade*quiet
        col = tuple(round((c*.5+115)*b) for c in accent)
        d.line((qx[k], qy[k], x, y), fill=col, width=1+int(z[k]<.25))
    # Atmosphere moves independently. Its rings keep clear space around the logo.
    atmosphere = Image.new('RGBA', (W, H))
    a = ImageDraw.Draw(atmosphere)
    intro = ease(t/1.15)
    raise_mark = ease((t-1.35)/1.95)
    enter = ease((t-7.05)/1.8)
    center_y = mix(mix(H*.46, H*.245, raise_mark), H*.46, enter)
    size = mix(mix(192, 112, raise_mark), 156, enter)
    # The portal is atmosphere, not a detached part of the trademark.
    pulse = ease((t-6.9)/2.4)
    portal_alpha = ease((t-6.7)/.7)*(1-ease((t-8.4)/1.4))
    if variant in (0, 4) and portal_alpha:
        r = mix(200, 1100, pulse)
        a.ellipse((cx-r, cy-r, cx+r, cy+r), outline=(*accent, round(110*portal_alpha)), width=2)
    if variant == 1:
        alpha = round(34*intro*(1-raise_mark)+24*launch*(1-settle))
        for offset in (-360, 360):
            x = cx+offset+100*launch
            a.line((x-200, 0, x+200, H), fill=(*accent, alpha), width=2)
    if variant == 2:
        alpha = round(46*intro*(1-raise_mark)+38*launch*(1-settle))
        for j in range(2):
            r = 270+j*80
            start = t*9+j*180
            a.arc((cx-r, cy-r, cx+r, cy+r), start, start+65, fill=(*accent, alpha), width=2)
    if variant == 4:
        alpha = round(34*launch*(1-settle))
        a.ellipse((cx-700, cy-700, cx+700, cy+700), outline=(*accent, alpha), width=3)
    im = Image.alpha_composite(im.convert('RGBA'), atmosphere)
    ink = Image.new('RGBA', (W, H))
    g = ImageDraw.Draw(ink)
    place_logo(ink, cx, center_y, size, intro)
    if ui > 0:
        alpha = round(ui*255)
        dy = (1-ease((t-2.5)/1.1))*18
        text(g, (cx, 428+dy), 'Welcome back', 36, (241, 246, 252, alpha), medium=True)
        text(g, (cx, 477+dy), 'Sign in to your workspace', 23, (157, 177, 197, alpha))
        g.rounded_rectangle((750, 527+dy, 1170, 589+dy), radius=10,
                            fill=(14, 26, 41, round(ui*242)), outline=(80, 101, 124, round(ui*180)))
        text(g, (777, 557+dy), 'Password', 24, (174, 192, 210, alpha), anchor='lm')
        g.rounded_rectangle((750, 609+dy, 1170, 667+dy), radius=10, fill=(2, 74, 216, alpha))
        text(g, (cx, 638+dy), 'Sign in', 24, (255, 255, 255, alpha), medium=True)
        text(g, (cx, 709+dy), 'English  ·  Session options', 20, (139, 161, 184, alpha))
    welcome = ease((t-9.0)/1.25)
    if welcome > 0:
        text(g, (cx, 647), 'Welcome', 34, (234, 242, 251, round(255*welcome)), medium=True)
    im = Image.alpha_composite(im, ink)
    d = ImageDraw.Draw(im)
    # Neutral editorial captions identify concepts without repeating the product name.
    text(d, (58, 54), f'{variant+1:02d} / {title}', 22, (129, 151, 175, 255), anchor='lm')
    text(d, (58, 1028), 'Motion concept · simulated sign-in transition', 18, (103, 125, 149, 255), anchor='lm')
    return im.convert('RGB')


def render(variant):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT/(VARIANTS[variant][0]+'.mp4')
    proc = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-an',
                             '-c:v', 'libx264', '-threads', '4', '-preset', 'fast', '-crf', '19',
                             '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(path)], stdin=subprocess.PIPE)
    for n in range(FPS*DURATION):
        proc.stdin.write(frame(n/FPS, variant).tobytes())
        if n%120 == 0:
            print(VARIANTS[variant][0], n, '/', FPS*DURATION, flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f'Encoding failed: {path}')
    return path


def preview():
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGB', (1600, 1000), (4, 8, 18))
    d = ImageDraw.Draw(sheet)
    for variant in range(5):
        for col, t in enumerate((1.2, 3.5, 5.5, 8.0, 10.5)):
            sheet.paste(frame(t, variant).resize((320, 180), Image.Resampling.LANCZOS), (col*320, variant*200+20))
        d.text((8, variant*200+3), VARIANTS[variant][1]+' | 1.2s / 3.5s / 5.5s / 8s / 10.5s', fill=(180, 199, 219))
    sheet.save(OUT/'comparison.png')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', type=int, choices=range(1, 6))
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    if args.preview:
        preview()
    else:
        for variant in ([args.variant-1] if args.variant else range(5)):
            render(variant)
