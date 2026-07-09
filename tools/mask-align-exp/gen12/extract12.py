#!/usr/bin/env python3
"""extract12 — role-driven, palette-agnostic extractor for the gen12 batch.

Everything (guide keys, backdrop, control ROLES, optional template geometry) is read from
<assets-dir>/results.json — ZERO hardcoded colours OR control names. Ports the proven run9/10/11
machinery: mask-colour correlation, largest-CC, fill-holes on 2-state toggle cells,
strip-by-colour-identity with MAXW distrust + paint-detected fallback, snap-X-only, circle-fit
knob sockets + matte-hole-CENTROID seat centre, rrect-fit toggle/slider, coverage-span seek
travel, global drift, leak/emptiness/ring gates.

NEW in gen12:
  * roles: button | knob | slider | toggle | region  (config-driven, not name-hardcoded)
  * templateless mode: results.json has no `template` → skip template fallback + drift metric,
    trust the mask+gradient fits directly (post-hoc detection only)
  * silhouette state-registration for multi-state sprites (toggle): align the ON cut onto the OFF
    cut by scale + (dx,dy) maximising silhouette IoU → regions[toggle].stateAlign (OFF-frame px),
    so the player's two states share one housing. (Supersedes the wild11 face-centroid heuristic.)

Usage:  python3 extract12.py <assets-dir>        e.g.  gen12/assets-fa-pod
Run once before biref (no seats yet), then again after biref (picks up matte seats + stateAlign).
"""
import os, sys, json
import numpy as np
from PIL import Image
from scipy import ndimage

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
BIREF = OUT + "_biref"
RES = json.load(open(os.path.join(OUT, "results.json")))
KEYS = {k: tuple(v) for k, v in RES["keys"].items()}
HB = {k: KEYS[k] for k in RES["buttons"]}          # baked icon buttons
SP = {k: KEYS[k] for k in RES["sprites"]}          # moving parts (knob/slider/toggle)
SC = {k: KEYS[k] for k in RES["extras"]}           # regions (visualizer / album_art / screen)
NAMES = list(HB) + list(SP) + list(SC)
COLS = np.array([KEYS[k] for k in NAMES])
DEVF = RES["devFrac"]
BGC = np.array(RES["backdrop"])
ROLES = RES.get("roles", {})
KNOBS = [k for k in SP if ROLES.get(k) == "knob"] or [k for k in SP if k == "vol"]
SLIDER = next((k for k in SP if ROLES.get(k) == "slider"), "seek" if "seek" in SP else None)
TOGGLE = next((k for k in SP if ROLES.get(k) == "toggle"), "tog" if "tog" in SP else None)
TEMPLATED = bool(RES.get("template"))

m = np.asarray(Image.open(os.path.join(OUT, "mask.png")).convert("RGB")).astype(int)
MH, MW, _ = m.shape; flat = m.reshape(-1, 3)
sat = ((flat.max(1) - flat.min(1)) > 55) & (flat.max(1) > 90)
d = np.sqrt(((flat[:, None, :] - COLS[None, :, :]) ** 2).sum(2))
assign = np.where(sat & (d.min(1) < 95), d.argmin(1), -1).reshape(MH, MW)


def bb(ys, xs):
    if len(xs) < 120: return None
    x0, x1 = np.percentile(xs, [2, 98]); y0, y1 = np.percentile(ys, [2, 98])
    return [float(x0) / MW, float(y0) / MH, float(x1 - x0) / MW, float(y1 - y0) / MH]


def largest_cc_bbox(m2d):
    lbl, n = ndimage.label(m2d)
    if n == 0: return None
    sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
    ys, xs = np.where(lbl == 1 + int(np.argmax(sizes)))
    return bb(ys, xs)


