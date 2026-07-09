#!/usr/bin/env python3
"""extract10 — palette-agnostic extractor. ALL colours (guide keys, backdrop) and the authored
template geometry come from assets10/results.json (written by run10.py) — ZERO hardcoded
colours. Otherwise the run9 machinery: mask-colour correlation, largest-CC, fill-holes on
toggle cells, strip-by-colour-identity with MAXW distrust gate + paint-detected fallback,
snap-X-only (with a NEW vivid-body distrust: if most of the snap window is saturated there is
no distinct icon to snap to), seek-groove extent, matte-hole seats, emptiness gate, fit check,
drift table."""
import os, json
import numpy as np
from PIL import Image
from scipy import ndimage

OUT = os.path.join(os.path.dirname(__file__), "assets10")
RES = json.load(open(os.path.join(OUT, "results.json")))
KEYS = {k: tuple(v) for k, v in RES["keys"].items()}
HB = {k: KEYS[k] for k in RES["buttons"]}
SP = {k: KEYS[k] for k in RES["sprites"]}
SC = {k: KEYS[k] for k in RES["extras"]}
NAMES = list(HB)+list(SP)+list(SC)
COLS = np.array([KEYS[k] for k in NAMES])
DEVF = RES["devFrac"]
BGC = np.array(RES["backdrop"])

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
    if name=="screen":
        regs[name]={"device":dev,"strip":[]}; continue
    stripmask=(assign==i)&(YY>=DEVF*MH)
    if name=="tog":
        stripmask=ndimage.binary_fill_holes(stripmask)
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

# --- MASK IS A GUIDE: detect the real painted PARTS in the strip band (distance from the
# KNOWN backdrop) as fallback for mask-omitted cells.
paint = np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("RGB"))
PPH,PPW = paint.shape[:2]; y0strip=int(PPH*DEVF)
band = paint[y0strip:]
bright = np.abs(band.astype(int)-BGC).max(2) > 55
col = bright.sum(0) > (band.shape[0]*0.04)
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
order=["vol","bal","seek","tog_off","tog_on"]
MAXW=0.16   # strip pitch is 0.195 — wider = the model FLOODED the cell; distrust it
def missing(name,idx=0):
    r=regs.get(name); s=r and r.get("strip")
    if not (s and len(s)>idx and s[idx]): return True
    return s[idx][2]>MAXW
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

# SNAP-TO-PAINT (X only). NEW for a VIVID body: a saturated-pixel "icon" snap is meaningless
# when the whole body is saturated (lava veins everywhere) — if >55% of the window is
# saturated there is no distinct feature, keep the mask bbox.
paintrgb=np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("RGB")).astype(int)
PPH2,PPW2=paintrgb.shape[:2]
def snap_to_paint(name,b):
    cx=b[0]+b[2]/2; cy=b[1]+b[3]/2
    wx0=int(max(0,(cx-b[2]*0.6)*PPW2)); wx1=int(min(PPW2,(cx+b[2]*0.6)*PPW2))
    wy0=int(max(0,(cy-b[3]*0.6)*PPH2)); wy1=int(min(PPH2,(cy+b[3]*0.6)*PPH2))
    win=paintrgb[wy0:wy1,wx0:wx1]
    if win.size==0: return b
    mx=win.max(2); mn=win.min(2)
    if name in HB:
        sel=(mx-mn)>60
        if sel.mean()>0.55: return b        # vivid body: saturation is everywhere, not an icon
    else:
        sel=(mx < max(45.0, float(np.median(mx))*0.6)) & (np.abs(win-BGC).max(2)>55)
    ys,xs=np.where(sel)
    if len(xs)<80: return b
    ncx=(wx0+xs.mean())/PPW2
    return [ncx-b[2]/2, b[1], b[2], b[3]]   # snap X ONLY (systematic horizontal model drift)
for name in NAMES:
    r=regs.get(name)
    if r and r.get("device"):
        r["maskDevice"]=list(r["device"])
        if name=="screen": continue
        r["device"]=snap_to_paint(name,r["device"])

