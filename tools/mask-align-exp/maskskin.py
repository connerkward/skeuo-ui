#!/usr/bin/env python3
"""The number that MATTERS: mask -> skin. How far each mask blob's centre is from the ACTUAL
painted control's centre (detected in the paint), as % of device width. This should be small
(the mask sits on the paint) — vs template->mask (the model's rearrangement) which is large."""
import os, json
import numpy as np
from PIL import Image

OUT=os.path.join(os.path.dirname(__file__),"assets8")
HB={"prev":(255,90,60),"play":(0,120,255),"next":(240,180,0),"stop":(170,80,255)}
SP={"vol":(0,190,90),"bal":(0,200,220),"seek":(255,140,30),"tog":(255,90,160)}
COL={**HB,**SP}; DEVF=1440/1920
mask=np.asarray(Image.open(os.path.join(OUT,"mask.png")).convert("RGB")).astype(int)
paint=np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("RGB")).astype(int)
MH,MW,_=mask.shape
R=json.load(open(os.path.join(OUT,"regions.json")))["regions"]

def mask_centroid(name):
    c=np.array(COL[name]); dist=np.sqrt(((mask-c)**2).sum(2))
    sel=(dist<70)&(np.arange(MH)[:,None]<DEVF*MH)
    ys,xs=np.where(sel)
    return (xs.mean(),ys.mean()) if len(xs)>100 else None

def paint_centroid(name,bbox):
    # search a padded window around the mask bbox in the PAINT
    pad=0.4
    x0=int(max(0,(bbox[0]-bbox[2]*pad)*MW)); y0=int(max(0,(bbox[1]-bbox[3]*pad)*MH))
    x1=int(min(MW,(bbox[0]+bbox[2]*(1+pad))*MW)); y1=int(min(MH,(bbox[1]+bbox[3]*(1+pad))*MH))
    win=paint[y0:y1,x0:x1];
    if win.size==0: return None
    mx=win.max(2); mn=win.min(2)
    if name in HB:                     # button: the COLOURED icon (saturated pixels)
        sel=(mx-mn)>60
    else:                              # socket/track/toggle: the DARK recessed well
        sel=mx<70
    ys,xs=np.where(sel)
    if len(xs)<50: return None
    return (x0+xs.mean(), y0+ys.mean())

dw=MW  # device width in px = mask/paint half width
print(f"{'control':6} {'mask→skin':>10} {'template→mask':>14}")
tot_ms=0; tot_tm=0; n=0
tmpl=json.load(open(os.path.join(OUT,"regions.json")))["template"]
for name in [*HB,*SP]:
    r=R.get(name);
    if not r or not r.get("device"): continue
    b=r["device"]
    mc=mask_centroid(name); pc=paint_centroid(name,b); tc=tmpl.get(name)
    if mc and pc:
        ms=np.hypot((mc[0]-pc[0])/dw,(mc[1]-pc[1])/dw)*100
    else: ms=float('nan')
    # template→mask (device-region centre vs authored template)
    cx=b[0]+b[2]/2; cy=b[1]+b[3]/2
    tm=np.hypot(cx-tc[0],(cy-tc[1]))*100 if tc else float('nan')
    print(f"{name:6} {ms:9.1f}% {tm:13.1f}%")
    if not np.isnan(ms): tot_ms+=ms; n+=1
    if not np.isnan(tm): tot_tm+=tm
print(f"{'AVG':6} {tot_ms/max(1,n):9.1f}% {tot_tm/max(1,n):13.1f}%")