YY = np.arange(MH)[:, None]
regs = {}
for i, name in enumerate(NAMES):
    ys, xs = np.where(assign == i)
    if len(xs) < 120: regs[name] = None; continue
    dev = largest_cc_bbox((assign == i) & (YY < DEVF * MH))
    if name in SC:                                   # region: device only, no strip cell
        regs[name] = {"device": dev, "strip": []}; continue
    stripmask = (assign == i) & (YY >= DEVF * MH)
    if name == TOGGLE:                               # two strip cells (OFF left, ON right)
        stripmask = ndimage.binary_fill_holes(stripmask)
        lbl, nc = ndimage.label(stripmask); cells = []
        for c in range(1, nc + 1):
            ys2, xs2 = np.where(lbl == c)
            if len(xs2) < 120: continue
            cells.append((xs2.min(), bb(ys2, xs2)))
        cells.sort(key=lambda t: t[0]); strip = [c[1] for c in cells[:2]]
        while len(strip) < 2: strip.append(None)
    else:
        strip = [largest_cc_bbox(stripmask)] if stripmask.sum() > 120 else []
    regs[name] = {"device": dev, "strip": strip}

# --- MASK IS A GUIDE: detect real painted PARTS in the strip band as fallback for omitted cells
paint = np.asarray(Image.open(os.path.join(OUT, "paint.png")).convert("RGB"))
PPH, PPW = paint.shape[:2]; y0strip = int(PPH * DEVF)
band = paint[y0strip:]
bright = np.abs(band.astype(int) - BGC).max(2) > 55
col = bright.sum(0) > (band.shape[0] * 0.04)
gap = int(PPW * 0.015); runs = []; i = 0; N = len(col)
while i < N:
    if col[i]:
        j = i
        while j < N and (col[j] or (j + 1 < N and any(col[j:min(N, j + gap)]))): j += 1
        runs.append((i, j)); i = j
    else: i += 1


def part_bbox(x0, x1):
    sub = bright[:, x0:x1]; ys, xs = np.where(sub)
    if len(xs) < 50: return None
    return [float(x0 + xs.min()) / PPW, float(y0strip + ys.min()) / PPH,
            float(xs.max() - xs.min()) / PPW, float(ys.max() - ys.min()) / PPH]


parts = [part_bbox(a, b) for (a, b) in runs if part_bbox(a, b)]
# strip order: knobs, slider thumb, toggle OFF, toggle ON
order = list(KNOBS)
if SLIDER: order.append(SLIDER)
if TOGGLE: order += [TOGGLE + "_off", TOGGLE + "_on"]
MAXW = 0.16
def missing(name, idx=0):
    r = regs.get(name); s = r and r.get("strip")
    if not (s and len(s) > idx and s[idx]): return True
    return s[idx][2] > MAXW
for i, name in enumerate(order):
    if i >= len(parts): continue
    if TOGGLE and name.startswith(TOGGLE):
        regs[TOGGLE] = regs.get(TOGGLE) or {"device": None, "strip": [None, None]}
        idx = 0 if name.endswith("_off") else 1
        while len(regs[TOGGLE]["strip"]) < 2: regs[TOGGLE]["strip"].append(None)
        if missing(TOGGLE, idx): regs[TOGGLE]["strip"][idx] = parts[i]
    else:
        regs[name] = regs.get(name) or {"device": None, "strip": []}
        if missing(name): regs[name]["strip"] = [parts[i]]

# SNAP-TO-PAINT (X only). Vivid-body distrust: if >55% of the window is saturated, no icon to snap.
paintrgb = np.asarray(Image.open(os.path.join(OUT, "paint.png")).convert("RGB")).astype(int)
PPH2, PPW2 = paintrgb.shape[:2]
def snap_to_paint(name, b):
    cx = b[0] + b[2] / 2; cy = b[1] + b[3] / 2
    wx0 = int(max(0, (cx - b[2] * 0.6) * PPW2)); wx1 = int(min(PPW2, (cx + b[2] * 0.6) * PPW2))
    wy0 = int(max(0, (cy - b[3] * 0.6) * PPH2)); wy1 = int(min(PPH2, (cy + b[3] * 0.6) * PPH2))
    win = paintrgb[wy0:wy1, wx0:wx1]
    if win.size == 0: return b
    mx = win.max(2); mn = win.min(2)
    if name in HB:
        sel = (mx - mn) > 60
        if sel.mean() > 0.55: return b
    else:
        sel = (mx < max(45.0, float(np.median(mx)) * 0.6)) & (np.abs(win - BGC).max(2) > 55)
    ys, xs = np.where(sel)
    if len(xs) < 80: return b
    ncx = (wx0 + xs.mean()) / PPW2
    return [ncx - b[2] / 2, b[1], b[2], b[3]]
