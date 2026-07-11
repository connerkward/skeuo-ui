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

# --- HUE-RECOVERY: the model sometimes paints a guide blob DESATURATED/lightened (pipboy vol:
# (255,0,128) requested, (219,121,149) painted -> euclidean dist 128 > the 95 gate, blob dropped).
# HUE survives desaturation, so for any control with NO device blob, re-search unclaimed saturated
# mask pixels by hue distance to the key and take the largest connected component.
import colorsys
_unclaimed = (assign == -1)
_mh = np.asarray(Image.fromarray(m.astype("uint8")).convert("HSV")).astype(int)
for i, name in enumerate(NAMES):
    r = regs.get(name)
    if r and r.get("device"): continue
    kh = int(colorsys.rgb_to_hsv(*[v / 255 for v in KEYS[name]])[0] * 255)
    hd = np.minimum(np.abs(_mh[:, :, 0] - kh), 255 - np.abs(_mh[:, :, 0] - kh))
    cand = _unclaimed & (hd < 18) & (_mh[:, :, 1] > 60) & (_mh[:, :, 2] > 80) & (YY < DEVF * MH)
    if cand.sum() < 400: continue
    bbx = largest_cc_bbox(cand)
    if not bbx: continue
    regs[name] = regs.get(name) or {"device": None, "strip": []}
    regs[name]["device"] = bbx; regs[name]["hueRecovered"] = True
    print(f"[hue-recover] {name}: found desaturated blob (hue-dist search) at {[round(v,3) for v in bbx]}")

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
# OVERLAP-AWARE fallback assignment. Blind index-pairing (parts[i] -> order[i]) misassigns the
# moment the paint band has an extra/merged bright run (a stray glint shifts every later part ->
# the player gets "a switch that isn't on the sprite sheet"). Instead: trusted mask cells CLAIM
# their overlapping paint parts; only unclaimed parts fill the MISSING cells, left-to-right.
def _xov(a, c):
    return max(0.0, min(a[0] + a[2], c[0] + c[2]) - max(a[0], c[0]))
claimed = []
for name in order:
    if TOGGLE and name.startswith(TOGGLE):
        idx = 0 if name.endswith("_off") else 1
        s = (regs.get(TOGGLE) or {}).get("strip") or []
        if len(s) > idx and s[idx] and not missing(TOGGLE, idx): claimed.append(s[idx])
    else:
        s = (regs.get(name) or {}).get("strip") or []
        if s and s[0] and not missing(name): claimed.append(s[0])
free = [p for p in parts if not any(_xov(p, c) > 0.5 * min(p[2], c[2]) for c in claimed)]
free.sort(key=lambda p: p[0]); fi = 0
for name in order:
    if fi >= len(free): break
    if TOGGLE and name.startswith(TOGGLE):
        regs[TOGGLE] = regs.get(TOGGLE) or {"device": None, "strip": [None, None]}
        idx = 0 if name.endswith("_off") else 1
        while len(regs[TOGGLE]["strip"]) < 2: regs[TOGGLE]["strip"].append(None)
        if missing(TOGGLE, idx):
            regs[TOGGLE]["strip"][idx] = free[fi]; fi += 1
            print(f"[strip-fallback] {TOGGLE}[{idx}] <- paint part at x={free[fi-1][0]:.3f}")
    else:
        regs[name] = regs.get(name) or {"device": None, "strip": []}
        if missing(name):
            regs[name]["strip"] = [free[fi]]; fi += 1
            print(f"[strip-fallback] {name} <- paint part at x={free[fi-1][0]:.3f}")

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

