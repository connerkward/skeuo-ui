#!/usr/bin/env python3
"""Extract regions (+ split the two toggle strip cells), the authored TEMPLATE positions, and an
overlay, for the interactive view + the template↔mask drift metric. Operates on assets9."""
import os, json
import numpy as np
from PIL import Image
from scipy import ndimage

OUT = os.path.join(os.path.dirname(__file__), "assets9")
HB = {"prev":(255,90,60),"play":(0,120,255),"next":(240,180,0),"stop":(170,80,255)}
SP = {"vol":(0,190,90),"bal":(0,200,220),"seek":(255,140,30),"tog":(255,90,160)}
SC = {"screen":(100,255,0)}   # lime — SCREEN/LCD, device-only region (no sprite-strip cell)
NAMES = list(HB)+list(SP)+list(SC)
COLS = np.array([*(HB[k] for k in HB), *(SP[k] for k in SP), *(SC[k] for k in SC)])
DEVF = 1440/1920
# The paint backdrop is CHOSEN per material brief (light backdrop for a dark body and vice versa),
# so keying is by DISTANCE FROM THE KNOWN BACKDROP colour, never an absolute dark/bright rule.
BGC = np.array(json.load(open(os.path.join(OUT,"results.json"))).get("backdrop",[22,22,26]))

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
    if name=="screen":                      # device-only: the screen has NO sprite-strip cell —
        regs[name]={"device":dev,"strip":[]}; continue   # ignore any stray lime in the strip band
    # STRIP CELLS by MASK COLOUR IDENTITY (not left-to-right order): each part's own hue locates it.
    stripmask=(assign==i)&(YY>=DEVF*MH)
    if name=="tog":                         # two pink cells → off (left), on (right)
        # run9 fix: the model drew each toggle cell as an OUTLINE frame + a disconnected
        # lever blob (4 CCs, not 2) — fill holes so a closed ring becomes one solid cell.
        # No-op on run8-style solid-filled cells.
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

# --- MASK IS A GUIDE, tune the cut on the ACTUAL SKIN: the model often omits the knob/seek
# cap cells in the mask strip, so detect the real silver PARTS in the paint's strip band
# (key the dark backdrop → column runs) and use THOSE as the sprite cells (left→right order).
paint = np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("RGB"))
PPH,PPW = paint.shape[:2]; y0strip=int(PPH*DEVF)
band = paint[y0strip:]                                  # strip band
bright = np.abs(band.astype(int)-BGC).max(2) > 55       # far from the KNOWN backdrop = a part
                                                        # (works for light AND dark backdrops)
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
MAXW=0.16   # strip cell pitch is 0.195 — a real part is always narrower; wider = model FLOODED the cell
def missing(name,idx=0):
    r=regs.get(name); s=r and r.get("strip")
    if not (s and len(s)>idx and s[idx]): return True
    return s[idx][2]>MAXW                   # flooded/oversized mask cell → distrust it, use the paint part
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
    if name in HB:
        sel=(mx-mn)>60                             # button icon (saturated)
    else:
        # socket = a recessed well: clearly darker than the LOCAL body tone (window median) —
        # relative, not absolute — and never a backdrop pixel (distance from known backdrop).
        sel=(mx < max(45.0, float(np.median(mx))*0.6)) & (np.abs(win-BGC).max(2)>55)
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
        if name=="screen": continue                  # screen: NO snap — the dark-well heuristic was built
        # for small sockets; on a region this large the window's dark selection can pick up backdrop /
        # bezel shadow. The raw mask bbox is kept (mask drift here is well under the region's size).
        r["device"]=snap_to_paint(name,r["device"])  # paint-true bbox (where the control actually is)