for name in NAMES:
    r = regs.get(name)
    if r and r.get("device"):
        r["maskDevice"] = list(r["device"])
        if name in SC: continue                      # regions: no snap
        r["device"] = snap_to_paint(name, r["device"])

# --- SEAT: matte alpha-hole CENTROID for knob sockets
_mp = os.path.join(BIREF, "global-matte.png")
_holes = []
if os.path.exists(_mp):
    _gm = np.asarray(Image.open(_mp).convert("RGBA").resize((PPW2, PPH2)))[:, :, 3] > 90
    _lbl, _n = ndimage.label(_gm)
    if _n:
        _sz = ndimage.sum(np.ones_like(_lbl), _lbl, range(1, _n + 1))
        _dev = _lbl == 1 + int(np.argmax(_sz))
        _hl, _hn = ndimage.label(~_gm)
        _edge = set(np.unique(np.r_[_hl[0], _hl[-1], _hl[:, 0], _hl[:, -1]]))
        for _h in range(1, _hn + 1):
            if _h in _edge: continue
            _hm = _hl == _h
            if _hm.sum() < 800: continue
            _ring = ndimage.binary_dilation(_hm, iterations=2) & ~_hm
            if _dev[_ring].mean() < 0.5: continue
            _dt = ndimage.distance_transform_edt(_hm)
            _hys, _hxs = np.where(_hm)
            _holes.append((float(_hxs.mean()), float(_hys.mean()), float(_dt.max())))

# template fallback (templated mode only) for a cell the mask omitted
template = RES.get("template", {})
DEFSZ = RES.get("defsz", {})
if TEMPLATED:
    for k in list(SP) + list(HB):                # buttons too: an omitted mask blob still gets a hotspot
        r = regs.get(k)
        if (not r or not r.get("device")) and k in template:
            t = template[k]; s = DEFSZ.get(k, 0.11)
            regs[k] = {"device": [t[0] - s / 2, t[1] - s / 2, s, s], "strip": (r or {}).get("strip", []),
                       "fromTemplate": True}
    for k in list(SC):
        r = regs.get(k)
        if (not r or not r.get("device")) and (k + "_rect") in RES:
            regs[k] = {"device": list(RES[k + "_rect"]), "strip": []}

# ==== GRADIENT-FIT ALIGNMENT (material-agnostic) ====
paintg = np.asarray(Image.open(os.path.join(OUT, "paint.png")).convert("L")).astype(float)
GH, GW = paintg.shape
gyy, gxx = np.gradient(paintg); gmag = np.hypot(gxx, gyy)
def circle_fit(b):
    cx0 = (b[0] + b[2] / 2) * GW; cy0 = (b[1] + b[3] / 2) * GH; r0 = (b[2] * GW + b[3] * GH) / 4
    best = (0, cx0, cy0, r0)
    ang = np.linspace(0, 2 * np.pi, 72, endpoint=False); ca, sa = np.cos(ang), np.sin(ang)
    for dy in range(int(-r0 * 0.5), int(r0 * 0.5) + 1, 3):
        for dx in range(int(-r0 * 0.5), int(r0 * 0.5) + 1, 3):
            for r in np.arange(r0 * 0.7, r0 * 1.3, 3):
                xs = (cx0 + dx + r * ca).astype(int); ys = (cy0 + dy + r * sa).astype(int)
                ok = (xs >= 0) & (xs < GW) & (ys >= 0) & (ys < GH)
                if ok.sum() < 60: continue
                s = gmag[ys[ok], xs[ok]].mean()
                if s > best[0]: best = (s, cx0 + dx, cy0 + dy, r)
    return best