# ---- KNOB ZERO-ANGLE: detect the BAKED pointer/indicator angle on the cut cap sprite ----
# The model paints the pointer/notch at whatever angle it feels like; the player then applies
# rotation RELATIVE TO THE CUT, so value-0 shows the baked angle unless we counter-rotate.
# Material-agnostic (relative signals only, no absolute luminance/colour constants): the
# indicator is a LOCAL RADIAL ANOMALY — an angular bin of the cap's own gradient-magnitude
# profile that stands out (robust median+MAD z-score) from the cap's otherwise
# radially-symmetric body (brushed-metal conic texture, knurled rim) — AND is angularly
# NARROW (a carved notch/tab), unlike a directional specular highlight streak which is wide.
# Convention: degrees CLOCKWISE from "up" (12 o'clock), matching CSS rotate(), measured in the
# CUT SPRITE's own axis-aligned frame (same frame build_player.py loads — a tight-crop does not
# rotate, so this angle transfers directly). Returns None when no anomaly clears the bar —
# never guess (placement-invariants-rule).
def detect_knob_zero_deg(cap_path, nbins=180, r_lo=0.28, r_hi=0.94, z_thresh=5.0, prom=2.5, max_width_deg=40):
    if not os.path.exists(cap_path): return None, "no-cap-file"
    arr = np.asarray(Image.open(cap_path).convert("RGBA")).astype(float)
    H, W = arr.shape[:2]
    alpha = arr[:, :, 3] > 40
    if alpha.sum() < 400: return None, "too-few-alpha-px"
    ys, xs = np.where(alpha)
    cy, cx = ys.mean(), xs.mean()
    R = float(np.percentile(np.hypot(xs - cx, ys - cy), 97))
    if R < 8: return None, "too-small"
    gray = arr[:, :, :3].mean(2)
    gyy, gxx = np.gradient(gray); gmag = np.hypot(gxx, gyy)
    YY, XX = np.mgrid[0:H, 0:W]
    dxp = XX - cx; dyp = YY - cy
    rad = np.hypot(dxp, dyp)
    theta = np.degrees(np.arctan2(dxp, -dyp)) % 360.0     # 0 = up, clockwise +ve (CSS rotate() sense)
    ring = alpha & (rad > r_lo * R) & (rad < r_hi * R)
    if ring.sum() < 300: return None, "ring-too-small"
    bw = 360.0 / nbins
    bin_idx = np.clip((theta[ring] / bw).astype(int), 0, nbins - 1)
    prof = np.zeros(nbins); cnt = np.zeros(nbins)
    np.add.at(prof, bin_idx, gmag[ring]); np.add.at(cnt, bin_idx, 1)
    valid = cnt > 3
    if valid.sum() < nbins * 0.5: return None, "insufficient-angular-coverage"
    avgprof = np.full(nbins, np.nan); avgprof[valid] = prof[valid] / cnt[valid]
    med = np.nanmedian(avgprof); mad = np.nanmedian(np.abs(avgprof - med)) + 1e-6
    z = (avgprof - med) / mad; zz = np.nan_to_num(z, nan=-999)
    peak = int(np.nanargmax(zz)); peak_z = float(z[peak])
    others = np.delete(z, peak); others = others[np.isfinite(others)]
    p90 = float(np.nanpercentile(others, 90)) if len(others) else 0.0
    # reject WIDE humps (a directional specular streak along the bezel) — a real carved
    # notch/pointer is angularly narrow. Width = contiguous arc around the peak above half its
    # excess over baseline.
    half = med + (avgprof[peak] - med) * 0.5
    lo = peak
    while zz[(lo - 1) % nbins] > -900 and avgprof[(lo - 1) % nbins] > half and (peak - lo) < nbins // 2: lo -= 1
    hi = peak
    while zz[(hi + 1) % nbins] > -900 and avgprof[(hi + 1) % nbins] > half and (hi - peak) < nbins // 2: hi += 1
    width_deg = (hi - lo) * bw
    if peak_z < z_thresh or (peak_z - p90) < prom:
        return None, f"no-strong-anomaly (z={peak_z:.1f})"
    if width_deg > max_width_deg:
        return None, f"anomaly-too-wide (likely specular, width={width_deg:.0f}deg)"
    return peak * bw, f"z={peak_z:.1f} width={width_deg:.0f}deg"


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
    zdeg, zinfo = detect_knob_zero_deg(os.path.join(BIREF, f"{k}.png"))
    r["knob_zero_deg"] = zdeg
    print(f"[knob-zero] {k}: {zdeg if zdeg is None else round(zdeg, 1)}  ({zinfo})")
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

