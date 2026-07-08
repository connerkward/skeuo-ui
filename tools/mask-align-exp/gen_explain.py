#!/usr/bin/env python3
"""Draw exactly how correlation reads the mask — and where the seek bug was. Produces:
  annotated.png  — paint | mask side by side, EVERY extracted region bbox drawn on BOTH (same coords),
                   labelled by control + hex, so you can see the mask is a near-perfect locator.
  seek-bug.png   — the paint strip with the OLD (order-based, WRONG) seek box vs the NEW (mask-colour) box."""
import os, json
from PIL import Image, ImageDraw, ImageFont

OUT=os.path.join(os.path.dirname(__file__),"assets8")
EXP=os.path.join(os.path.dirname(__file__),"explain"); os.makedirs(EXP,exist_ok=True)
HB={"prev":(255,90,60),"play":(0,120,255),"next":(240,180,0),"stop":(170,80,255)}
SP={"vol":(0,190,90),"bal":(0,200,220),"seek":(255,140,30),"tog":(255,90,160)}
COL={**HB,**SP}
def font(s):
    for f in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf","/System/Library/Fonts/Helvetica.ttc"]:
        try: return ImageFont.truetype(f,s)
        except: pass
    return ImageFont.load_default()

paint=Image.open(os.path.join(OUT,"paint.png")).convert("RGB")
mask=Image.open(os.path.join(OUT,"mask.png")).convert("RGB")
PW,PH=paint.size
R=json.load(open(os.path.join(OUT,"regions.json")))["regions"]

# side-by-side: paint | mask
canvas=Image.new("RGB",(PW*2+8,PH),(20,20,24))
canvas.paste(paint,(0,0)); canvas.paste(mask,(PW+8,0))
d=ImageDraw.Draw(canvas); F=font(46); Fs=font(34)
def draw_box(bbox,col,label,offx):
    if not bbox: return
    x=bbox[0]*PW+offx; y=bbox[1]*PH; w=bbox[2]*PW; h=bbox[3]*PH
    d.rectangle([x,y,x+w,y+h],outline=col,width=7)
    d.text((x+4,y-52),label,fill=col,font=F)
for name in [*HB,*SP]:
    r=R.get(name);
    if not r: continue
    hexc="#%02x%02x%02x"%COL[name]
    for offx in (0,PW+8):                     # draw on BOTH paint and mask (same coords)
        draw_box(r.get("device"),COL[name],f"{name}",offx)
        for j,s in enumerate(r.get("strip") or []):
            if s: draw_box(s,COL[name],f"{name}{'·off' if (name=='tog' and j==0) else '·on' if name=='tog' else ''} cell",offx)
d.text((20,10),"PAINT — same boxes",fill=(255,255,255),font=F)
d.text((PW+28,10),"MASK — the near-perfect locator (each colour = a control)",fill=(255,255,255),font=F)
canvas.save(os.path.join(EXP,"annotated.png")); print("annotated.png",canvas.size)

# seek bug: strip band, OLD (order-based) box vs NEW (mask-colour) box
band=paint.crop((0,int(PH*0.75),PW,PH)); bw,bh=band.size
bd=ImageDraw.Draw(band)
new=R["seek"]["strip"][0]                     # mask-colour: correct thumb
oldx=0.795                                    # what the old order-based code picked (a toggle)
def bandbox(bbox,col,lab,dy=-46):
    x=bbox[0]*PW; y=(bbox[1]-0.75)*PH; w=bbox[2]*PW; h=bbox[3]*PH
    bd.rectangle([x,y,x+w,y+h],outline=col,width=7); bd.text((x,y+dy),lab,fill=col,font=Fs)
bandbox(new,(90,230,120),"NEW seek — by MASK COLOUR (orange cell) ✓")
bd.rectangle([oldx*PW,(0.855-0.75)*PH,(oldx+0.135)*PW,(0.855-0.75+0.09)*PH],outline=(255,80,80),width=7)
bd.text((oldx*PW,(0.855-0.75)*PH-46),"OLD seek — by LEFT-TO-RIGHT ORDER (grabbed a toggle) ✗",fill=(255,80,80),font=Fs)
band.save(os.path.join(EXP,"seek-bug.png")); print("seek-bug.png",band.size)