def rrect_perimeter(cx, cy, w, h, n=96):
    r = 0.38 * min(w, h); pts = []
    L = 2 * (w - 2 * r) + 2 * (h - 2 * r) + 2 * np.pi * r
    for s in np.linspace(0, L, n, endpoint=False):
        if s < w - 2 * r: pts.append((cx - w / 2 + r + s, cy - h / 2))
        elif s < w - 2 * r + np.pi * r / 2:
            a = (s - (w - 2 * r)) / r; pts.append((cx + w / 2 - r + r * np.sin(a), cy - h / 2 + r - r * np.cos(a)))
        elif s < w - 2 * r + np.pi * r / 2 + h - 2 * r:
            t = s - (w - 2 * r + np.pi * r / 2); pts.append((cx + w / 2, cy - h / 2 + r + t))
        elif s < w - 2 * r + np.pi * r + h - 2 * r:
            a = (s - (w - 2 * r + np.pi * r / 2 + h - 2 * r)) / r; pts.append((cx + w / 2 - r + r * np.cos(a), cy + h / 2 - r + r * np.sin(a)))
        elif s < 2 * (w - 2 * r) + np.pi * r + h - 2 * r:
            t = s - (w - 2 * r + np.pi * r + h - 2 * r); pts.append((cx + w / 2 - r - t, cy + h / 2))
        elif s < 2 * (w - 2 * r) + np.pi * r * 1.5 + h - 2 * r:
            a = (s - (2 * (w - 2 * r) + np.pi * r + h - 2 * r)) / r; pts.append((cx - w / 2 + r - r * np.sin(a), cy + h / 2 - r + r * np.cos(a)))
        elif s < 2 * (w - 2 * r) + np.pi * r * 1.5 + 2 * (h - 2 * r):
            t = s - (2 * (w - 2 * r) + np.pi * r * 1.5 + h - 2 * r); pts.append((cx - w / 2, cy + h / 2 - r - t))
        else:
            a = (s - (2 * (w - 2 * r) + np.pi * r * 1.5 + 2 * (h - 2 * r))) / r; pts.append((cx - w / 2 + r - r * np.cos(a), cy - h / 2 + r - r * np.sin(a)))
    return np.array(pts)
def rrect_fit(b):
    cx0 = (b[0] + b[2] / 2) * GW; cy0 = (b[1] + b[3] / 2) * GH; w0 = b[2] * GW; h0 = b[3] * GH
    best = (0, cx0, cy0, w0, h0)
    for dy in range(int(-h0 * 0.3), int(h0 * 0.3) + 1, 4):
        for dx in range(int(-w0 * 0.3), int(w0 * 0.3) + 1, 4):
            for sw in np.arange(0.85, 1.35, 0.08):
                for sh in np.arange(0.85, 1.35, 0.08):
                    pts = rrect_perimeter(cx0 + dx, cy0 + dy, w0 * sw, h0 * sh)
                    xs = pts[:, 0].astype(int); ys = pts[:, 1].astype(int)
                    ok = (xs >= 0) & (xs < GW) & (ys >= 0) & (ys < GH)
                    if ok.sum() < 70: continue
                    s = gmag[ys[ok], xs[ok]].mean()
                    if s > best[0]: best = (s, cx0 + dx, cy0 + dy, w0 * sw, h0 * sh)
    return best

drift_samples = []
for k in KNOBS:
    r = regs.get(k)
    if not r or not r.get("maskDevice"): continue
    sc, fx, fy, fr = circle_fit(r["maskDevice"])
    mb = r["maskDevice"]; mcx = (mb[0] + mb[2] / 2) * GW; mcy = (mb[1] + mb[3] / 2) * GH
    bw = mb[2] * GW; bh = mb[3] * GH
    hc = [h for h in _holes if abs(h[0] - fx) < bw and abs(h[1] - fy) < bh and 0.4 * fr < h[2] < 1.4 * fr]
    if hc: fx, fy = min(hc, key=lambda t: (t[0] - fx) ** 2 + (t[1] - fy) ** 2)[:2]
    drift_samples.append((fx - mcx, fy - mcy))
    r["device"] = [(fx - fr) / GW, (fy - fr) / GH, 2 * fr / GW, 2 * fr / GH]
    r["seat"] = [fx / GW, fy / GH, fr / GW]
    print(f"[circle-fit] {k}: ({fx:.0f},{fy:.0f}) r={fr:.0f}px (mask offset {fx - mcx:+.0f},{fy - mcy:+.0f}px)")