# --- SEAT: measured painted-socket geometry from the global matte's alpha holes -------------
# The one-pass BiRefNet matte (run_biref9) keeps the device body opaque but reads each OPEN
# socket well as background, so every socket becomes an ENCLOSED ALPHA HOLE inside the device
# island. A hole's inscribed circle IS the painted socket: centre + radius, in paint space.
# Seating a part there needs no bbox scaling and no magic ×1.10 — it generalizes to any
# generation/drift/lighting because it reads the painted geometry itself. Matching is by
# centroid against each SOCKET region (mask identity), so matte holes punched through shiny
# chrome buttons are ignored. Emitted ADDITIVELY as regs[name]["seat"] = [cx, cy, r]
# (cx and r normalized by paint WIDTH, cy by paint HEIGHT); consumers fall back to the bbox
# when absent. run_biref9 runs after the first extract9 pass — rerun extract9 to pick seats up.
_mp = os.path.join(os.path.dirname(__file__), "assets9_biref", "global-matte.png")
if os.path.exists(_mp):
    _gm = np.asarray(Image.open(_mp).convert("RGBA").resize((PPW2, PPH2)))[:, :, 3] > 90
    _lbl, _n = ndimage.label(_gm)
    if _n:
        _sz = ndimage.sum(np.ones_like(_lbl), _lbl, range(1, _n + 1))
        _dev = _lbl == 1 + int(np.argmax(_sz))                      # device body island
        _hl, _hn = ndimage.label(~_gm)
        _edge = set(np.unique(np.r_[_hl[0], _hl[-1], _hl[:, 0], _hl[:, -1]]))
        _holes = []
        for _h in range(1, _hn + 1):
            if _h in _edge: continue                                # backdrop touches the border
            _hm = _hl == _h
            if _hm.sum() < 800: continue                            # noise gate
            _ring = ndimage.binary_dilation(_hm, iterations=2) & ~_hm
            if _dev[_ring].mean() < 0.5: continue                   # enclosed by the DEVICE, not a strip part
            _dt = ndimage.distance_transform_edt(_hm)
            _cy, _cx = np.unravel_index(int(np.argmax(_dt)), _dt.shape)
            _holes.append((float(_cx), float(_cy), float(_dt.max())))
        print("socket seats (painted wells via matte alpha-holes):")
        for name in SP:                                             # sockets only, never buttons
            r = regs.get(name)
            if not (r and r.get("device")): continue
            b = r["device"]
            bcx = (b[0] + b[2] / 2) * PPW2; bcy = (b[1] + b[3] / 2) * PPH2
            bw = b[2] * PPW2; bh = b[3] * PPH2
            cand = [(hx, hy, hr) for hx, hy, hr in _holes
                    if abs(hx - bcx) < bw and abs(hy - bcy) < bh             # centroid = mask identity
                    and 0.25 * max(bw, bh) < 2 * hr < 1.6 * max(bw, bh)]     # size plausibility
            if not cand: continue
            hx, hy, hr = min(cand, key=lambda t: (t[0] - bcx) ** 2 + (t[1] - bcy) ** 2)
            r["seat"] = [hx / PPW2, hy / PPH2, hr / PPW2]
            print(f"  {name:5} well @({hx:.0f},{hy:.0f}) r={hr:.0f}px  "
                  f"(bbox-ctr off dx={bcx-hx:+.0f} dy={bcy-hy:+.0f}px; bbox×1.10={1.1*max(bw,bh):.0f}px vs well dia {2*hr:.0f}px)")

# authored template centres (from run9 make_blueprint), normalized to the paint-half (COL_W x H)
T=0.75  # DEV_H/H
template={"prev":[0.35,0.335*T],"play":[0.63,0.36*T],"next":[0.37,0.505*T],"stop":[0.645,0.525*T],
    "vol":[0.36,0.765*T],"bal":[0.64,0.765*T],"seek":[0.50,0.645*T],"tog":[0.50,0.895*T],
    "screen":[0.50,0.15*T]}
# device-socket fallback to template when the mask omitted it (e.g. the toggle socket)
DEFSZ={"vol":0.13,"bal":0.13,"seek":0.02,"tog":0.10}
for k in ["vol","bal","seek","tog"]:
    r=regs.get(k)
    if r and not r.get("device") and k in template:
        t=template[k]; s=DEFSZ[k]
        r["device"]=[t[0]-s/2, t[1]-s/2, s, s]
