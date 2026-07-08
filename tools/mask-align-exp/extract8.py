#!/usr/bin/env python3
"""Extract regions (+ split the two toggle strip cells), the authored TEMPLATE positions, and an
overlay, for the interactive view + the template↔mask drift metric. Operates on assets8."""
import os, json
import numpy as np
from PIL import Image
from scipy import ndimage

OUT = os.path.join(os.path.dirname(__file__), "assets8")
HB = {"prev":(255,90,60),"play":(0,120,255),"next":(240,180,0),"stop":(170,80,255)}
SP = {"vol":(0,190,90),"bal":(0,200,220),"seek":(255,140,30),"tog":(255,90,160)}
NAMES = list(HB)+list(SP); COLS = np.array([*(HB[k] for k in HB), *(SP[k] for k in SP)])
DEVF = 1440/1920

m = np.asarray(Image.open(os.path.join(OUT,"mask.png")).convert("RGB")).astype(int)
MH,MW,_ = m.shape; flat = m.reshape(-1,3)
sat = ((flat.max(1)-flat.min(1))>55)&(flat.max(1)>90)
d = np.sqrt(((flat[:,None,:]-COLS[None,:,:])**2).sum(2))
assign = np.where(sat&(d.min(1)<95), d.argmin(1), -1).reshape(MH,MW)

def bb(ys,xs):
    if len(xs)<120: return None
    x0,x1=np.percentile(xs,[2,98]); y0,y1=np.percentile(ys,[2,98])
    return [float(x0)/MW,float(y0)/MH,float(x1-x0)/MW,float(y1-y0)/MH]
def largest_cc_bbox(m2d):
    # largest connected component only → a stray red icon/pixel cluster can't inflate the bbox
    lbl,n=ndimage.label(m2d)
    if n==0: return None
    sizes=ndimage.sum(np.ones_like(lbl),lbl,range(1,n+1))
    ys,xs=np.where(lbl==1+int(np.argmax(sizes)))
    return bb(ys,xs)
YY=np.arange(MH)[:,None]

regs={}
for i,name in enumerate(NAMES):
    ys,xs=np.where(assign==i)
    if len(xs)<120: regs[name]=None; continue
    dev=largest_cc_bbox((assign==i)&(YY<DEVF*MH))
    # STRIP CELLS by MASK COLOUR IDENTITY (not left-to-right order): each part's own hue locates it.
    stripmask=(assign==i)&(YY>=DEVF*MH)
    if name=="tog":                         # two pink cells → off (left), on (right)
        lbl,nc=ndimage.label(stripmask); cells=[]
        for c in range(1,nc+1):
            ys2,xs2=np.where(lbl==c)
            if len(xs2)<120: continue
            cells.append((xs2.min(),bb(ys2,xs2)))
        cells.sort(key=lambda t:t[0]); strip=[c[1] for c in cells[:2]]
        while len(strip)<2: strip.append(None)
    else:
        strip=[largest_cc_bbox(stripmask)] if stripmask.sum()>120 else []
    regs[name]={"device":dev,"strip":strip}

# --- MASK IS A GUIDE, tune the cut on the ACTUAL SKIN: the model often omits the knob/seek
# cap cells in the mask strip, so detect the real silver PARTS in the paint's strip band
# (key the dark backdrop → column runs) and use THOSE as the sprite cells (left→right order).
paint = np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("RGB"))
PPH,PPW = paint.shape[:2]; y0strip=int(PPH*DEVF)
band = paint[y0strip:]                                  # strip band
bright = band.max(2) > 74                               # non-(dark backdrop)
col = bright.sum(0) > (band.shape[0]*0.04)              # columns with a part
# merge runs across small gaps (< 1.5% width)
gap=int(PPW*0.015); runs=[]; i=0; N=len(col)
while i<N:
    if col[i]:
        j=i
        while j<N and (col[j] or (j+1<N and any(col[j:min(N,j+gap)]))): j+=1
        runs.append((i,j)); i=j
    else: i+=1
def part_bbox(x0,x1):
    sub=bright[:,x0:x1]; ys,xs=np.where(sub)
    if len(xs)<50: return None
    return [float(x0+xs.min())/PPW, float(y0strip+ys.min())/PPH,
            float(xs.max()-xs.min())/PPW, float(ys.max()-ys.min())/PPH]
parts=[part_bbox(a,b) for (a,b) in runs if part_bbox(a,b)]
order=["vol","bal","seek","tog_off","tog_on"]           # expected left→right
# FALLBACK ONLY: mask colour identity (above) is authoritative; use paint-detection to fill a
# sprite cell ONLY when the model OMITTED it from the mask (so we never override a good mask cell).
def missing(name,idx=0):
    r=regs.get(name); s=r and r.get("strip"); return not (s and len(s)>idx and s[idx])