if drift_samples:
    gdx = float(np.median([d[0] for d in drift_samples])) / GW
    gdy = float(np.median([d[1] for d in drift_samples])) / GH
    print(f"[global drift] mask->paint = ({gdx * 100:+.2f}%, {gdy * 100:+.2f}%)")
    for k in [*HB] + ([SLIDER] if SLIDER else []) + ([TOGGLE] if TOGGLE else []) + list(SC):
        r = regs.get(k)
        if not r or not r.get("maskDevice"): continue
        mb = r["maskDevice"]
        r["device"] = [mb[0] + gdx, mb[1] + gdy, mb[2], mb[3]]
for k in ([TOGGLE] if TOGGLE else []) + ([SLIDER] if SLIDER else []):
    r = regs.get(k)
    if not r or not r.get("device"): continue
    sc, fx, fy, fw, fh = rrect_fit(r["device"])
    b = r["device"]
    print(f"[rrect-fit] {k}: ({fx:.0f},{fy:.0f}) {fw:.0f}x{fh:.0f}px (was {b[2] * GW:.0f}x{b[3] * GH:.0f})")
    r["device"] = [(fx - fw / 2) / GW, (fy - fh / 2) / GH, fw / GW, fh / GH]

# ---- SEEK GROOVE EXTENT + TRAVEL (coverage span) ----
# The mask/rrect groove bbox routinely UNDERSHOOTS the painted channel, so the thumb stops short
# of the ends. Detect the painted groove's FULL x-extent directly: walk out from centre through
# the dark recess AND its bright bezel rims, stopping only where the body turns bright-and-stays
# (past the rim) or hits near-black backdrop. Set BOTH device x-extent and travel to it.
if SLIDER:
    r = regs.get(SLIDER)
    if r and r.get("device"):
        b = r["device"]
        cyp = (b[1] + b[3] / 2) * GH; hh = max(6, int(b[3] * GH * 0.30)); by0 = int(cyp - hh); by1 = int(cyp + hh)
        pad = int(b[2] * GW * 0.40); bx0 = max(0, int(b[0] * GW) - pad); bx1 = min(GW, int((b[0] + b[2]) * GW) + pad)
        med = np.median(paintrgb[by0:by1, bx0:bx1].max(2), 0)
        dx0 = max(0, int(b[0] * GW) - bx0); dx1 = min(len(med), int((b[0] + b[2]) * GW) - bx0); ctr = (dx0 + dx1) // 2
        Dfloor = float(np.percentile(med[dx0:dx1] if dx1 > dx0 else med, 15))   # recess floor
        bgd = float(np.percentile(med, 2))                     # near-black backdrop level
        recess = Dfloor + 22; rim = Dfloor + 70
        def _walk(step):
            x = ctr; last = ctr; brun = 0; cap = max(8, int((dx1 - dx0) * 0.06))
            while 0 <= x < len(med):
                if med[x] <= bgd + 8: break                    # backdrop → stop hard
                if med[x] < recess: last = x; brun = 0         # dark recess
                elif med[x] > rim:
                    last = x; brun += 1                        # bright bezel rim — keep but count
                    if brun > cap: break                       # sustained bright = past rim into body
                else: brun = 0                                 # mid tone (rim slope) — continue
                x += step
            return last
        lo = bx0 + _walk(-1); hi = bx0 + _walk(+1)
        gx0, gx1 = int(b[0] * GW), int((b[0] + b[2]) * GW)
        if hi - lo < 0.5 * (gx1 - gx0):                        # detection collapsed → keep mask bbox
            lo, hi = gx0, gx1
        r["device"] = [lo / GW, b[1], (hi - lo) / GW, b[3]]    # expand device to the painted groove
        M = int((hi - lo) * 0.02)
        r["travel"] = [round(max(0, lo - M) / GW, 5), round(min(GW, hi + M) / GW, 5)]
        print(f"[travel] {SLIDER} groove {lo}..{hi}px (was bbox {gx0}..{gx1}) -> travel {r['travel']}")

