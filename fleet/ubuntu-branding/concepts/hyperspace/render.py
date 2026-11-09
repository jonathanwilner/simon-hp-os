#!/usr/bin/env python3
"""One continuous HP circle -> HP-OS -> premium slash reveal, with optical glow."""
import argparse, functools, hashlib, json, math, os, pathlib, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
W,H,FPS,DURATION=1920,1080,60,12
KIT=pathlib.Path(os.environ.get('HP_BRAND_ASSETS','/home/jonathan/src/pdf-ppt-kit/assets'))
OUT=pathlib.Path(os.environ.get('HP_MOTION_OUTPUT',pathlib.Path.home()/'Videos/hp-logo-morph-v3'))
ACCENT=(48,139,255)
POLYS=[[(339,0),(238,0),(0,653),(102,653)],[(188,653),(290,653),(401,347),(300,347)],[(487,347),(589,347),(351,999),(250,999)],[(564,653),(666,653),(777,347),(676,347)]]
def sat(x):return max(0.,min(1.,x))
def ease(x):
 x=sat(x);return x*x*x*(x*(6*x-15)+10)
def mix(a,b,t):return a+(b-a)*t
def ramp_integral(t,start,duration):
 x=(t-start)/duration
 return 0 if x<=0 else duration*(x-.5) if x>=1 else duration*(x**6-3*x**5+2.5*x**4)
def travel(t):return .022*t+.44*ramp_integral(t,5.4,2.6)-.405*ramp_integral(t,8.0,3.4)
@functools.lru_cache(maxsize=12)
def font(size):return ImageFont.truetype(str(KIT/'fonts/ttf/HPFormaDJROffice-Medium.ttf'),size)
logo=Image.open(KIT/'logos/logo_HP_Electric_Blue_keyline.png').convert('RGBA').resize((700,700),Image.Resampling.LANCZOS)
a=np.array(logo);yy,xx=np.mgrid[:700,:700]
# Original asset's white inner letterforms. Its blue outer circle becomes the O.
inner=Image.fromarray(np.uint8((a[:,:,0]>190)&(a[:,:,1]>190)&(((xx-350)**2+(yy-350)**2)<322**2))*255)
def hero(t,native=False):
 ink=Image.new('RGBA',(W,H));d=ImageDraw.Draw(ink)
 reveal=ease(t/.95);m=ease((t-1.4)/2.3);depart=ease((t-5.4)/2.6)
 # Circle follows one unbroken path: logo ring -> typographic O -> star portal.
 ox,oy=1067,480
 rx=mix(960,ox,m);ry=480;rr=mix(118,55,m);ratio=mix(1,.87,m)
 rx=mix(rx,960,depart if not native else 0);ry=mix(ry,480,depart if not native else 0)
 rr=mix(rr,1130,depart if not native else 0);ratio=mix(ratio,1,depart if not native else 0)
 opacity=reveal*(1-ease((t-5.5)/1.4) if native else 1-ease((t-6.5)/1.7))
 color=tuple(round(mix(ACCENT[i],(246,250,255)[i],m)) for i in range(3))
 width=max(1,round(mix(3,14,m)*(1-.76*depart)))
 if opacity>0:
  d.ellipse((rx-rr*ratio,ry-rr,rx+rr*ratio,ry+rr),outline=(*color,round(255*opacity)),width=width)
 # The original hp drifts left and softly resolves into the new letterforms.
 oldalpha=reveal*(1-ease((t-1.7)/1.55))
 if oldalpha>0:
  s=round(mix(234,180,m));mask=inner.resize((s,s),Image.Resampling.LANCZOS).point(lambda p:round(p*oldalpha))
  ink.paste((246,250,255),(round(mix(960,836,m)-s/2),round(480-s/2)),mask)
 word=ease((t-2.05)/1.65)*(1-ease((t-5.5)/1.4))
 if word>0:
  alpha=round(255*word)
  d.text((995,480),'HP-',font=font(152),anchor='rm',fill=(246,250,255,alpha))
  d.text((1138,480),'S',font=font(152),anchor='lm',fill=(246,250,255,alpha))
 # Final modern mark uses the original official four-stroke proportions intact.
 slash=ease((t-6.45)/1.95)
 if slash>0:
  size=mix(205,230,slash)
  for p in POLYS:
   d.polygon([(960+(x-388.5)*size/999,480+(y-499.5)*size/999) for x,y in p],fill=(247,251,255,round(slash*255)))
 # Two optical bloom scales keep a crisp core and a broad electric-blue halo.
 small=ink.resize((480,270),Image.Resampling.LANCZOS)
 glow=Image.new('RGBA',(480,270))
 for radius,gain in ((8,1.45),(2.3,.8)):
  alpha=small.getchannel('A').filter(ImageFilter.GaussianBlur(radius)).point(lambda p:min(255,round(p*gain)))
  tint=Image.new('RGBA',small.size,(*ACCENT,0));tint.putalpha(alpha);glow=Image.alpha_composite(glow,tint)
 glow=glow.resize((W,H),Image.Resampling.BILINEAR)
 return Image.alpha_composite(glow,ink)