# ---- DISPLAY-REGION REFIT (role "region": visualizer / album_art) ----
# The model sometimes paints a display-region mask blob OFFSET/OVERSIZED vs the painted window
# (ps1-wild: visualizer blob spanned body left of the glass), so mask-bbox+drift alone draws the
# live canvas outside the painted display. Detect the ACTUAL painted window — the dark glassy
# pane set into the body — within/around the mask bbox (pad 40%) by dark-CC region growing (see
# region_refit docstring), snap when sane (dims within 0.5-2x of the mask bbox), keep mask bbox
# otherwise. Material-agnostic: all levels RELATIVE to the local window stats, never absolute.
def region_refit(b, excl=()):
    """Detect the painted display WINDOW near mask bbox `b` (normalized rect) by region-growing
    the dark glass directly: threshold the padded search window RELATIVE to its local body level
    (no absolute luminance constants), label connected components, pick the CC with max pixel
    overlap with the mask blob rect. Returns (rect, info) or (None, reason). Deterministic —
    a freeform rect-search scorer kept finding adversarial optima (plate outlines, mid-glass
    specular boundaries); a dark CC has no search space to go wrong in.
    `excl` = the OTHER regions' mask-blob rects: two display regions can share ONE glass pane
    (fallout-vault CRT: dark upper half = visualizer, amber lower = album_art) — without the
    exclusion both refits grab the whole pane and end up overlapping. CC detection and edge
    growth both treat the other region's blob as off-limits."""
    x0 = max(0, int((b[0] - b[2] * 0.4) * GW)); x1 = min(GW, int((b[0] + b[2] * 1.4) * GW))
    y0 = max(0, int((b[1] - b[3] * 0.4) * GH)); y1 = min(GH, int((b[1] + b[3] * 1.4) * GH))
    win = paintg[y0:y1, x0:x1]
    if win.size < 2000: return None, "tiny-window"
    # exclude the keyed backdrop — but only backdrop-toned pixels CONNECTED TO THE WINDOW BORDER.
    # On a dark theme the glass itself can sit within the backdrop tone (fa-pod: near-black BG,
    # dark navy glass); real backdrop is outside the device, so border-connectivity separates them.
    bgm = np.abs(paintrgb[y0:y1, x0:x1] - BGC).max(2) <= 45
    lblb, nbg = ndimage.label(bgm)
    border = sorted(set(np.unique(np.r_[lblb[0], lblb[-1], lblb[:, 0], lblb[:, -1]])) - {0})
    notbg = ~np.isin(lblb, border) if border else np.ones(win.shape, bool)
    vals = win[notbg]
    if vals.size < 2000: return None, "no-body"
    body = float(np.percentile(vals, 80)); floor = float(np.percentile(vals, 5))
    if body - floor < 30: return None, "flat"                     # no recess contrast here
    ex = np.zeros(win.shape, bool)
    for e in excl:
        ex0 = max(0, int(e[0] * GW) - x0); ey0 = max(0, int(e[1] * GH) - y0)
        ex1 = min(win.shape[1], int((e[0] + e[2]) * GW) - x0)
        ey1 = min(win.shape[0], int((e[1] + e[3]) * GH) - y0)
        if ex1 > ex0 and ey1 > ey0: ex[ey0:ey1, ex0:ex1] = True
    thr = floor + 0.35 * (body - floor)
    darkm = ndimage.binary_opening((win < thr) & notbg & ~ex, iterations=2)
    lbl, n = ndimage.label(darkm)
    if n == 0: return None, "no-dark-cc"
    bx0 = b[0] * GW - x0; by0 = b[1] * GH - y0
    bx1 = bx0 + b[2] * GW; by1 = by0 + b[3] * GH
    blob_area = max(1.0, b[2] * GW * b[3] * GH)
    best = None
    for c in range(1, n + 1):
        ys, xs = np.where(lbl == c)
        if len(xs) < max(1500, 0.03 * blob_area): continue
        ov = int(((xs >= bx0) & (xs <= bx1) & (ys >= by0) & (ys <= by1)).sum())
        if ov == 0: continue
        if best is None or ov > best[0]: best = (ov, xs, ys)
    if best is None: return None, "no-overlapping-cc"
    _, xs, ys = best
    fx0, fx1 = np.percentile(xs, [1, 99]); fy0, fy1 = np.percentile(ys, [1, 99])
    # EXPAND from the dark CORE to the full recessed pane: a specular sweep can lift part of the
    # glass above the core threshold while staying well below body level (fa-pod: the lower half
    # of each window). Grow each edge while the adjacent strip is still clearly recessed.
    loose = floor + 0.65 * (body - floor)
    fx0, fx1, fy0, fy1 = int(fx0), int(fx1), int(fy0), int(fy1)
    wh, ww = win.shape
    def _rec(y0_, y1_, x0_, x1_):                      # strip is recessed (non-backdrop + below loose)
        s = win[y0_:y1_, x0_:x1_]; nb = notbg[y0_:y1_, x0_:x1_]
        if s.size == 0 or nb.mean() < 0.6: return False
        if ex[y0_:y1_, x0_:x1_].mean() > 0.5: return False   # don't grow into another region's blob
        return float(np.median(s[nb])) < loose
    grew = True
    while grew:
        grew = False
        if fy0 >= 3 and _rec(fy0 - 3, fy0, fx0, fx1): fy0 -= 3; grew = True
        if fy1 <= wh - 4 and _rec(fy1 + 1, fy1 + 4, fx0, fx1): fy1 += 3; grew = True
        if fx0 >= 3 and _rec(fy0, fy1, fx0 - 3, fx0): fx0 -= 3; grew = True
        if fx1 <= ww - 4 and _rec(fy0, fy1, fx1 + 1, fx1 + 4): fx1 += 3; grew = True
    rect = [(x0 + fx0) / GW, (y0 + fy0) / GH, (fx1 - fx0) / GW, (fy1 - fy0) / GH]
    return rect, f"cc {len(xs)}px thr {thr:.0f} loose {loose:.0f} (body {body:.0f} floor {floor:.0f})"
