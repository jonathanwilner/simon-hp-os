#!/usr/bin/env python3
"""Deterministic HP motion studies. Private brand assets are referenced, never copied."""
import argparse, math, pathlib, subprocess, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
W,H,FPS,DURATION=1920,1080,30,12
KIT=pathlib.Path('/home/jonathan/src/pdf-ppt-kit/assets')
OUT=pathlib.Path('/home/jonathan/Videos/hp-os-motion-variants')
VARIANTS=[('01-orbital-aperture','Orbital aperture',(57,146,255),1.0,0.0),('02-prism-fold','Prism fold',(111,164,255),1.18,0.10),('03-ion-vortex','Ion vortex',(70,219,237),1.48,0.36),('04-silver-slipstream','Silver slipstream',(182,211,255),0.94,0.0),('05-blue-supernova','Blue supernova',(51,112,255),1.65,-0.12)]
FONT=lambda s:ImageFont.truetype(str(KIT/'fonts/ttf/HPFormaDJROffice-Regular.ttf'),s)
fonts={s:FONT(s) for s in [20,23,26,30,38,144]}
def sat(x): return max(0,min(1,x))
def ease(x): x=sat(x);return x*x*(3-2*x)
def mix(a,b,t):return a+(b-a)*t
rng=np.random.default_rng(821)
stars=np.column_stack([rng.uniform(-2.8,2.8,1150),rng.uniform(-1.7,1.7,1150),rng.uniform(.03,1,1150),rng.uniform(.3,1,1150)])
# Use the canonical logo's white forms with its circle as a separate animated part.
logo=Image.open(KIT/'logos/logo_HP_Electric_Blue_keyline.png').convert('RGBA').resize((700,700))
a=np.array(logo); yy,xx=np.mgrid[:700,:700]; inside=((xx-350)**2+(yy-350)**2)<(322**2)
mask=Image.fromarray(np.uint8((a[:,:,0]>190)&(a[:,:,1]>190)&inside)*255)
# Exact premium geometry from HP Brand Central's public reference, reproduced as polygons.
polys=[[(339,0),(238,0),(0,653),(102,653)],[(188,653),(290,653),(401,347),(300,347)],[(487,347),(589,347),(351,999),(250,999)],[(564,653),(666,653),(777,347),(676,347)]]
def premium(d,cx,cy,size,col,morph=1):
 for i,p in enumerate(polys):
  pts=[]
  for x,y in p:
   tx=(x-388.5)*size/999;ty=(y-499.5)*size/999
   # Four light ribbons arrive from the original letter strokes.
   sx=(x-388.5)*size/999*1.4;sy=(y-499.5)*size/999*.50
   pts.append((cx+mix(sx,tx,morph),cy+mix(sy,ty,morph)))
  d.polygon(pts,fill=col)