rng=np.random.default_rng(821)
stars=np.column_stack([rng.uniform(-2.8,2.8,850),rng.uniform(-1.7,1.7,850),rng.uniform(.03,1,850),rng.uniform(.3,1,850)])
yy,xx=np.mgrid[:H,:W];radius=np.sqrt(((xx-W/2)/(W/2))**2+((yy-480)/(H*.65))**2)
bg=np.zeros((H,W,3),dtype=np.uint8)
for i,c in enumerate((1,4,12)):bg[:,:,i]=c+np.uint8(np.exp(-radius*2.2)*(2,5,12)[i])
BACKGROUND=Image.fromarray(bg);del bg,xx,yy
def frame(t):
 im=BACKGROUND.copy();d=ImageDraw.Draw(im);launch=ease((t-5.4)/2.6);settle=ease((t-8)/3.4)
 depth=travel(t);z=(stars[:,2]-depth)%1+.07
 px=960+stars[:,0]/z*390;py=480+stars[:,1]/z*390
 tail=.003+.18*launch*(1-.83*settle)
 qx=960+stars[:,0]/(z+tail)*390;qy=480+stars[:,1]/(z+tail)*390
 visibility=.18+.82*ease((t-5.4)/2.2)
 for k in range(len(stars)):
  x,y=px[k],py[k]
  if not(-60<x<W+60 and -60<y<H+60):continue
  far=ease((1.07-z[k])/.15);near=ease((z[k]-.07)/.05)
  quiet=.2+.8*min(1,((x-960)/370)**2+((y-480)/250)**2)
  b=stars[k,3]*min(1,.6/z[k])*far*near*quiet*visibility
  d.line((qx[k],qy[k],x,y),fill=tuple(round(c*b) for c in (151,197,255)),width=1+int(z[k]<.25))
 return Image.alpha_composite(im.convert('RGBA'),hero(t)).convert('RGB')
def render():
 OUT.mkdir(parents=True,exist_ok=True);path=OUT/'01-hp-circle-to-os.mp4'
 p=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-threads','4','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],stdin=subprocess.PIPE)
 for n in range(FPS*DURATION):
  p.stdin.write(frame(n/FPS).tobytes())
  if n%120==0:print(n,'/',FPS*DURATION,flush=True)
 p.stdin.close();assert p.wait()==0
 return path
def preview():
 OUT.mkdir(parents=True,exist_ok=True);sheet=Image.new('RGB',(1440,860),(1,4,12));d=ImageDraw.Draw(sheet)
 for i,t in enumerate((1.2,2.3,3.1,4.3,5.5,6.5,7.6,9,11.5)):
  x=(i%3)*480;y=(i//3)*286
  sheet.paste(frame(t).resize((480,270),Image.Resampling.LANCZOS),(x,y+16));d.text((x+8,y),f'{t:.1f}s',fill=(160,190,225))
 sheet.save(OUT/'storyboard.png')
def native():
 OUT.mkdir(parents=True,exist_ok=True)
 for label,w,h,fps in [('native',480,200,30)]:
  folder=pathlib.Path('/tmp/hp-native-morph-frames');folder.mkdir(exist_ok=True)
  for n in range(6*fps+1):
   hero(n/fps*1.4,native=True).crop((480,280,1440,680)).resize((w,h),Image.Resampling.LANCZOS).save(folder/f'frame-{n:03d}.png')
  print(label,'done',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true');p.add_argument('--native',action='store_true');args=p.parse_args()
 preview() if args.preview else native() if args.native else render()
