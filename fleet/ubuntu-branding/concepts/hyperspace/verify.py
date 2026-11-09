#!/usr/bin/env python3
"""Decode the delivered movie and verify its declared timing and smooth velocity."""
import json, math, subprocess
import render
p=render.OUT/'01-hp-circle-to-os.mp4'
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
s=meta['streams'][0]
assert (s['width'],s['height'],s['r_frame_rate'],s['nb_frames'])==(1920,1080,'60/1','720')
assert abs(float(meta['format']['duration'])-12)<.02
subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True)
# The star displacement is an integral of eased speed, without boundary jumps.
for t in (5.4,8.0,11.4):
 h=1e-5
 left=(render.travel(t)-render.travel(t-h))/h
 right=(render.travel(t+h)-render.travel(t))/h
 assert abs(left-right)<1e-4
report={'file':str(p),'resolution':'1920x1080','fps':60,'frames':720,'duration':12,'full_decode':'pass','speed_continuity':'pass','sha256':render.hashlib.sha256(p.read_bytes()).hexdigest()}
(render.OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