# ---- SLOT ANGLE (rotational placement): a slot following an organic body is tilted, so the part
# must be rotated to match. Major-axis angle from PCA on the slot's mask blob. Knobs are radial.
for k in ([TOGGLE] if TOGGLE else []):
    idx = NAMES.index(k) if k in NAMES else -1
    if idx < 0: continue
    ys, xs = np.where((assign == idx) & (YY < DEVF * MH))   # DEVICE slot only (exclude strip cells!)
    if len(xs) < 200: continue
    xs2 = xs - xs.mean(); ys2 = ys - ys.mean()
    cov = np.array([[(xs2 * xs2).mean(), (xs2 * ys2).mean()], [(xs2 * ys2).mean(), (ys2 * ys2).mean()]])
    w, v = np.linalg.eigh(cov)
    ax = v[:, int(np.argmax(w))]
    ang = float(np.degrees(np.arctan2(ax[1], ax[0])))
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    if abs(ang) > 4 and regs.get(k):
        regs[k]["angle"] = round(ang, 1)
        print(f"[angle] {k}: {ang:+.1f}deg")

# ---- SILHOUETTE STATE-REGISTRATION for the toggle (align ON cut onto OFF cut) ----
def _alpha(path):
    if not os.path.exists(path): return None
    return np.asarray(Image.open(path).convert("RGBA"))[:, :, 3] > 30
if TOGGLE:
    off = _alpha(os.path.join(BIREF, TOGGLE + "_off.png"))
    on = _alpha(os.path.join(BIREF, TOGGLE + "_on.png"))
    if off is not None and on is not None:
        def _bbox(a):
            ys, xs = np.where(a); return xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        ox, oy, ow, oh = _bbox(off); nx, ny, nw, nh = _bbox(on)
        # scale ON to OFF's bbox dims (housing is the invariant), then search dx,dy for max IoU
        onc = Image.fromarray((on[ny:ny + nh, nx:nx + nw] * 255).astype("uint8"))
        onc = onc.resize((ow, oh), Image.NEAREST)
        onb = np.asarray(onc) > 127
        offb = off[oy:oy + oh, ox:ox + ow]
        canvas = np.zeros((oh * 3, ow * 3), bool); canvas[oh:2 * oh, ow:2 * ow] = offb
        best = (-1, 0, 0)
        for dy in range(-12, 13):
            for dx in range(-12, 13):
                sh = np.zeros_like(canvas)
                sh[oh + dy:2 * oh + dy, ow + dx:2 * ow + dx] = onb
                inter = (canvas & sh).sum(); union = (canvas | sh).sum()
                iou = inter / union if union else 0
                if iou > best[0]: best = (iou, dx, dy)
        iou, dx, dy = best
        scale = ow / nw           # ON cut px → OFF-frame px (uniform via bbox-w ratio)
        scale_h = oh / nh
        r = regs.get(TOGGLE)
        if r is not None:
            r["stateAlign"] = {"scaleX": round(scale, 4), "scaleY": round(scale_h, 4),
                               "dx": int(dx), "dy": int(dy), "iou": round(float(iou), 4)}
            print(f"[state-align] {TOGGLE} ON->OFF scale=({scale:.3f},{scale_h:.3f}) d=({dx},{dy}) IoU={iou:.3f}")

json.dump({"devFrac": DEVF, "buttons": list(HB), "sprites": list(SP), "extras": list(SC),
           "roles": ROLES, "templated": TEMPLATED,
           "keys": {k: list(v) for k, v in KEYS.items()}, "keyNames": RES.get("keyNames", {}),
           "regions": regs, "template": template},
          open(os.path.join(OUT, "regions.json"), "w"), indent=2)

# overlay
p = Image.open(os.path.join(OUT, "paint.png")).convert("RGB")
mm = Image.open(os.path.join(OUT, "mask.png")).convert("RGB").resize(p.size)
pa = np.asarray(p).astype(float); ma = np.asarray(mm).astype(float); nb = (ma.max(2) > 45)[..., None]
Image.fromarray((pa * (1 - 0.5 * nb) + ma * (0.5 * nb)).astype("uint8")).save(os.path.join(OUT, "overlay.png"))

