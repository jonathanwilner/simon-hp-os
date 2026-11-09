#!/usr/bin/env python3
"""One continuous HP circle -> HP-OS -> premium slash reveal, with optical glow."""
import argparse, functools, hashlib, json, math, os, pathlib, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
W,H,FPS,DURATION=1920,1080,60,14
KIT=pathlib.Path(os.environ.get('HP_BRAND_ASSETS','/home/jonathan/src/pdf-ppt-kit/assets'))
OUT=pathlib.Path(os.environ.get('HP_MOTION_OUTPUT',pathlib.Path.home()/'Videos/hp-logo-morph-v4'))
ACCENT=(48,139,255)
POLYS=[[(339,0),(238,0),(0,653),(102,653)],[(188,653),(290,653),(401,347),(300,347)],[(487,347),(589,347),(351,999),(250,999)],[(564,653),(666,653),(777,347),(676,347)]]
def sat(x):return max(0.,min(1.,x))
def ease(x):
 x=sat(x);return x*x*x*(x*(6*x-15)+10)
def mix(a,b,t):return a+(b-a)*t
def ramp_integral(t,start,duration):
 x=(t-start)/duration
 return 0 if x<=0 else duration*(x-.5) if x>=1 else duration*(x**6-3*x**5+2.5*x**4)
def travel(t):return .022*t+.44*ramp_integral(t,8.0,2.6)-.405*ramp_integral(t,10.6,3.4)
@functools.lru_cache(maxsize=12)
def font(size):return ImageFont.truetype(str(KIT/'fonts/ttf/HPFormaDJROffice-Medium.ttf'),size)
logo=Image.open(KIT/'logos/logo_HP_Electric_Blue_keyline.png').convert('RGBA').resize((700,700),Image.Resampling.LANCZOS)
a=np.array(logo);yy,xx=np.mgrid[:700,:700]
# Original asset's white inner letterforms. Its blue outer circle becomes the O.
inner=Image.fromarray(np.uint8((a[:,:,0]>190)&(a[:,:,1]>190)&(((xx-350)**2+(yy-350)**2)<322**2))*255)
# All five characters are laid out by one font operation, preserving its kerning.
TITLE_FONT=font(152)
TITLE="HP-OS"
TITLE_X=round((W-TITLE_FONT.getlength(TITLE))/2)
TITLE_Y=480-92
wordmask=Image.new('L',(W,H));ImageDraw.Draw(wordmask).text((TITLE_X,TITLE_Y),TITLE,font=TITLE_FONT,fill=255)
omask=Image.new('L',(W,H));ImageDraw.Draw(omask).text((TITLE_X+TITLE_FONT.getlength('HP-'),TITLE_Y),'O',font=TITLE_FONT,fill=255)
obox=omask.getbbox();OCX=(obox[0]+obox[2])/2;OCY=(obox[1]+obox[3])/2
others=ImageChops.subtract(wordmask,omask)
# Radial samples follow the actual Forma O outer and counter contours, not an ellipse.
local_o=Image.new('L',(320,320));local_o.paste(omask.crop(obox),(round(160-(obox[2]-obox[0])/2),round(160-(obox[3]-obox[1])/2)))
angles=np.linspace(0,2*math.pi,360,endpoint=False)
outer=[];counter=[];oa=np.array(local_o)
for angle in angles:
 rr=np.arange(0,150,.25)
 xx=np.clip(np.round(160+np.cos(angle)*rr).astype(int),0,319)
 yy=np.clip(np.round(160+np.sin(angle)*rr).astype(int),0,319)
 hit=rr[oa[yy,xx]>127]
 counter.append(hit.min());outer.append(hit.max())
outer=np.array(outer);counter=np.array(counter)
def ring_mask(m):
 # Supersampling prevents stair-stepping while the circular contour becomes the O.
 im=Image.new('L',(640,640));d=ImageDraw.Draw(im)
 for radii,fill in ((outer,255),(counter,0)):
  start=118 if fill else 115
  radii=start+(radii-start)*m
  pts=[((160+math.cos(a)*r)*2,(160+math.sin(a)*r)*2) for a,r in zip(angles,radii)]
  d.polygon(pts,fill=fill)
 im=im.resize((320,320),Image.Resampling.LANCZOS)
 return Image.blend(im,local_o,ease((m-.86)/.14))
def glow_layer(ink):
 small=ink.resize((480,270),Image.Resampling.LANCZOS);glow=Image.new('RGBA',(480,270))
 for radius,gain in ((8,1.25),(2.3,.65)):
  alpha=small.getchannel('A').filter(ImageFilter.GaussianBlur(radius)).point(lambda p:min(255,round(p*gain)))
  tint=Image.new('RGBA',small.size,(*ACCENT,0));tint.putalpha(alpha);glow=Image.alpha_composite(glow,tint)
 return Image.alpha_composite(glow.resize((W,H),Image.Resampling.BILINEAR),ink)