# --- SEAT: measured painted-socket geometry from the global matte's alpha holes
_mp = os.path.join(os.path.dirname(__file__), "assets10_biref", "global-matte.png")
if os.path.exists(_mp):
    _gm = np.asarray(Image.open(_mp).convert("RGBA").resize((PPW2, PPH2)))[:, :, 3] > 90
    _lbl, _n = ndimage.label(_gm)
    if _n:
        _sz = ndimage.sum(np.ones_like(_lbl), _lbl, range(1, _n + 1))
        _dev = _lbl == 1 + int(np.argmax(_sz))
        _hl, _hn = ndimage.label(~_gm)
        _edge = set(np.unique(np.r_[_hl[0], _hl[-1], _hl[:, 0], _hl[:, -1]]))
        _holes = []
        for _h in range(1, _hn + 1):
            if _h in _edge: continue
            _hm = _hl == _h
            if _hm.sum() < 800: continue
            _ring = ndimage.binary_dilation(_hm, iterations=2) & ~_hm
            if _dev[_ring].mean() < 0.5: continue
            _dt = ndimage.distance_transform_edt(_hm)
            _cy, _cx = np.unravel_index(int(np.argmax(_dt)), _dt.shape)
            _holes.append((float(_cx), float(_cy), float(_dt.max())))
        print("socket seats (painted wells via matte alpha-holes):")
        for name in SP:
            r = regs.get(name)
            if not (r and r.get("device")): continue
            b = r["device"]
            bcx = (b[0] + b[2] / 2) * PPW2; bcy = (b[1] + b[3] / 2) * PPH2
            bw = b[2] * PPW2; bh = b[3] * PPH2
            cand = [(hx, hy, hr) for hx, hy, hr in _holes
                    if abs(hx - bcx) < bw and abs(hy - bcy) < bh
                    and 0.25 * max(bw, bh) < 2 * hr < 1.6 * max(bw, bh)]
            if not cand: continue
            hx, hy, hr = min(cand, key=lambda t: (t[0] - bcx) ** 2 + (t[1] - bcy) ** 2)
            r["seat"] = [hx / PPW2, hy / PPH2, hr / PPW2]
            print(f"  {name:5} well @({hx:.0f},{hy:.0f}) r={hr:.0f}px  "
                  f"(bbox-ctr off dx={bcx-hx:+.0f} dy={bcy-hy:+.0f}px; bbox×1.10={1.1*max(bw,bh):.0f}px vs well dia {2*hr:.0f}px)")

# authored template centres + fallbacks — from results.json (single source: run10.py)
template=RES["template"]
DEFSZ=RES["defsz"]
for k in list(SP):
    r=regs.get(k)
    if r and not r.get("device") and k in template:
        t=template[k]; s=DEFSZ[k]
        r["device"]=[t[0]-s/2, t[1]-s/2, s, s]
if not (regs.get("screen") and regs["screen"].get("device")):
    regs["screen"]={"device":list(RES["screen_rect"]),"strip":[]}

# ==== GRADIENT-FIT ALIGNMENT (material-agnostic — ported/extended from extract9) ====
# The slot rims (gold chrome here) are strong image GRADIENTS whatever the body colour —
# black wells in a black crust defeat dark-pixel and alpha-hole logic, but never edge energy.
#   circles  → knob sockets (mini-Hough on gradient)
#   r-rects  → toggle slot + seek groove (same scoring along a rounded-rect perimeter)
# Then ONE global mask→paint drift vector from the confident fits → baseline for everything else.
paintg=np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("L")).astype(float)
GH,GW=paintg.shape
gyy,gxx=np.gradient(paintg); gmag=np.hypot(gxx,gyy)
def circle_fit(b):
    cx0=(b[0]+b[2]/2)*GW; cy0=(b[1]+b[3]/2)*GH; r0=(b[2]*GW+b[3]*GH)/4
    best=(0,cx0,cy0,r0)
    ang=np.linspace(0,2*np.pi,72,endpoint=False); ca,sa=np.cos(ang),np.sin(ang)
    for dy in range(int(-r0*0.5),int(r0*0.5)+1,3):
        for dx in range(int(-r0*0.5),int(r0*0.5)+1,3):
            for r in np.arange(r0*0.7,r0*1.3,3):
                xs=(cx0+dx+r*ca).astype(int); ys=(cy0+dy+r*sa).astype(int)
                ok=(xs>=0)&(xs<GW)&(ys>=0)&(ys<GH)
                if ok.sum()<60: continue
                s=gmag[ys[ok],xs[ok]].mean()
                if s>best[0]: best=(s,cx0+dx,cy0+dy,r)
    return best
