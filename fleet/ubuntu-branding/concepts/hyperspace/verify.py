#!/usr/bin/env python3
"""Decode every exported frame and review encoded samples, not source-only frames."""
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw
from render import OUT, VARIANTS, FPS, DURATION, ease, travel

assert ease(0) == 0 and ease(1) == 1
# The integrated speed is continuous at every acceleration/deceleration boundary.
for _, _, _, density, _ in VARIANTS:
    for t in (6.6, 9.2, 11.8):
        h = 1e-4
        left = (travel(t, density)-travel(t-h, density))/h
        right = (travel(t+h, density)-travel(t, density))/h
        assert abs(left-right) < 1e-5, (t, left, right)

sheet = Image.new('RGB', (1600, 1000), (3, 7, 17))
draw = ImageDraw.Draw(sheet)
reports = []
for row, (slug, title, *_) in enumerate(VARIANTS):
    path = OUT/(slug+'.mp4')
    meta = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))
    video = meta['streams'][0]
    assert video['codec_name'] == 'h264'
    assert (video['width'], video['height']) == (1920, 1080)
    assert video['r_frame_rate'] == f'{FPS}/1'
    assert int(video['nb_frames']) == FPS*DURATION
    assert abs(float(meta['format']['duration'])-DURATION) < .02
    # fps extraction still decodes the entire stream. -xerror fails on decode damage.
    data = subprocess.check_output(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                                    '-vf', 'fps=2,scale=320:180', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
    stride = 320*180*3
    assert len(data) == DURATION*2*stride
    for col, index in enumerate((2, 7, 11, 16, 21)):
        sample = data[index*stride:(index+1)*stride]
        sheet.paste(Image.frombytes('RGB', (320, 180), sample), (col*320, row*200+20))
    draw.text((8, row*200+3), title+' | encoded samples: 1s / 3.5s / 5.5s / 8s / 10.5s', fill=(180, 199, 219))
    report = dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  width=1920, height=1080, fps=FPS, seconds=DURATION, frames=FPS*DURATION,
                  full_decode='pass', audio='intentionally silent', speed_continuity='pass')
    reports.append(report)
    print(path.name, 'pass', flush=True)
sheet.save(OUT/'encoded-review.png')
(OUT/'verification.json').write_text(json.dumps(reports, indent=2)+'\n')