# screen fallback: authored blueprint rect (0.26..0.74 x, 0.075..0.225 of DEV_H) if the mask omitted it
if not (regs.get("screen") and regs["screen"].get("device")):
    regs["screen"]={"device":[0.26,0.075*T,0.48,0.15*T],"strip":[]}

# ==== CIRCLE-FIT + GLOBAL DRIFT (the principled alignment pass) ====
# 1) Knob sockets are RADIAL features — fit the socket rim circle by scoring gradient magnitude
#    along candidate circles (mini-Hough). Material/lighting-agnostic: "align a circle with a
#    circle" directly, instead of dark-well heuristics that break per design.
# 2) Estimate ONE global mask→paint drift vector from the confident circle fits (the mask's
#    systematic right bias), and apply it to EVERY control that lacks its own local fit — so
#    nothing ever falls back to a raw drifted bbox.
paintg=np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("L")).astype(float)
GH,GW=paintg.shape
gy,gx=np.gradient(paintg); gmag=np.hypot(gx,gy)
def circle_fit(b):
    # window around the mask bbox, padded ×1.6
    cx0=(b[0]+b[2]/2)*GW; cy0=(b[1]+b[3]/2)*GH; r0=(b[2]*GW+b[3]*GH)/4
    best=(0,cx0,cy0,r0)
    ang=np.linspace(0,2*np.pi,72,endpoint=False); ca,sa=np.cos(ang),np.sin(ang)
    for dy in range(int(-r0*0.5),int(r0*0.5)+1,3):
        for dx in range(int(-r0*0.5),int(r0*0.5)+1,3):
            for r in np.arange(r0*0.7,r0*1.25,3):
                xs=(cx0+dx+r*ca).astype(int); ys=(cy0+dy+r*sa).astype(int)
                ok=(xs>=0)&(xs<GW)&(ys>=0)&(ys<GH)
                if ok.sum()<60: continue
                s=gmag[ys[ok],xs[ok]].mean()
                if s>best[0]: best=(s,cx0+dx,cy0+dy,r)
    return best  # (score, cx, cy, r) in px
drift_samples=[]
for k in ["vol","bal"]:
    r=regs.get(k)
    if not r or not r.get("maskDevice"): continue
    sc,fx,fy,fr=circle_fit(r["maskDevice"])
    mb=r["maskDevice"]; mcx=(mb[0]+mb[2]/2)*GW; mcy=(mb[1]+mb[3]/2)*GH
    drift_samples.append((fx-mcx, fy-mcy))
    r["device"]=[(fx-fr)/GW,(fy-fr)/GH,2*fr/GW,2*fr/GH]
    r["seat"]=[fx/GW, fy/GH, fr/GW]
    print(f"[circle-fit] {k}: centre=({fx:.0f},{fy:.0f}) r={fr:.0f}px  (mask ctr offset {fx-mcx:+.0f},{fy-mcy:+.0f}px)")
if drift_samples:
    gdx=float(np.median([d[0] for d in drift_samples]))/GW
    gdy=float(np.median([d[1] for d in drift_samples]))/GH
    print(f"[global drift] mask→paint = ({gdx*100:+.2f}%, {gdy*100:+.2f}%) — baseline for all non-fitted controls")
    for k in [*HB,"seek","tog","screen"]:
        r=regs.get(k)
        if not r or not r.get("maskDevice"): continue
        mb=r["maskDevice"]
        r["device"]=[mb[0]+gdx, mb[1]+gdy, mb[2], mb[3]]

