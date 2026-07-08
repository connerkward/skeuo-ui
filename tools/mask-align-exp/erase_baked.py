#!/usr/bin/env python3
"""GATE-DRIVEN REPAIR: for any must-be-empty region (knob sockets, seek groove, toggle slot)
whose interior FAILS the relative emptiness check, ERASE the baked part — fill above-floor
pixels with the well's own floor tone (+ light noise), feathered. Deterministic, ~free, and
far cheaper than rejection-sampling a model whose 'slider has a thumb' prior keeps winning."""
import os, json, sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

OUT=os.path.join(os.path.dirname(__file__),"assets9")
R=json.load(open(os.path.join(OUT,"regions.json")))
regs=R["regions"]
p=Image.open(os.path.join(OUT,"paint.png")).convert("RGB")
a=np.asarray(p).astype(float); H,W=a.shape[:2]
repaired=[]
for k in ["vol","bal","seek","tog"]:
    r=regs.get(k)
    if not r or not r.get("device"): continue
    b=r["device"]; sh=0.14
    x0=int((b[0]+b[2]*sh)*W); x1=int((b[0]+b[2]*(1-sh))*W)
    y0=int((b[1]+b[3]*sh)*H); y1=int((b[1]+b[3]*(1-sh))*H)
    win=a[y0:y1,x0:x1]; lum=win.max(2)
    floor=np.percentile(lum,10)
    part=(lum>floor+55)
    if part.mean()<=0.10: continue          # empty enough — leave it
    # dilate the part mask, then fill with the floor tone sampled from this well
    part=ndimage.binary_dilation(part,iterations=6)
    floor_px=win[lum<=floor+25]
    tone=floor_px.mean(0) if len(floor_px)>50 else win.reshape(-1,3).min(0)
    noise=np.random.RandomState(7).normal(0,2.5,size=win.shape)
    fill=np.clip(tone[None,None,:]+noise,0,255)
    # feather: blur the binary mask for a soft blend
    soft=ndimage.gaussian_filter(part.astype(float),4)[...,None]
    a[y0:y1,x0:x1]=win*(1-soft)+fill*soft
    repaired.append((k,float(part.mean())))
    print(f"[repair] {k}: erased baked part ({part.mean()*100:.0f}% of interior) → filled with well floor tone")
if repaired:
    Image.fromarray(a.astype("uint8")).save(os.path.join(OUT,"paint.png"))
    # keep the joint in sync (left half = repaired paint)
    j=Image.open(os.path.join(OUT,"joint-4k.png")); j.paste(Image.fromarray(a.astype("uint8")),(0,0)); j.save(os.path.join(OUT,"joint-4k.png"))
    print(f"[repair] saved — {len(repaired)} region(s) repaired")
else:
    print("[repair] nothing to repair")