def _iou(a, b):
    x0 = max(a[0], b[0]); y0 = max(a[1], b[1])
    x1 = min(a[0] + a[2], b[0] + b[2]); y1 = min(a[1] + a[3], b[1] + b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / max(1e-9, a[2] * a[3] + b[2] * b[3] - inter)
for k in SC:
    r = regs.get(k)
    if not r or not r.get("device"): continue
    b = r["device"]
    excl = [regs[o].get("maskDevice") or regs[o]["device"] for o in SC
            if o != k and regs.get(o) and regs[o].get("device")]
    fit, info = region_refit(b, excl)
    if fit is None:
        print(f"[region-refit] {k}: kept mask bbox ({info})")
        continue
    ok_size = 0.5 <= fit[2] / b[2] <= 2.0 and 0.5 <= fit[3] / b[3] <= 2.0
    if not ok_size:
        print(f"[region-refit] {k}: kept mask bbox (fit size out of 0.5-2x sanity; {info})")
        continue
    r["device"] = fit
    r["regionRefit"] = {"info": info, "iouVsMask": round(_iou(fit, r.get("maskDevice", b)), 3)}
    print(f"[region-refit] {k}: snapped to painted window px({fit[0]*GW:.0f},{fit[1]*GH:.0f} "
          f"{fit[2]*GW:.0f}x{fit[3]*GH:.0f}) IoU-vs-mask {r['regionRefit']['iouVsMask']} ({info})")

# ---- SEEK GROOVE EXTENT + TRAVEL (coverage span, LEVEL-AWARE) ----
# The mask/rrect groove bbox routinely UNDERSHOOTS the painted channel, and a STEPPED recess
# (deep near-black channel inside a lighter outer trough) defeats fixed offsets from the dark
# floor: the lighter trough sits above Dfloor+22, reads as "body", and the walk stops at the
# dark channel's end instead of the slot's semantic end (fallout-vault). Level-aware version:
#   * base span = the DEVICE-region slot MASK CELL (the model's own declaration of the slot).
#     Walking never happens INSIDE it, which makes the algorithm baked-handle-proof for free
#     (ps1-crunchy, n64-lowpoly: an interior bright handle is never even visited) and immune
#     to dark-channel-vs-backdrop confusion inside the slot.
#   * from each cell edge walk OUTWARD to complete the visual end caps: continue while the
#     smoothed column median is CLEARLY BELOW the LOCAL body plateau (recessed at ANY depth —
#     dark channel or lighter trough) or is a bright bezel rim; stop on a short sustained
#     near-body run, a sustained bright run past the rim, or the designed backdrop COLOUR
#     (distance-from-BGC — a dark channel floor is indistinguishable from a near-black
#     backdrop in raw luminance).
#   * body plateau is PER-SIDE, from the band flanking just outside that end (same rows,
#     backdrop + deep-recess columns excluded) — a darker neighbouring material (porthole's
#     bronze ring beside a brass plate) would poison a single global estimate.
#   * clamp: at most +12% of the cell width beyond the cell per side (wider-than-bbox
#     recessed spans are allowed; textured-body creep is not). Collapse guard unchanged.
if SLIDER:
    r = regs.get(SLIDER)
    if r and r.get("device"):
        b = r["device"]; mb = r.get("maskDevice") or b
        # PORTRAIT slot (h > w*1.3) => VERTICAL slider (wmp-vario "seek goes up and down"):
        # run the identical level-aware walk along Y by transposing the paint + swapping the
        # rect axes; travel is then emitted as a Y-range + "vertical": true for the player.
        VERT = (b[3] * GH) > (b[2] * GW) * 1.3
        if VERT:
            _prgb = np.ascontiguousarray(paintrgb.transpose(1, 0, 2))
            _W, _H = GH, GW
            _b = [b[1], b[0], b[3], b[2]]; _mb = [mb[1], mb[0], mb[3], mb[2]]
        else:
            _prgb = paintrgb; _W, _H = GW, GH; _b = b; _mb = mb
        cyp = (_b[1] + _b[3] / 2) * _H; hh = max(6, int(_b[3] * _H * 0.30)); by0 = int(cyp - hh); by1 = int(cyp + hh)
        ux0 = min(_b[0], _mb[0]); ux1 = max(_b[0] + _b[2], _mb[0] + _mb[2])   # union: fit bbox + mask cell
        pad = int((ux1 - ux0) * _W * 0.40)
        bx0 = max(0, int(ux0 * _W) - pad); bx1 = min(_W, int(ux1 * _W) + pad)
        med = np.median(_prgb[by0:by1, bx0:bx1].max(2), 0)
        med = np.convolve(med, np.ones(7) / 7, mode="same")    # smooth: kill 1-col noise dips
        cdist = np.median(np.abs(_prgb[by0:by1, bx0:bx1] - BGC).max(2), 0)
        gx0, gx1 = int(_b[0] * _W), int((_b[0] + _b[2]) * _W)
        dx0 = max(0, gx0 - bx0); dx1 = min(len(med), gx1 - bx0)
        mx0 = max(0, int(_mb[0] * _W) - bx0); mx1 = min(len(med), int((_mb[0] + _mb[2]) * _W) - bx0)
        if mx1 <= mx0: mx0, mx1 = dx0, dx1
        cw = max(1, mx1 - mx0)
        bgd = float(BGC.max())                                 # designed backdrop level (known)
        slot = med[mx0:mx1]
        Dfloor = float(np.percentile(slot, 10))                # darkest fraction, not centre-biased
        fw = max(30, int(cw * 0.20))                           # per-side flank window
        def _body(sl):                                         # local plateau, recesses+backdrop out
            fl = med[sl]
            fl = fl[(fl > bgd + 25) & (fl > Dfloor + 15)]
            # 70th percentile, NOT median: the flank is often BIMODAL (a neighbour control's
            # shadow next to the raised body plate — quicksilver: knob shadow ~94 / plate ~196).
            # A median lands between the modes, the plate then reads as "bright bezel rim" and
            # the walk rides it ~58px off the slot. The plateau is the RAISED level → p70.
            return float(np.percentile(fl, 70)) if len(fl) >= 8 else None
        bodyL = _body(np.s_[max(0, mx0 - 4 - fw):max(0, mx0 - 4)])
        bodyR = _body(np.s_[mx1 + 4:mx1 + 4 + fw])
        glob = _body(np.s_[:]) or float(np.percentile(med, 85))
        bodyL = bodyL if bodyL is not None else glob; bodyR = bodyR if bodyR is not None else glob
        rimcap = max(8, int(cw * 0.03))                        # TOTAL bright budget per walk — a real
        # bezel end-cap is THIN; 6% of a 950px cell (57px) let a mis-read body plate extend travel
        stopcap = max(6, int(cw * 0.02))                       # sustained near-body = past the slot
        def _walk(edge, step, body):
            below = body - max(14.0, 0.22 * max(0.0, body - Dfloor))   # "clearly below body"
            rimhi = body + 20.0                                # bright bezel above the plateau
            x = edge + step; last = edge; nrun = 0; rrun = 0
            while 0 <= x < len(med):
                if cdist[x] < 30: break                        # backdrop colour → stop hard
                if med[x] < below:
                    # RECESS CONTINUITY: a below-body run only belongs to THIS slot while it is
                    # contiguous with the slot channel. Once the walk has crossed the bright
                    # bezel rim (rrun>0) or a near-body ridge wider than smoothing noise
                    # (nrun>2), a later dark run is a NEIGHBOUR's recess/shadow (quicksilver:
                    # the adjacent knob's dark shadow re-extended travel ~78px past the left
                    # rim) — stop, keep `last` at the rim/channel edge, never resume through.
                    if rrun > 0 or nrun > 2: break
                    last = x; nrun = 0                         # recessed (any depth), contiguous
                elif med[x] > rimhi:
                    last = x; rrun += 1; nrun = 0              # bright bezel rim — keep but count
                    # rrun is CUMULATIVE: the bright end-cap budget never resets, so a carved
                    # frame (diablo) can't ride rim→rim forever; and with the continuity rule
                    # above the walk hard-stops at the first dark run PAST the rim anyway.
                    if rrun > rimcap: break                    # bright budget spent = past the rim
                else:
                    nrun += 1                                  # near-body level
                    if nrun > stopcap: break                   # sustained body = past the slot
                x += step
            return last
        lo = bx0 + _walk(mx0, -1, bodyL); hi = bx0 + _walk(mx1 - 1, +1, bodyR)
        if hi - lo < 0.5 * (gx1 - gx0):                        # detection collapsed → keep fit bbox
            lo, hi = gx0, gx1
        lo = max(lo, bx0 + mx0 - int(0.12 * cw)); hi = min(hi, bx0 + mx1 + int(0.12 * cw))
        M = int((hi - lo) * 0.02)
        tvv = [round(max(0, lo - M) / _W, 5), round(min(_W, hi + M) / _W, 5)]
        if VERT:
            r["device"] = [b[0], lo / _W, b[2], (hi - lo) / _W]   # expand device to the painted groove (Y)
            r["travel"] = tvv; r["vertical"] = True
        else:
            r["device"] = [lo / _W, b[1], (hi - lo) / _W, b[3]]   # expand device to the painted groove (X)
            r["travel"] = tvv; r.pop("vertical", None)
        print(f"[travel] {SLIDER} {'VERTICAL ' if VERT else ''}groove {lo}..{hi}px "
              f"(fit bbox {gx0}..{gx1}, mask cell {bx0 + mx0}..{bx0 + mx1}, "
              f"body L{bodyL:.0f}/R{bodyR:.0f} floor {Dfloor:.0f}) -> travel {r['travel']}")

# ---- SLOT ANGLE (rotational placement): a slot following an organic body is tilted, so the part
# must be rotated to match. Major-axis angle from PCA on the slot's mask blob. Knobs are radial.
def _pca_angle(mask2d):
    # returns (angle_deg, elongation_ratio). A near-round or ragged blob has a MEANINGLESS axis —
    # callers must require strong elongation before trusting the angle (myst read +71deg noise).
    ys, xs = np.where(mask2d)
    if len(xs) < 200: return None
    xs2 = xs - xs.mean(); ys2 = ys - ys.mean()
    cov = np.array([[(xs2 * xs2).mean(), (xs2 * ys2).mean()], [(xs2 * ys2).mean(), (ys2 * ys2).mean()]])
    w, v = np.linalg.eigh(cov); ax = v[:, int(np.argmax(w))]
    a = float(np.degrees(np.arctan2(ax[1], ax[0])))
    a = (a - 180) if a > 90 else (a + 180) if a < -90 else a
    elong = float(np.sqrt(max(w) / max(1e-9, min(w))))
    return a, elong
for k in ([TOGGLE] if TOGGLE else []):
    idx = NAMES.index(k) if k in NAMES else -1
    if idx < 0: continue
    slot_r = _pca_angle((assign == idx) & (YY < DEVF * MH))   # DEVICE slot only (exclude strip cells!)
    if slot_r is None or not regs.get(k): continue
    slot_ang, slot_el = slot_r
    # rotate the PART so ITS OWN long axis lines up with the SLOT's — relative, not absolute. A vertical
    # part in a vertical slot then needs ~0deg (not 90). part axis from the biref OFF cut's alpha.
    poff = os.path.join(BIREF, k + "_off.png")
    part_r = _pca_angle(np.asarray(Image.open(poff).convert("RGBA"))[:, :, 3] > 30) if os.path.exists(poff) else None
    part_ang, part_el = part_r if part_r else (0.0, 0.0)
    # ELONGATION GATE: a weak axis (ratio < 2.0) on EITHER blob means the angle is noise → no rotation
    if slot_el < 2.0 or part_el < 2.0:
        regs[k].pop("angle", None)
        print(f"[angle] {k}: elongation too weak (slot {slot_el:.1f}, part {part_el:.1f}) -> no rotation")
        continue
    rot = slot_ang - (part_ang or 0.0)
    rot = (rot + 90) % 180 - 90            # wrap to (-90, 90]
    # PCA on rough painted blobs is noisy (+-10deg): snap near-cardinal to EXACT 0/90 so a vertical
    # part in a vertical slot never gets a bogus partial rotation. Only true diagonals (>12deg off
    # cardinal) rotate.
    if abs(rot) <= 20: rot = 0.0
    elif abs(rot - 90) <= 20: rot = 90.0
    elif abs(rot + 90) <= 20: rot = -90.0
    if abs(rot) > 0 and regs.get(k):
        regs[k]["angle"] = round(rot, 1)
        print(f"[angle] {k}: slot={slot_ang:+.0f} part={part_ang or 0:+.0f} -> rotate {rot:+.1f}deg")
    elif regs.get(k):
        regs[k].pop("angle", None)

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
    gext = gb[3] if regs[SLIDER].get("vertical") else gb[2]   # groove extent along the travel axis
    seek_cov = round((tv[1] - tv[0]) / max(1e-6, gext), 3)    # travel span / groove extent (~1.0 good)
# state-align sanity — catch only GENUINELY BROKEN toggle states, not legitimate creative
# asymmetry (lever protruding at opposite/different ends between OFF/ON is a valid design
# choice, not a defect). The scale-ratio bounds catch a "wildly different scale" or a
# collapsed/near-empty "speck" state (either drives scaleX/scaleY far from 1.0); the raw
# silhouette IoU>=0.9 floor used to ALSO hard-fail any asymmetric-but-correct state (measured
# 0.58-0.79 IoU on legitimate designs) — dropped to a low floor that only catches states with
# near-zero overlap even at best alignment (effectively disjoint / broken), per user directive
# 2026-07-09 (5 of 8 fresh-regen FAILs burned rolls on the old >=0.9 floor).
sa = (regs.get(TOGGLE) or {}).get("stateAlign") if TOGGLE else None
sa_ok = bool(sa and 0.7 <= sa.get("scaleX", 0) <= 1.4 and 0.7 <= sa.get("scaleY", 0) <= 1.4 and sa.get("iou", 0) >= 0.05)
# biref parts present
biref_parts = [p for p in ["vol", "seek", TOGGLE + "_off", TOGGLE + "_on"] if TOGGLE
               and os.path.exists(os.path.join(BIREF, p + ".png"))]
need_parts = (KNOBS + ([SLIDER] if SLIDER else []) + ([TOGGLE + "_off", TOGGLE + "_on"] if TOGGLE else []))
biref_ok = all(os.path.exists(os.path.join(BIREF, p + ".png")) for p in need_parts) if os.path.exists(BIREF) else None
# region misplacement: refit landed far from the mask blob -> the model painted the display
# blob off its window; the render was rescued by the refit but the generation is visually broken
region_misplaced = []
for k in SC:
    r = regs.get(k)
    if not (r and r.get("device") and r.get("maskDevice")): continue
    if _iou(r["device"], r["maskDevice"]) < 0.5: region_misplaced.append(k)
reasons = []
knob_tmpl = [k for k in KNOBS if (regs.get(k) or {}).get("fromTemplate")]
if knob_tmpl: reasons.append("knob-template-fallback:" + ",".join(knob_tmpl))
for k in region_misplaced: reasons.append(f"region-misplaced:{k}")
if empty_fail: reasons.append("emptiness")
if missing: reasons.append("missing:" + ",".join(missing))
if seek_cov is not None and seek_cov < 0.7: reasons.append(f"seek-cov={seek_cov}")
if TOGGLE and not sa_ok and sa is not None: reasons.append("state-align")
if biref_ok is False: reasons.append("biref-parts")
leak_val = RES.get("leak")
if leak_val is not None and leak_val > 0.003: reasons.append(f"leak={leak_val}")
gate = {"empty_ok": not empty_fail, "controls": len(NAMES) - len(missing), "controls_total": len(NAMES),
        "missing": missing, "seek_cov": seek_cov, "state_align_ok": sa_ok, "biref_ok": biref_ok,
        "leak": RES.get("leak"), "reasons": reasons,
        "PASS": (not empty_fail) and (not missing) and (not knob_tmpl) and (not region_misplaced)
                and (seek_cov is None or seek_cov >= 0.7)
                and (biref_ok is not False) and (RES.get("leak", 0) is None or RES.get("leak", 0) <= 0.003)
                and (not TOGGLE or sa is None or sa_ok)}
R2 = json.load(open(os.path.join(OUT, "regions.json"))); R2["gate"] = gate
json.dump(R2, open(os.path.join(OUT, "regions.json"), "w"), indent=2)
print(f"[GATE] {'PASS' if gate['PASS'] else 'FAIL'} "
      f"controls={gate['controls']}/{gate['controls_total']} seek_cov={seek_cov} "
      f"empty={'ok' if not empty_fail else 'FAIL'} align={'ok' if sa_ok else 'x'} "
      f"reasons={reasons or 'none'}")
