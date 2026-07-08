#!/usr/bin/env python3
"""Compare two sprite-cutting strategies on the run8 paint:
  A) ONE BiRefNet pass over the ENTIRE paint (device + sprite sheet) → then MASK CORRELATION
     (connected-component islands of the global matte, assigned to controls via the mask regions).
  B) MASK CORRELATION first (locate each region) → then BiRefNet PER crop.
Reports per-part cut, cost (fal bills BiRefNet per compute-second), timing, and edge quality."""
import os, re, io, time, json, sys
import requests
import numpy as np
from PIL import Image
from scipy import ndimage

def fal_key():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m=re.match(r"\s*FAL_KEY\s*=\s*(.+)",line)
        if m: return m.group(1).strip().strip('"').strip("'")
    sys.exit("no FAL_KEY")
FAL=fal_key()
BIREF="fal-ai/birefnet/v2"
SRC=os.path.join(os.path.dirname(__file__),"assets8")
OUT=os.path.join(os.path.dirname(__file__),"assets_biref"); os.makedirs(OUT,exist_ok=True)
os.makedirs(os.path.join(OUT,"A"),exist_ok=True); os.makedirs(os.path.join(OUT,"B"),exist_ok=True)

def upload(png_bytes,name="x.png"):
    init=requests.post("https://rest.alpha.fal.ai/storage/upload/initiate",
        headers={"Authorization":f"Key {FAL}","Content-Type":"application/json"},
        json={"file_name":name,"content_type":"image/png"}).json()
    requests.put(init["upload_url"],headers={"Content-Type":"image/png"},data=png_bytes)
    return init["file_url"]

def birefnet(png_bytes):
    url=upload(png_bytes)
    job=requests.post(f"https://queue.fal.run/{BIREF}",
        headers={"Authorization":f"Key {FAL}","Content-Type":"application/json"},
        json={"image_url":url,"model":"General Use (Heavy)","operating_resolution":"2048x2048","output_format":"png"}).json()
    t0=time.time()
    while True:
        s=requests.get(job["status_url"],headers={"Authorization":f"Key {FAL}"}).json().get("status")
        if s=="COMPLETED": break
        if s in ("FAILED","ERROR") or time.time()-t0>180: raise RuntimeError(f"birefnet {s}")
        time.sleep(2)
    out=requests.get(job["response_url"],headers={"Authorization":f"Key {FAL}"}).json()
    img=requests.get(out["image"]["url"]).content
    return img, time.time()-t0

def to_bytes(im):
    b=io.BytesIO(); im.save(b,"PNG"); return b.getvalue()

paint=Image.open(os.path.join(SRC,"paint.png")).convert("RGB"); PW,PH=paint.size
R=json.load(open(os.path.join(SRC,"regions.json"))); DEVF=R["devFrac"]; reg=R["regions"]
# sprite parts (name, bbox) left→right; toggle has two cells
PARTS=[]
for k in ["vol","bal","seek"]:
    s=reg[k]["strip"];
    if s and s[0]: PARTS.append((k,s[0]))
if reg["tog"]["strip"]:
    for i,cell in enumerate(reg["tog"]["strip"]):
        if cell: PARTS.append((("tog_off","tog_on")[i],cell))

timings={"A":{},"B":{}}

# ---------- A: ONE global BiRefNet, then correlate ----------
print("[A] one global BiRefNet over the whole paint…",flush=True)
gA,tA=birefnet(to_bytes(paint)); timings["A"]["birefnet_s"]=round(tA,1); timings["A"]["calls"]=1
open(os.path.join(OUT,"global-matte.png"),"wb").write(gA)
gimg=Image.open(io.BytesIO(gA)).convert("RGBA").resize((PW,PH))
alpha=np.asarray(gimg)[:,:,3]
# strip-band islands → connected components → sort left→right → assign to PARTS order
band0=int(PH*DEVF); bandA=alpha[band0:]>90
lbl,n=ndimage.label(bandA)
comps=[]
for c in range(1,n+1):
    ys,xs=np.where(lbl==c)
    if len(xs)<400: continue
    comps.append((xs.min(),xs.max(),ys.min()+band0,ys.max()+band0))
comps.sort(key=lambda b:b[0])
for (name,_),(x0,x1,y0,y1) in zip(PARTS,comps):
    part=gimg.crop((x0,y0,x1,y1))
    part.save(os.path.join(OUT,"A",f"{name}.png"))
print(f"[A] {tA:.1f}s, correlated {len(comps)} islands to {len(PARTS)} parts",flush=True)

# ---------- B: mask locates each region → BiRefNet per crop ----------
print("[B] per-part BiRefNet…",flush=True); tsum=0
for name,bbox in PARTS:
    pad=0.12
    x=max(0,(bbox[0]-bbox[2]*pad)*PW); y=max(0,(bbox[1]-bbox[3]*pad)*PH)
    w=min(PW-x,bbox[2]*(1+2*pad)*PW); h=min(PH-y,bbox[3]*(1+2*pad)*PH)
    crop=paint.crop((int(x),int(y),int(x+w),int(y+h)))
    rb,tb=birefnet(to_bytes(crop)); tsum+=tb
    Image.open(io.BytesIO(rb)).convert("RGBA").save(os.path.join(OUT,"B",f"{name}.png"))
    print(f"[B] {name} {tb:.1f}s",flush=True)
timings["B"]["birefnet_s"]=round(tsum,1); timings["B"]["calls"]=len(PARTS)

json.dump({"parts":[p[0] for p in PARTS],"timings":timings,
           "note":"BiRefNet fal price = $0.0008/compute-second; A=1 call on full image, B=N calls on crops"},
          open(os.path.join(OUT,"biref.json"),"w"),indent=2)
print("DONE",json.dumps(timings),flush=True)