def text(d,xy,s,size,col,anchor='mm'):d.text(xy,s,font=fonts[size],fill=col,anchor=anchor)
def frame(t,v):
 slug,title,accent,density,twist=VARIANTS[v]
 # Dim radial atmosphere leaves a quiet center and luminous edge depth.
 im=Image.new('RGB',(W,H),(1,4,13));d=ImageDraw.Draw(im)
 launch=ease((t-6.6)/1.8);settle=ease((t-10.5)/1.5)
 cx=960+42*math.sin(t*.42)*twist;cy=485+20*math.cos(t*.38)*twist
 travel=t*.055 + max(0,t-6.6)**2*.21*density
 z=(stars[:,2]-travel)%1+.055
 ang=twist*travel*.34
 xx=stars[:,0]*math.cos(ang)-stars[:,1]*math.sin(ang); yy=stars[:,0]*math.sin(ang)+stars[:,1]*math.cos(ang)
 px=cx+xx/z*390;py=cy+yy/z*390
 tail=.007+launch*(.14+.07*density)*(1-.45*settle)
 qx=cx+xx/(z+tail)*390;qy=cy+yy/(z+tail)*390
 for k in range(int(680*density)):
  x,y=px[k],py[k]
  if -100<x<W+100 and -100<y<H+100:
   b=stars[k,3]*(.85+.65*launch)*min(1,.65/z[k])
   col=tuple(int((c*.5+127)*b) for c in accent)
   width=1+(z[k]<.28)
   d.line((qx[k],qy[k],x,y),fill=col,width=width)
   if z[k]<.2:d.ellipse((x-1,y-1,x+1,y+1),fill=(210,231,255))
 # Main mark and lettering are vector/text layers with a soft blue optical glow.
 ink=Image.new('RGBA',(W,H));g=ImageDraw.Draw(ink)
 appear=ease(t/.8);detach=ease((t-1.7)/1.65);word=ease((t-2.25)/1.1);fly=ease((t-6.7)/2.0)
 ox,oy=1053,440
 rx=mix(960,ox,detach);ry=mix(460,oy,detach);rr=mix(117,51,detach)
 if t<6.9:
  if v==1:ry-=math.sin(detach*math.pi)*78
  if v==2:rx+=math.sin(detach*math.pi)*100
  if v==4:rr+=math.sin(detach*math.pi)*55
  opacity=appear*(1-ease((t-6.4)/.65))
  squash=1-.72*math.sin(detach*math.pi) if v==1 else 1
  g.ellipse((rx-rr*squash,ry-rr,rx+rr*squash,ry+rr),outline=(*accent,int(255*opacity)),width=3)
  if v in (0,2,4):
   for j in range(2):
    r=rr+8+j*7;start=(t*55+j*155)%360
    g.arc((rx-r,ry-r,rx+r,ry+r),start,start+85,fill=(*accent,int(85*opacity)),width=1)
  if detach<1:
   size=int(mix(234,185,detach));lm=mask.resize((size,size),Image.Resampling.LANCZOS)
   lm=lm.point(lambda a:int(a*appear*(1-detach)))
   ink.paste((244,249,255), (int(mix(960,820,detach)-size/2),int(mix(460,440,detach)-size/2)),lm)
 # HP-OS exact title; O is an animated outline carrying the original circle.
 alpha=int(255*word*(1-ease((t-6.55)/.85)))
 if alpha:
  text(g,(990,440),'HP-',144,(247,250,255,alpha),'rm')
  text(g,(1115,440),'S',144,(247,250,255,alpha),'lm')
  # O ring remains after the logo circle has reached the letter position.
  if t>3.35:g.ellipse((1002,389,1104,491),outline=(247,250,255,alpha),width=8)
 # Readable login controls with genuine animation state, concept authentication only.
 ui=ease((t-3.6)/.65)*(1-ease((t-6.45)/.4))
 if ui:
  text(g,(960,600),'Welcome back',30,(224,234,248,int(ui*255)))
  g.rounded_rectangle((760,644,1160,708),radius=16,fill=(11,22,43,int(ui*240)),outline=(88,115,157,int(ui*160)),width=1)
  text(g,(960,676),'• • • • • • • •',26,(230,239,255,int(ui*255)))
  text(g,(960,751),'Sign in  →',26,(*accent,int(ui*255)))
  text(g,(960,825),'HP-OS     ·     English',20,(128,150,180,int(ui*255)))
 # Circle expands into the vanishing point as authentication enters hyperspace.
 if 6.55<t<9.1:
  p=ease((t-6.55)/2.5);r=51+1100*p*p;centerx=mix(ox,960,p);centery=mix(oy,490,p)
  fade=int(230*(1-p))
  g.ellipse((centerx-r,centery-r,centerx+r,centery+r),outline=(*accent,fade),width=max(1,int(8*(1-p))))
  if v==4:
   r2=r*.72;g.ellipse((centerx-r2,centery-r2,centerx+r2,centery+r2),outline=(*accent,fade//2),width=2)
 # The HP letterforms resolve into the exact four-stroke premium mark.
 m=ease((t-6.85)/1.9)
 if m:
  size=mix(160,210,m)*(1+.035*math.sin(t*2)*(1-settle))
  premium(g,960,476,size,(247,251,255,int(255*m)),m)
  text(g,(960,668),'HP-OS',38,(242,247,255,int(255*ease((t-8.25)/1.1))))
  text(g,(960,722),'Welcome',23,(164,187,219,int(255*ease((t-9.3)/.8))))
 # Glow under crisp foreground; small working surface keeps deterministic render cheap.
 glow=ink.resize((480,270)).filter(ImageFilter.GaussianBlur(7)).resize((W,H),Image.Resampling.BILINEAR)
 tint=Image.new('RGBA',(W,H),(*accent,0));tint.putalpha(glow.getchannel('A').point(lambda a:min(255,int(a*1.5))))
 im=Image.alpha_composite(im.convert('RGBA'),tint);im=Image.alpha_composite(im,ink)
 d=ImageDraw.Draw(im)
 text(d,(58,54),f'{v+1:02d} / {title}',23,(146,167,198,255),'lm')
 text(d,(1862,54),'HP-OS · MOTION STUDY',20,(115,136,166,255),'rm')
 text(d,(58,1028),'Concept preview · automatic login sequence for demonstration',20,(102,122,150,255),'lm')
 return im.convert('RGB')
def render(v):
 OUT.mkdir(parents=True,exist_ok=True);path=OUT/(VARIANTS[v][0]+'.mp4')
 proc=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],stdin=subprocess.PIPE)
 for n in range(FPS*DURATION):
  im=frame(n/FPS,v);proc.stdin.write(im.tobytes())
  if n%90==0:print(VARIANTS[v][0],n,flush=True)
 proc.stdin.close();assert proc.wait()==0
 return path
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--variant',type=int);p.add_argument('--preview',action='store_true');a=p.parse_args()
 if a.preview:
  sheet=Image.new('RGB',(1600,1000),(4,8,18))
  for v in range(5):
   for j,t in enumerate([.9,3.5,5.3,8.1,10.5]):sheet.paste(frame(t,v).resize((320,200)),(j*320,v*200))
  sheet.save(OUT/'comparison.png')
 else:
  for v in ([a.variant-1] if a.variant else range(5)):render(v)