def rrect_perimeter(cx,cy,w,h,n=96):
    # rounded-rect perimeter samples, corner radius 0.38*min(w,h)
    r=0.38*min(w,h); pts=[]
    L=2*(w-2*r)+2*(h-2*r)+2*np.pi*r
    seg=np.linspace(0,L,n,endpoint=False)
    for s in seg:
        if s<w-2*r: pts.append((cx-w/2+r+s, cy-h/2))
        elif s<w-2*r+np.pi*r/2*1:
            a=(s-(w-2*r))/r; pts.append((cx+w/2-r+r*np.sin(a), cy-h/2+r-r*np.cos(a)))
        elif s<w-2*r+np.pi*r/2+h-2*r:
            t=s-(w-2*r+np.pi*r/2); pts.append((cx+w/2, cy-h/2+r+t))
        elif s<w-2*r+np.pi*r+h-2*r:
            a=(s-(w-2*r+np.pi*r/2+h-2*r))/r; pts.append((cx+w/2-r+r*np.cos(a), cy+h/2-r+r*np.sin(a)))
        elif s<2*(w-2*r)+np.pi*r+h-2*r:
            t=s-(w-2*r+np.pi*r+h-2*r); pts.append((cx+w/2-r-t, cy+h/2))
        elif s<2*(w-2*r)+np.pi*r*1.5+h-2*r:
            a=(s-(2*(w-2*r)+np.pi*r+h-2*r))/r; pts.append((cx-w/2+r-r*np.sin(a), cy+h/2-r+r*np.cos(a)))
        elif s<2*(w-2*r)+np.pi*r*1.5+2*(h-2*r):
            t=s-(2*(w-2*r)+np.pi*r*1.5+h-2*r); pts.append((cx-w/2, cy+h/2-r-t))
        else:
            a=(s-(2*(w-2*r)+np.pi*r*1.5+2*(h-2*r)))/r; pts.append((cx-w/2+r-r*np.cos(a), cy-h/2+r-r*np.sin(a)))
    return np.array(pts)
def rrect_fit(b):
    cx0=(b[0]+b[2]/2)*GW; cy0=(b[1]+b[3]/2)*GH; w0=b[2]*GW; h0=b[3]*GH
    best=(0,cx0,cy0,w0,h0)
    for dy in range(int(-h0*0.3),int(h0*0.3)+1,4):
        for dx in range(int(-w0*0.3),int(w0*0.3)+1,4):
            for sw in np.arange(0.85,1.35,0.08):
                for sh in np.arange(0.85,1.35,0.08):
                    pts=rrect_perimeter(cx0+dx,cy0+dy,w0*sw,h0*sh)
                    xs=pts[:,0].astype(int); ys=pts[:,1].astype(int)
                    ok=(xs>=0)&(xs<GW)&(ys>=0)&(ys<GH)
                    if ok.sum()<70: continue
                    s=gmag[ys[ok],xs[ok]].mean()
                    if s>best[0]: best=(s,cx0+dx,cy0+dy,w0*sw,h0*sh)
    return best
drift_samples=[]
for k in ["vol","bal"]:
    r=regs.get(k)
    if not r or not r.get("maskDevice"): continue
    sc,fx,fy,fr=circle_fit(r["maskDevice"])
    mb=r["maskDevice"]; mcx=(mb[0]+mb[2]/2)*GW; mcy=(mb[1]+mb[3]/2)*GH
    drift_samples.append((fx-mcx,fy-mcy))
    r["device"]=[(fx-fr)/GW,(fy-fr)/GH,2*fr/GW,2*fr/GH]
    r["seat"]=[fx/GW,fy/GH,fr/GW]
    print(f"[circle-fit] {k}: ({fx:.0f},{fy:.0f}) r={fr:.0f}px (mask offset {fx-mcx:+.0f},{fy-mcy:+.0f}px)")
if drift_samples:
    gdx=float(np.median([d[0] for d in drift_samples]))/GW
    gdy=float(np.median([d[1] for d in drift_samples]))/GH
    print(f"[global drift] mask→paint = ({gdx*100:+.2f}%, {gdy*100:+.2f}%)")
    for k in [*HB,"seek","tog","screen"]:
        r=regs.get(k)
        if not r or not r.get("maskDevice"): continue
        mb=r["maskDevice"]
        r["device"]=[mb[0]+gdx, mb[1]+gdy, mb[2], mb[3]]
for k in ["tog","seek"]:
    r=regs.get(k)
    if not r or not r.get("device"): continue
    sc,fx,fy,fw,fh=rrect_fit(r["device"])
    b=r["device"]
    print(f"[rrect-fit] {k}: ({fx:.0f},{fy:.0f}) {fw:.0f}×{fh:.0f}px (was {b[2]*GW:.0f}×{b[3]*GH:.0f})")
    r["device"]=[(fx-fw/2)/GW,(fy-fh/2)/GH,fw/GW,fh/GH]