def hero(t,native=False):
 ink=Image.new('RGBA',(W,H));d=ImageDraw.Draw(ink)
 reveal=ease(t/.95);m=ease((t-1.3)/2.2)
 leave=ease((t-8.0)/1.6)
 shift=0 if native else -145*ease((t-3.7)/1.0)*(1-ease((t-8)/1.6))
 # Once the morph completes, render the entire exact wordmark in a single pass.
 if m>=1:
  mask=wordmask.point(lambda p:round(p*(1-leave)))
  ink.paste((246,250,255),(0,round(shift)),mask)
 else:
  mask=ring_mask(m).point(lambda p:round(p*reveal))
  cx=mix(960,OCX,m);cy=mix(480,OCY,m)
  color=tuple(round(mix(ACCENT[i],(246,250,255)[i],m)) for i in range(3))
  ink.paste(color,(round(cx-160),round(cy-160+shift)),mask)
  oldalpha=reveal*(1-ease((t-1.55)/1.55))
  if oldalpha>0:
   z=round(mix(234,180,m));mask=inner.resize((z,z),Image.Resampling.LANCZOS).point(lambda p:round(p*oldalpha))
   ink.paste((246,250,255),(round(mix(960,815,m)-z/2),round(480-z/2+shift)),mask)
  opacity=ease((t-1.95)/1.55)
  ink.paste((246,250,255),(0,round(shift)),others.point(lambda p:round(p*opacity)))
 slash=ease((t-8.6)/2.0)
 if slash>0:
  size=mix(205,230,slash)
  for p in POLYS:
   d.polygon([(960+(x-388.5)*size/999,480+(y-499.5)*size/999) for x,y in p],fill=(247,251,255,round(slash*255)))
 return glow_layer(ink)
def login_layer(t):
 ink=Image.new('RGBA',(W,H));d=ImageDraw.Draw(ink)
 ui=ease((t-4.0)/.9)*(1-ease((t-8)/.8))
 if ui<=0:return ink
 alpha=lambda v:round(v*ui)
 def text(xy,value,size,color=(233,242,255),anchor='mm'):
  d.text(xy,value,font=font(size),fill=(*color,alpha(255)),anchor=anchor)
 text((960,462),'Jonathan',32)
 d.rounded_rectangle((740,518,1180,582),radius=12,fill=(12,24,43,alpha(250)),outline=(80,144,226,alpha(220)),width=2)
 entered=max(0,min(9,int((t-5.15)/.20)))
 if entered:text((766,549),'• '*entered,27,anchor='lm')
 else:text((766,549),'Password',25,(135,158,190),anchor='lm')
 clicked=ease((t-7.55)/.15)
 d.rounded_rectangle((740,606,1180,666),radius=12,fill=(15,round(mix(94,72,clicked)),round(mix(220,183,clicked)),alpha(255)))
 text((960,636),'Signing in…' if t>=7.55 else 'Sign in',25)
 text((960,716),'English  ·  Session options',19,(132,156,185))
 # Visible pointer moves to Sign in and depresses the button after password entry.
 if t>=6.9:
  move=ease((t-6.9)/.6);x=mix(1250,1088,move);y=mix(760,642,move)
  d.polygon([(x,y),(x+4,y+24),(x+10,y+17),(x+18,y+18)],fill=(240,247,255,alpha(240)))
 return ink
rng=np.random.default_rng(821)
stars=np.column_stack([rng.uniform(-2.8,2.8,850),rng.uniform(-1.7,1.7,850),rng.uniform(.03,1,850),rng.uniform(.3,1,850)])
yy,xx=np.mgrid[:H,:W];radius=np.sqrt(((xx-W/2)/(W/2))**2+((yy-480)/(H*.65))**2)
bg=np.zeros((H,W,3),dtype=np.uint8)
for i,c in enumerate((1,4,12)):bg[:,:,i]=c+np.uint8(np.exp(-radius*2.2)*(2,5,12)[i])
BACKGROUND=Image.fromarray(bg);del bg,xx,yy
def frame(t):
 im=BACKGROUND.copy();d=ImageDraw.Draw(im);launch=ease((t-8.0)/2.6);settle=ease((t-10.6)/3.4)
 depth=travel(t);z=(stars[:,2]-depth)%1+.07
 px=960+stars[:,0]/z*390;py=480+stars[:,1]/z*390
 tail=.003+.18*launch*(1-.83*settle)
 qx=960+stars[:,0]/(z+tail)*390;qy=480+stars[:,1]/(z+tail)*390
 visibility=.18+.82*ease((t-8.0)/2.2)
 for k in range(len(stars)):
  x,y=px[k],py[k]
  if not(-60<x<W+60 and -60<y<H+60):continue
  far=ease((1.07-z[k])/.15);near=ease((z[k]-.07)/.05)
  quiet=.2+.8*min(1,((x-960)/370)**2+((y-480)/250)**2)
  b=stars[k,3]*min(1,.6/z[k])*far*near*quiet*visibility
  d.line((qx[k],qy[k],x,y),fill=tuple(round(c*b) for c in (151,197,255)),width=1+int(z[k]<.25))
 return Image.alpha_composite(Image.alpha_composite(im.convert('RGBA'),hero(t)),login_layer(t)).convert('RGB')
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
 for i,t in enumerate((1.1,2.6,3.5,4.8,6.3,7.7,8.5,10.4,13)):
  x=(i%3)*480;y=(i//3)*286
  sheet.paste(frame(t).resize((480,270),Image.Resampling.LANCZOS),(x,y+16));d.text((x+8,y),f'{t:.1f}s',fill=(160,190,225))
 sheet.save(OUT/'storyboard.png')
def native():
 folder=pathlib.Path('/tmp/hp-native-morph-v4-frames');folder.mkdir(exist_ok=True)
 # 0..105 reveal to exact wordmark; 106..183 are the success-only continuation.
 times=[n/30 for n in range(106)]+[8.0+n/30 for n in range(1,79)]
 for n,t in enumerate(times):
  hero(t,native=True).crop((480,280,1440,680)).resize((480,200),Image.Resampling.LANCZOS).save(folder/f'frame-{n:03d}.png')
 print('native done',len(times),'hold=105 success=106 final=183',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true');p.add_argument('--native',action='store_true');args=p.parse_args()
 preview() if args.preview else native() if args.native else render()