# ---- EMPTINESS GATE ----
pr = np.asarray(p).astype(int); PH2, PW2 = pr.shape[:2]
print("emptiness gate (bright-part pixels inside must-be-empty sockets):")
empty_fail = False
for k in list(SP):
    r = regs.get(k)
    if not r or not r.get("device"): continue
    b = r["device"]; sh = 0.18
    x0 = int((b[0] + b[2] * sh) * PW2); x1 = int((b[0] + b[2] * (1 - sh)) * PW2)
    y0 = int((b[1] + b[3] * sh) * PH2); y1 = int((b[1] + b[3] * (1 - sh)) * PH2)
    win = pr[y0:y1, x0:x1]
    if win.size == 0: continue
    brightf = float((win.max(2) > 150).mean())
    verdict = "FAIL - baked part?" if brightf > 0.10 else "ok"
    if brightf > 0.10: empty_fail = True
    print(f"  {k:8} bright-interior {brightf * 100:5.1f}%  {verdict}")
print(f"[emptiness gate] {'FAIL - regenerate' if empty_fail else 'ok'}")

# ---- FIT CHECK ----
print("fit check (device slot vs strip part, w x h ratio):")
for k in KNOBS + ([TOGGLE] if TOGGLE else []):
    r = regs.get(k)
    if not r or not r.get("device") or not r.get("strip") or not r["strip"][0]: continue
    d_ = r["device"]; s = r["strip"][0]
    rw = d_[2] / s[2]; rh = d_[3] / s[3]
    flag = " <- MISMATCH >15%" if abs(1 - rw) > 0.15 or abs(1 - rh) > 0.15 else ""
    print(f"  {k:8} slot/part w={rw:.2f} h={rh:.2f}{flag}")

# ==== GATE SUMMARY (structured PASS/FAIL for the auto-regen loop) ====
missing = [k for k in NAMES if not (regs.get(k) and regs[k].get("device"))]
# seek coverage: travel span vs groove bbox x-extent
seek_cov = None
if SLIDER and regs.get(SLIDER) and regs[SLIDER].get("travel") and regs[SLIDER].get("device"):
    tv = regs[SLIDER]["travel"]; gb = regs[SLIDER]["device"]
    seek_cov = round((tv[1] - tv[0]) / max(1e-6, gb[2]), 3)   # travel span / groove width (~1.0 good)
# state-align sanity
sa = (regs.get(TOGGLE) or {}).get("stateAlign") if TOGGLE else None
sa_ok = bool(sa and 0.7 <= sa.get("scaleX", 0) <= 1.4 and 0.7 <= sa.get("scaleY", 0) <= 1.4 and sa.get("iou", 0) >= 0.9)
# biref parts present
biref_parts = [p for p in ["vol", "seek", TOGGLE + "_off", TOGGLE + "_on"] if TOGGLE
               and os.path.exists(os.path.join(BIREF, p + ".png"))]
need_parts = (KNOBS + ([SLIDER] if SLIDER else []) + ([TOGGLE + "_off", TOGGLE + "_on"] if TOGGLE else []))
biref_ok = all(os.path.exists(os.path.join(BIREF, p + ".png")) for p in need_parts) if os.path.exists(BIREF) else None
reasons = []
if empty_fail: reasons.append("emptiness")
if missing: reasons.append("missing:" + ",".join(missing))
if seek_cov is not None and seek_cov < 0.7: reasons.append(f"seek-cov={seek_cov}")
if TOGGLE and not sa_ok and sa is not None: reasons.append("state-align")
if biref_ok is False: reasons.append("biref-parts")
gate = {"empty_ok": not empty_fail, "controls": len(NAMES) - len(missing), "controls_total": len(NAMES),
        "missing": missing, "seek_cov": seek_cov, "state_align_ok": sa_ok, "biref_ok": biref_ok,
        "leak": RES.get("leak"), "reasons": reasons,
        "PASS": (not empty_fail) and (not missing) and (seek_cov is None or seek_cov >= 0.7)
                and (biref_ok is not False) and (RES.get("leak", 0) is None or RES.get("leak", 0) <= 0.003)}
R2 = json.load(open(os.path.join(OUT, "regions.json"))); R2["gate"] = gate
json.dump(R2, open(os.path.join(OUT, "regions.json"), "w"), indent=2)
print(f"[GATE] {'PASS' if gate['PASS'] else 'FAIL'} "
      f"controls={gate['controls']}/{gate['controls_total']} seek_cov={seek_cov} "
      f"empty={'ok' if not empty_fail else 'FAIL'} align={'ok' if sa_ok else 'x'} "
      f"reasons={reasons or 'none'}")