# ---- SEEK TRAVEL (coverage span): the slider thumb's extremes must COVER the slot ends, so
# travel is the slot's full VISUAL x-extent — dark recess core PLUS its bright bezel rim / soft
# rounded end-caps — NOT the rrect/slot fit bbox (locks onto the raised outer plate on run9 and
# onto the inner recess on run10 — wrong in both directions). Material-agnostic by construction:
# find the dark recess core (a tight-gap dark run near centre so a bright rim SPLITS it and dark
# background can't chain in), then per side walk outward — through a bright bezel rim to its
# outer edge if one exists (rimmed grooves), else a small fixed cap margin (dark grooves).
# Errs slightly WIDE (coverage side), never onto the body. Consumers clamp: x0=travel[0],
# x1=travel[1]-thumbW. Reproduces the hand-measured spans (run9 628..1651, run10 641..1648).
r=regs.get("seek")
if r and r.get("device"):
    b=r["device"]
    cyp=(b[1]+b[3]/2)*GH; hh=max(6,int(b[3]*GH*0.30)); by0=int(cyp-hh); by1=int(cyp+hh)
    pad=int(b[2]*GW*0.10); bx0=max(0,int(b[0]*GW)-pad); bx1=min(GW,int((b[0]+b[2])*GW)+pad)
    med=np.median(paintrgb[by0:by1,bx0:bx1].max(2),0)        # column median luminance profile
    dx0=int(b[0]*GW)-bx0; dx1=int((b[0]+b[2])*GW)-bx0; ctr=(dx0+dx1)//2
    D=float(np.percentile(med,10))                         # recess floor level
    def _runs(mask,gap):
        out=[]
        for x in np.where(mask)[0]:
            if out and x-out[-1][1]<=gap: out[-1][1]=int(x)
            else: out.append([int(x),int(x)])
        return out
    cr=[t for t in _runs(med<D+15,6) if t[1]-t[0]>10]      # gap 6: a bright bezel rim breaks the run
    if cr:
        core=min(cr,key=lambda t:0 if t[0]<=ctr<=t[1] else min(abs(t[0]-ctr),abs(t[1]-ctr)))
        cw=core[1]-core[0]; rim=D+70
        def _edge(x0,step):
            x=x0; last=x0
            for _ in range(max(20,int(cw*0.12))):          # search a rim within 12% of core width
                x+=step
                if x<0 or x>=len(med): break
                if med[x]>rim: last=x                       # bright bezel column → extend through it
            return (last+step*4) if last!=x0 else (x0+step*int(cw*0.035))
        lo=bx0+_edge(core[0],-1); hi=bx0+_edge(core[1],+1)
        r["travel"]=[round(lo/GW,5),round(hi/GW,5)]
        print(f"[travel] seek coverage span {lo}..{hi}px (core {bx0+core[0]}..{bx0+core[1]}) -> {r['travel']}")

json.dump({"devFrac":DEVF,"buttons":list(HB),"sprites":list(SP),"extras":list(SC),
           "keys":{k:list(v) for k,v in KEYS.items()},"keyNames":RES.get("keyNames",{}),
           "regions":regs,"template":template},
          open(os.path.join(OUT,"regions.json"),"w"),indent=2)

# overlay
p=Image.open(os.path.join(OUT,"paint.png")).convert("RGB")
mm=Image.open(os.path.join(OUT,"mask.png")).convert("RGB").resize(p.size)
pa=np.asarray(p).astype(float); ma=np.asarray(mm).astype(float); nb=(ma.max(2)>45)[...,None]
Image.fromarray((pa*(1-0.5*nb)+ma*(0.5*nb)).astype("uint8")).save(os.path.join(OUT,"overlay.png"))

# ---- EMPTINESS GATE: sockets/groove/toggle-slot must be EMPTY dark wells in the paint.
pr=np.asarray(p).astype(int); PH2,PW2=pr.shape[:2]
print("emptiness gate (bright-part pixels inside must-be-empty regions):")
empty_fail=False
for k in list(SP):
    r=regs.get(k)
    if not r or not r.get("device"): continue
    b=r["device"]; sh=0.18
    x0=int((b[0]+b[2]*sh)*PW2); x1=int((b[0]+b[2]*(1-sh))*PW2)
    y0=int((b[1]+b[3]*sh)*PH2); y1=int((b[1]+b[3]*(1-sh))*PH2)
    win=pr[y0:y1,x0:x1]
    if win.size==0: continue
    bright=float((win.max(2)>150).mean())
    verdict="FAIL — baked part?" if bright>0.10 else "ok"
    if bright>0.10: empty_fail=True
    print(f"  {k:5} bright-interior {bright*100:5.1f}%  {verdict}")
print(f"[emptiness gate] {'FAIL — regenerate' if empty_fail else 'ok'}")

# ---- FIT CHECK: slot vs strip-part size
print("fit check (device slot vs strip part, w×h ratio):")
for k in ["vol","bal","tog"]:
    r=regs.get(k)
    if not r or not r.get("device") or not r.get("strip") or not r["strip"][0]: continue
    d_=r["device"]; s=r["strip"][0]
    rw=d_[2]/s[2]; rh=d_[3]/s[3]
    flag=" ← MISMATCH >15%" if abs(1-rw)>0.15 or abs(1-rh)>0.15 else ""
    print(f"  {k:5} slot/part w={rw:.2f} h={rh:.2f}{flag}")

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