# SLOT-EXTENT refinement (runs AFTER the drift baseline — never clobbered by it): the mask
# blob draws ~25% inset of the painted slot, so for the seek groove AND the toggle slot,
# measure the actual dark recess around the drift-corrected centre and use ITS bbox — the
# sprite then scales to the true painted slot, not the under-sized blob.
prgb=np.asarray(Image.open(os.path.join(OUT,"paint.png")).convert("RGB")).astype(int)
for k in ["seek","tog"]:
    r=regs.get(k)
    if not r or not r.get("device"): continue
    b=r["device"]; padx,pady=b[2]*0.5,b[3]*0.5
    wx0=int(max(0,(b[0]-padx)*GW)); wx1=int(min(GW,(b[0]+b[2]+padx)*GW))
    wy0=int(max(0,(b[1]-pady)*GH)); wy1=int(min(GH,(b[1]+b[3]+pady)*GH))
    win=prgb[wy0:wy1,wx0:wx1]; lum=win.max(2)
    floor=float(np.percentile(lum,5))
    dark=lum<floor+35
    lbl,n=ndimage.label(dark)
    if not n: continue
    sizes=ndimage.sum(np.ones_like(lbl),lbl,range(1,n+1))
    ys,xs=np.where(lbl==1+int(np.argmax(sizes)))
    if len(xs)<300: continue
    nb=[(wx0+xs.min())/GW,(wy0+ys.min())/GH,(xs.max()-xs.min())/GW,(ys.max()-ys.min())/GH]
    print(f"[slot-extent] {k}: blob {b[2]*100:.1f}×{b[3]*100:.1f}% → painted slot {nb[2]*100:.1f}×{nb[3]*100:.1f}%")
    r["device"]=nb

json.dump({"devFrac":DEVF,"buttons":list(HB),"sprites":list(SP),"extras":list(SC),
           "regions":regs,"template":template},
          open(os.path.join(OUT,"regions.json"),"w"),indent=2)

# overlay
p=Image.open(os.path.join(OUT,"paint.png")).convert("RGB")
mm=Image.open(os.path.join(OUT,"mask.png")).convert("RGB").resize(p.size)
pa=np.asarray(p).astype(float); ma=np.asarray(mm).astype(float); nb=(ma.max(2)>45)[...,None]
Image.fromarray((pa*(1-0.5*nb)+ma*(0.5*nb)).astype("uint8")).save(os.path.join(OUT,"overlay.png"))

# ---- EMPTINESS GATE: sockets/groove/toggle-slot must be EMPTY dark wells in the paint.
# A baked part (chrome dome/thumb/lever) shows up as bright pixels inside the region. The
# leak gate catches colour; THIS catches the model baking parts in despite the prompt.
pr=np.asarray(p).astype(int); PH2,PW2=pr.shape[:2]
print("emptiness gate (bright-part pixels inside must-be-empty regions):")
empty_fail=False
for k in ["vol","bal","seek","tog"]:
    r=regs.get(k)
    if not r or not r.get("device"): continue
    b=r["device"]; sh=0.18  # inspect the INTERIOR (shrink 18% to ignore the rim)
    x0=int((b[0]+b[2]*sh)*PW2); x1=int((b[0]+b[2]*(1-sh))*PW2)
    y0=int((b[1]+b[3]*sh)*PH2); y1=int((b[1]+b[3]*(1-sh))*PH2)
    win=pr[y0:y1,x0:x1]
    if win.size==0: continue
    # RELATIVE check: an empty well is uniform near its floor tone; a baked part sticks out
    # ABOVE the floor. Absolute bright>150 missed dark-grey parts on dark bodies.
    lum=win.max(2); floor=float(np.percentile(lum,10))
    bright=float((lum>floor+55).mean())
    verdict="FAIL — baked part?" if bright>0.10 else "ok"
    if bright>0.10: empty_fail=True
    print(f"  {k:5} above-floor interior {bright*100:5.1f}% (floor {floor:.0f})  {verdict}")
print(f"[emptiness gate] {'FAIL — regenerate' if empty_fail else 'ok'}")

# ---- FIT CHECK: slot vs strip-part size (the model shrinks on-device sockets ~25% vs parts)
print("fit check (device slot vs strip part, w×h ratio):")
for k in ["vol","bal","tog"]:
    r=regs.get(k)
    if not r or not r.get("device") or not r.get("strip") or not r["strip"][0]: continue
    d=r["device"]; s=r["strip"][0]
    rw=d[2]/s[2]; rh=d[3]/s[3]
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