for i,name in enumerate(order):
    if i>=len(parts): continue
    if name.startswith("tog"):
        regs["tog"]=regs.get("tog") or {"device":None,"strip":[None,None]}
        idx=0 if name=="tog_off" else 1
        while len(regs["tog"]["strip"])<2: regs["tog"]["strip"].append(None)
        if missing("tog",idx): regs["tog"]["strip"][idx]=parts[i]
    else:
        regs[name]=regs.get(name) or {"device":None,"strip":[]}
        if missing(name): regs[name]["strip"]=[parts[i]]

# SNAP-TO-PAINT: the model paints the mask ~0.2-0.7% RIGHT of the paint (systematic model drift,
# consistent in direction across generations). Refine each control's device centre onto the ACTUAL
# painted feature so placement ignores the drift — dark well for sockets, saturated icon for buttons.
paintrgb=np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("RGB")).astype(int)
PPH2,PPW2=paintrgb.shape[:2]
def snap_to_paint(name,b):
    cx=b[0]+b[2]/2; cy=b[1]+b[3]/2
    wx0=int(max(0,(cx-b[2]*0.6)*PPW2)); wx1=int(min(PPW2,(cx+b[2]*0.6)*PPW2))
    wy0=int(max(0,(cy-b[3]*0.6)*PPH2)); wy1=int(min(PPH2,(cy+b[3]*0.6)*PPH2))
    win=paintrgb[wy0:wy1,wx0:wx1]
    if win.size==0: return b
    mx=win.max(2); mn=win.min(2)
    sel=((mx-mn)>60) if name in HB else (mx<70)   # button icon (saturated) vs socket (dark well)
    ys,xs=np.where(sel)
    if len(xs)<80: return b                        # not confident → keep the mask bbox
    ncx=(wx0+xs.mean())/PPW2
    # snap X ONLY: the model's drift is horizontal (~+0.5% right); vertically the mask is fine,
    # and the dark-pixel centroid is biased UP (recess shadow hugs the TOP inner rim under
    # top-light), which was seating knobs too high in their sockets.
    return [ncx-b[2]/2, b[1], b[2], b[3]]
for name in NAMES:
    r=regs.get(name)
    if r and r.get("device"):
        r["maskDevice"]=list(r["device"])            # raw mask bbox (where the blob actually is)
        r["device"]=snap_to_paint(name,r["device"])  # paint-true bbox (where the control actually is)

# authored template centres (from run6 make_blueprint), normalized to the paint-half (COL_W x H)
T=0.75  # DEV_H/H
template={"prev":[0.36,0.60*T],"play":[0.55,0.63*T],"next":[0.76,0.57*T],"stop":[0.44,0.84*T],
    "vol":[0.70,0.83*T],"bal":[0.88,0.68*T],"seek":[0.50,0.40*T],"tog":[0.17,0.62*T]}
# device-socket fallback to template when the mask omitted it (e.g. the toggle socket)
DEFSZ={"vol":0.13,"bal":0.13,"seek":0.02,"tog":0.10}
for k in ["vol","bal","seek","tog"]:
    r=regs.get(k)
    if r and not r.get("device") and k in template:
        t=template[k]; s=DEFSZ[k]
        r["device"]=[t[0]-s/2, t[1]-s/2, s, s]

json.dump({"devFrac":DEVF,"buttons":list(HB),"sprites":list(SP),"regions":regs,"template":template},
          open(os.path.join(OUT,"regions.json"),"w"),indent=2)

# overlay
p=Image.open(os.path.join(OUT,"paint.png")).convert("RGB")
mm=Image.open(os.path.join(OUT,"mask.png")).convert("RGB").resize(p.size)
pa=np.asarray(p).astype(float); ma=np.asarray(mm).astype(float); nb=(ma.max(2)>45)[...,None]
Image.fromarray((pa*(1-0.5*nb)+ma*(0.5*nb)).astype("uint8")).save(os.path.join(OUT,"overlay.png"))

# drift sense: template centre vs mask device-bbox centre, in % of half-width
print("control  template→mask drift (% of device width)")
tot=0;n=0
for k in NAMES:
    r=regs.get(k); t=template.get(k)
    if r and r["device"] and t:
        cx=r["device"][0]+r["device"][2]/2; cy=r["device"][1]+r["device"][3]/2
        dpx=(cx-t[0])*100; dpy=(cy-t[1])*100/DEVF; drift=(dpx*dpx+dpy*dpy)**0.5
        print(f"  {k:5} {drift:5.1f}%"); tot+=drift; n+=1
print(f"  AVG   {tot/max(1,n):5.1f}%")
