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
import os, sys, json, colorsys
import numpy as np
from PIL import Image
from scipy import ndimage
from knob_angle import detect_from_sprite

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
# TOGGLE_TRACK (2026-07-12, genskin.py TOGGLE_TRACK_ENABLED): the shuffle is a TWO-DETENT
# TRACK SLIDER — ONE loose lever strip cell + a painted empty track on the device — instead
# of the legacy two-state sprite-swap (two mirror-paired strip cells + stateAlign). Read from
# results.json (genskin writes it per gen); default False so every pre-existing asset dir
# keeps its legacy extraction contract byte-identically. Downstream effects here: single
# toggle strip cell, track/detents emission (reusing the seek walk), no state-align pass,
# lever-vs-track sprite-fit bounds, `<toggle>_lever` in the biref part lists.
TOGGLE_TRACK = bool(RES.get("toggle_track_enabled", False))

m = np.asarray(Image.open(os.path.join(OUT, "mask.png")).convert("RGB")).astype(int)
MH, MW, _ = m.shape; flat = m.reshape(-1, 3)
sat = ((flat.max(1) - flat.min(1)) > 55) & (flat.max(1) > 90)
d = np.sqrt(((flat[:, None, :] - COLS[None, :, :]) ** 2).sum(2))
assign = np.where(sat & (d.min(1) < 95), d.argmin(1), -1).reshape(MH, MW)

# ---- DEVICE-BAND EXCLUSIVE BLOB->KEY REASSIGNMENT ----
# Root cause of the 2026-07-11 "button hitbox landed on a DIFFERENT control" review round
# (wmp-quicksilver: playpause->vol's knob, prev->the seek groove; myst-arcanum: repeat
# reduced to a degenerate sliver). mask.png is NOT flat key-colour fills -- genskin's guide
# render bakes shading/gradient on top of each control's key colour (measured: playpause
# (255,255,0) painted as ~(249,224,71), 78px euclidean from its OWN key). The OLD per-PIXEL
# nearest-key argmin above lets a shading-drifted pixel of one control's blob defect to a
# DIFFERENT, merely-closer-after-shading key -- two visually distinct, non-touching blobs
# (playpause's circle + vol's circle) then both label under the SAME index, and
# largest_cc_bbox coin-flips which one "wins" (confirmed: both were within 6% pixel-count of
# each other), handing playpause's device bbox to the volume knob. The same per-pixel leak
# also FRAGMENTS a single blob across two indices (myst-arcanum repeat lost its outer ring to
# neighbouring keys, leaving only a thin sliver assigned to its own index).
#
# Fix: segment the DEVICE band first (role-agnostic connected components of "any
# sufficiently saturated pixel" -- backdrop is flat/unsaturated between controls, so this
# cleanly separates distinct painted shapes regardless of their internal colour drift), THEN
# assign each WHOLE BLOB to its nearest-median-colour key via greedy EXCLUSIVE bipartite
# matching (closest blob/key pairs claimed first; a blob or key claimed once is removed from
# the pool). Immune to intra-blob gradient (uses the blob's MEDIAN colour, not per-pixel) and
# immune to cross-blob theft (one key claims exactly one blob, one blob is claimed by exactly
# one key) -- the actual invariant a "device bbox" needs. Scoped to the device band only
# (STRIP band keeps the old per-pixel path unchanged) because the strip band's TOGGLE case
# intentionally needs TWO cells to share one key -- an exclusive 1-blob-per-key match would
# break that; the button-misassignment bug is device-band only anyway (verified).
_dcut = int(DEVF * MH)
_devrows = np.zeros((MH, MW), bool); _devrows[:_dcut] = True
_sat2d = sat.reshape(MH, MW)
def _exclusive_blob_assign(mask2d):
    lbl, n = ndimage.label(mask2d)
    out = np.full((MH, MW), -1, dtype=int)
    if n == 0: return out
    blobs = []
    for c in range(1, n + 1):
        ys, xs = np.where(lbl == c)
        if len(xs) < 120: continue
        med = np.median(m[ys, xs], axis=0)
        dists = np.sqrt(((med[None, :] - COLS) ** 2).sum(1))
        bw = int(xs.max() - xs.min()) + 1; bh = int(ys.max() - ys.min()) + 1
        elong = max(bw, bh) / max(1, min(bw, bh))
        blobs.append((c, len(xs), dists, elong))
    if not blobs: return out
    # ROLE-SIZE TIE-BREAK for a genuine colour near-tie (myst-arcanum: one blob measured 69.9
    # to 'vol' and 75.2 to 'repeat' -- a 7% gap, essentially a coin flip on colour alone,
    # because the model painted this blob at a shade almost exactly between the two keys). A
    # blob's SIZE is an independent signal: buttons in one skin are drawn near-identically
    # sized by convention (confirmed: 3 other unambiguous button blobs measured
    # 97591-98522px; the disputed blob measured 98192px, matching to within 0.2%), while a
    # knob is a structurally different control and won't coincidentally match that size. Build
    # a per-ROLE median size from only UNAMBIGUOUS blobs (colour distance < 50, no ambiguity to
    # resolve) and use it as a bounded nudge -- never enough to override a clear match, only to
    # break a close one.
    role_sizes = {}
    for c, sz, dists, elong in blobs:
        order = np.argsort(dists)
        # "unambiguous" = a clear GAP to the runner-up (relative separation), not an absolute
        # distance cutoff — a heavily-shaded mask.png can push EVERY match past a fixed bar
        # (this roster: correct matches ran 60-135) while still being obviously correct
        # relative to the next-best candidate.
        if len(order) >= 2 and (dists[order[1]] - dists[order[0]]) > 40:
            role = ROLES.get(NAMES[int(order[0])])
            if role: role_sizes.setdefault(role, []).append(sz)
    # >=3 samples (not 2): a role's "typical size" must be a MEDIAN over enough same-role
    # controls to resist a single outlier — playpause is legitimately drawn larger than its
    # sibling buttons, and with only 2 samples that outlier IS the median.
    role_med = {r: float(np.median(v)) for r, v in role_sizes.items() if len(v) >= 3}
    cands = []
    for c, sz, dists, elong in blobs:
        order = np.argsort(dists)[:3]                 # keep top-3 keys/blob so greedy can fall
        for ki in order:                               # through when the #1 pick is taken
            base = float(dists[ki])
            role = ROLES.get(NAMES[int(ki)])
            if role in role_med:
                rel = abs(sz - role_med[role]) / role_med[role]
                adj = min(40.0, rel * 60.0) - 8.0        # good size match => bonus; bad => penalty
            else:
                adj = 6.0                                # no size reference for this role -> mild
                                                          # uncertainty penalty, not a free pass
            # SHAPE CONSISTENCY: a 'slider' groove or 'toggle' housing is ALWAYS an elongated
            # bar/pill by construction (this roster's real grooves measured elongation 4-9x,
            # toggle pills ~2.5x) — a near-square/circular blob (elongation ~1) can NEVER be
            # either, regardless of how close its shaded colour lands to that key. Caught TWO
            # real cross-assignments on the same skin (wmp-quicksilver): the ROUND rewind/prev
            # button (elongation 1.0) drifted to 93.1 colour-distance from 'seek', narrowly
            # beating prev's own 110.7 to its own blob; the ROUND repeat button (elongation
            # 1.0) likewise drifted closer to 'shuffle' than repeat's own key. Pure
            # colour-distance greedily handed both sprite roles a circular BUTTON blob instead
            # of their own elongated housing. A large, role-appropriate-shape penalty is a
            # hard physical prior, not a fragile tuning knob: it only fires when the shape is
            # CATEGORICALLY wrong for the role.
            if role in ("slider", "toggle") and elong < 1.8:
                adj += 80.0
            cands.append((base + adj, base, c, int(ki)))
    cands.sort(key=lambda t: t[0])
    claimed_blob, claimed_key = set(), set()
    for _score, dist, c, ki in cands:
        if dist > 170: break                        # sanity ceiling (on the RAW colour distance,
                                                       # never on the adjusted score) -- unrelated
                                                       # blob/key stays unrelated regardless of size
        if c in claimed_blob or ki in claimed_key: continue
        claimed_blob.add(c); claimed_key.add(ki)
        out[lbl == c] = ki
    return out
assign[_devrows] = _exclusive_blob_assign(_sat2d & _devrows)[_devrows]


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
    if name == TOGGLE:                               # strip cells: 1 lever (track mode) / 2 states (legacy)
        stripmask = ndimage.binary_fill_holes(stripmask)
        lbl, nc = ndimage.label(stripmask); cells = []
        for c in range(1, nc + 1):
            ys2, xs2 = np.where(lbl == c)
            if len(xs2) < 120: continue
            cells.append((xs2.min(), bb(ys2, xs2)))
        _ncell = 1 if TOGGLE_TRACK else 2
        # track mode: ONE lever cell — take the LARGEST component (not leftmost) so a stray
        # speck of the toggle's key colour elsewhere in the band can't displace the real lever
        if TOGGLE_TRACK:
            cells.sort(key=lambda t: -(t[1][2] * t[1][3]))
        else:
            cells.sort(key=lambda t: t[0])
        strip = [c[1] for c in cells[:_ncell]]
        while len(strip) < _ncell: strip.append(None)
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
# strip order: knobs, slider thumb, then toggle lever (track mode) / toggle OFF+ON (legacy)
order = list(KNOBS)
if SLIDER: order.append(SLIDER)
if TOGGLE: order += [TOGGLE + "_lever"] if TOGGLE_TRACK else [TOGGLE + "_off", TOGGLE + "_on"]
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
TOG_CELLS = 1 if TOGGLE_TRACK else 2          # toggle strip-cell count under the active contract
def _tog_idx(name):
    # track mode: the single lever cell is idx 0; legacy: OFF=0, ON=1
    if TOGGLE_TRACK: return 0
    return 0 if name.endswith("_off") else 1
claimed = []
for name in order:
    if TOGGLE and name.startswith(TOGGLE):
        idx = _tog_idx(name)
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
        regs[TOGGLE] = regs.get(TOGGLE) or {"device": None, "strip": [None] * TOG_CELLS}
        idx = _tog_idx(name)
        while len(regs[TOGGLE]["strip"]) < TOG_CELLS: regs[TOGGLE]["strip"].append(None)
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
    # MAGNITUDE CAP (buttons only): on a weathered/textured body (rust patina, gold trim) the
    # "vivid" pixel test (mx-mn>60) can find a genuinely colourful DECORATIVE patch beside the
    # button rather than the button's own icon -- fallout-vault: prev/repeat's engraved icon is
    # low-saturation grey metal, but a rust/gold trim strip sits just to their left and IS
    # colourful, so the un-bounded recentre dragged both boxes a full button-width onto that
    # trim (confirmed: the raw, un-snapped mask position was already dead-on; snapping made it
    # worse). A small icon-content nudge is legitimate; a big jump onto neighbouring material is
    # not -- cap the shift to a modest fraction of the button's own size, consistent with the
    # bounded-search-window pattern used elsewhere in this file (rrect-fit +-30%, seek clamp
    # +-12%).
    if name in HB:
        cap = b[2] * 0.20
        ncx = max(cx - cap, min(cx + cap, ncx))
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
#
# The actual radial-anomaly math lives in knob_angle.py (shared with the knob-zero closed-loop
# render verifier — one implementation, not a reimplementation per skin per call-site; see that
# module's docstring for the 2026-07-11 root-cause writeup of the bin-edge/no-sub-bin bug this
# replaced). This is a thin wrapper: alpha-bbox-center + parabolic sub-bin refinement, matching
# EXACTLY the origin build_player.py's tight()+background-size:cover renders around.
def detect_knob_zero_deg(cap_path):
    angle, info, geo = detect_from_sprite(cap_path)
    return angle, info, geo


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
    zdeg, zinfo, zgeo = detect_knob_zero_deg(os.path.join(BIREF, f"{k}.png"))
    r["knob_zero_deg"] = zdeg
    # store the detector's OWN measured (cx,cy,R) in the cut sprite's pixel frame — so any later
    # proof/overlay page draws FROM this stored geometry instead of re-deriving it independently
    # (the exact §7 proxy-trap the old knobzero-proof/annotate.py committed; verify-outputs-rule).
    r["knob_zero_geo"] = None if zgeo is None else [round(zgeo[0], 2), round(zgeo[1], 2), round(zgeo[2], 2)]
    print(f"[knob-zero] {k}: {zdeg if zdeg is None else round(zdeg, 1)}  ({zinfo})")
if drift_samples:
    gdx = float(np.median([d[0] for d in drift_samples])) / GW
    gdy = float(np.median([d[1] for d in drift_samples])) / GH
    print(f"[global drift] mask->paint = ({gdx * 100:+.2f}%, {gdy * 100:+.2f}%)")
    # BUTTONS (HB) are DELIBERATELY EXCLUDED here. This drift is measured from KNOB circle-fit
    # (gradient-fit centre) vs each knob's own mask-blob centre -- a correction for how ROUND
    # dials render (matte-hole vs guide-circle offset), not a proven whole-canvas rigid
    # translation. Applying it to buttons overwrote their own already-computed `device`
    # (mask-assign + the paint-aware X-snap above) with `maskDevice + gdx,gdy` -- discarding a
    # per-button local signal in favour of an unrelated knob-derived shift. Root-caused
    # 2026-07-11: fallout-vault's prev/repeat measured a UNIFORM -64px (=gdx) shift on EVERY
    # button, while the RAW pre-snap mask position was already dead-on the painted icon (visual
    # crop confirmed) -- the blind overwrite is what introduced the "shifted a full
    # button-width left" defect. SLIDER/TOGGLE/SC are NOT excluded: each gets its own further
    # gradient-fit / region-refit pass right after this (rrect_fit, region_refit) that
    # self-corrects a modest starting drift via local search -- buttons get no such downstream
    # refinement, so a wrong drift here is final and uncorrectable.
    for k in ([SLIDER] if SLIDER else []) + ([TOGGLE] if TOGGLE else []) + list(SC):
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

# ---- ART/VIZ SWAP-RELABEL (album_art <-> visualizer identity swap) ----
# The two display windows are functionally interchangeable glass (same round-trip through
# region_refit above); when the model paints them in the OPPOSITE vertical order the
# template declared (e.g. viz above art instead of art above viz), the render places album-
# art content in the visualizer's painted window and vice versa -- what LOOKS like a huge
# template-drift regression (fallout-pipboy seed 951: album_art measured 1807.8px drift,
# visualizer 413.8px) is actually a clean identity swap, not a placement failure. Relabeling
# (swap which NAME the two already-detected regions are filed under) makes the render match
# the paint and the "drift" collapses -- no re-generation needed.
# Guard: only swap when BOTH detected windows are closer to the OTHER's template slot than
# their own (mutual-nearest) -- a genuine single-window drift (one detector off, the other
# fine) is left alone for the drift gate to catch, never silently relabeled.
art_viz_swapped = False
if TEMPLATED and "album_art" in template and "visualizer" in template:
    ra = regs.get("album_art"); rv = regs.get("visualizer")
    if ra and rv and ra.get("device") and rv.get("device"):
        da = ra["device"]; dv = rv["device"]
        ca = (da[0] + da[2] / 2, da[1] + da[3] / 2)
        cv = (dv[0] + dv[2] / 2, dv[1] + dv[3] / 2)
        ta = tuple(template["album_art"]); tv = tuple(template["visualizer"])
        def _d(p, q): return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5
        order_inverted = (ca[1] - cv[1]) * (ta[1] - tv[1]) < 0   # opposite sign = vertical order flipped
        mutual_nearest = _d(ca, tv) < _d(ca, ta) and _d(cv, ta) < _d(cv, tv)
        if order_inverted and mutual_nearest:
            regs["album_art"], regs["visualizer"] = rv, ra
            art_viz_swapped = True
            print(f"[art-viz-swap] album_art<->visualizer identities SWAPPED (detected vertical "
                  f"order inverted vs template; mutual-nearest confirmed: album_art was "
                  f"{_d(ca, ta):.3f} from its own template slot, {_d(ca, tv):.3f} from viz's)")
        elif order_inverted:
            print(f"[art-viz-swap] vertical order looks inverted but mutual-nearest guard failed "
                  f"(not a clean swap) -- left as-is for the drift gate")

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
baked_thumb_flagged = []       # BAKED-THUMB-IN-GROOVE gate hits, filled below
sprite_fit_flagged = []        # SPRITE-VS-SLOT FIT gate hits, filled below
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
            fl = med[sl]; cd = cdist[sl]
            # DISTANCE FROM BACKDROP COLOUR, not "brighter than backdrop": the old
            # `fl > bgd+25` inequality silently assumed the device body is BRIGHTER than the
            # (near-white) canvas backdrop — true for a metallic/bright skin but WRONG-SIGNED
            # for a dark-bodied skin on the same light backdrop. ps1-crunchy: chassis ~40-100
            # vs backdrop 235 → `fl>bgd+25` never once passes, both flank windows return None,
            # and the coarse whole-row 85th-percentile fallback then blends groove+body+
            # backdrop into one number that's too PERMISSIVE — the walk rode 44px past the
            # slot's own declared mask cell onto the surrounding chassis plate before stopping
            # (confirmed: raw mask cell edge was already correct, the WALK overshot it).
            # `cdist` (already computed for this window) is the material-agnostic version:
            # exclude pixels near backdrop colour in EITHER brightness direction, keep the rest
            # as body candidates — works for bright-body-on-dark-backdrop and
            # dark-body-on-light-backdrop alike.
            fl = fl[(cd > 30) & (fl > Dfloor + 15)]
            # 70th percentile, NOT median: the flank is often BIMODAL (a neighbour control's
            # shadow next to the raised body plate — quicksilver: knob shadow ~94 / plate ~196).
            # A median lands between the modes, the plate then reads as "bright bezel rim" and
            # the walk rides it ~58px off the slot. The plateau is the RAISED level → p70.
            return float(np.percentile(fl, 70)) if len(fl) >= 8 else None
        bodyL = _body(np.s_[max(0, mx0 - 4 - fw):max(0, mx0 - 4)])
        bodyR = _body(np.s_[mx1 + 4:mx1 + 4 + fw])
        # LOCAL fallback when the immediate flank has too few valid samples (low local
        # contrast between this slot's body and floor): widen progressively (2x, 3x, 5x fw)
        # before resorting to the whole search window. The whole-row `med` can reach deep into
        # a NEIGHBOURING control (wmp-vario: the volume knob's own glowing rim sat within the
        # 40%-padded search window; its brightness dominated a whole-row percentile, inflating
        # the body reference to 197.5 -- far above this slot's own ~85 immediate material -- so
        # `below` never dropped low enough and the walk rode the flat low-contrast body clear
        # through to the knob's edge, 88px past the model's own declared slot cell). A
        # progressively-widened but still LOCAL window keeps the reference honest to nearby
        # material instead of jumping straight to "anything in the whole search box."
        def _local_glob(edge, direction):
            for mult in (2, 3, 5):
                w = fw * mult
                sl = np.s_[max(0, edge - w):edge] if direction < 0 else np.s_[edge:edge + w]
                v = _body(sl)
                if v is not None: return v
            return None
        if bodyL is None: bodyL = _local_glob(mx0 - 4, -1)
        if bodyR is None: bodyR = _local_glob(mx1 + 4, +1)
        glob = _body(np.s_[:]) or float(np.percentile(med, 85))
        bodyL = bodyL if bodyL is not None else glob; bodyR = bodyR if bodyR is not None else glob
        rimcap = max(8, int(cw * 0.03))                        # TOTAL bright budget per walk — a real
        # bezel end-cap is THIN; 6% of a 950px cell (57px) let a mis-read body plate extend travel
        stopcap = max(6, int(cw * 0.02))                       # sustained near-body = past the slot
        def _walk(edge, step, body):
            below = body - max(18.0, 0.35 * max(0.0, body - Dfloor))   # "clearly below body" —
            # wider margin than a flat body-to-floor split alone: a curved wall/bevel fillet
            # right at the slot's TRUE edge has its own shading gradient (a highlight-then-
            # shadow "bump"), which a narrow margin misreads as still-recessed and rides
            # straight through onto the material beyond (steam-porthole: the bevel's smoothed
            # brightness bounced 62-136 across a ~100px transition, repeatedly dipping back
            # under a too-close `below` and resetting progress). A wider margin keeps genuine
            # deep recess (near Dfloor) classified correctly while excluding more of that
            # transitional bounce as "already past the slot."
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
        # SATURATED-WALK DISTRUST (per side): a real end-cap completion stops on its own — a
        # bezel rim, a body plateau, or the backdrop. A walk that rides all the way PAST the
        # ±12% clamp never found ANY stop signal (wmp-vario: a wide decorative outer trough
        # around the true channel is uniformly low-contrast "recessed", so both walks ran to
        # the clamp and shipped the full 88px-per-side overshoot — the reviewed "css slider
        # bar too far left. too far right also" defect). A measurement that saturates its own
        # sanity bound is not a measurement; that side falls back to the model's own declared
        # slot-cell edge (the walk's base span by design). Sides that stop WITHIN the clamp
        # (fallout-vault's genuine stepped-recess widening, thin bezel caps) keep their walked
        # extent unchanged.
        loClamp = bx0 + mx0 - int(0.12 * cw); hiClamp = bx0 + mx1 + int(0.12 * cw)
        if lo <= loClamp: lo = bx0 + mx0
        if hi >= hiClamp: hi = bx0 + mx1
        lo = max(lo, loClamp); hi = min(hi, hiClamp)
        # travel == the walked/device span EXACTLY, no added margin (2026-07-12 fix for the
        # recurring cross-roster "CSS slider outside slot" review complaint -- claymation,
        # diablo-gothic, fallout-vault, n64-cutscene, ps1-crunchy, reported since round1 2026-07-11
        # and STILL present in round3, i.e. it predates and survives the seek-track/fill CSS
        # overlay, so it was never that overlay alone). ROOT CAUSE: this used to add a further
        # +/-2%-of-span `M` pad on top of `lo..hi` (which is *already* the outward-walked, "err
        # wide" coverage span vs the model's own mask cell -- see the SEEK GROOVE EXTENT docstring
        # above). That's TWO independent widenings stacked: the walk expands mx0/mx1 -> lo/hi
        # (up to 12% of the mask-cell width per side, by design), then M expanded lo/hi again. A
        # real-runtime measurement (Playwright getBoundingClientRect vs the true visual groove
        # edge in the rendered player, fallout-vault seek at val=1) showed the thumb's rendered
        # right edge landing ~11px (2.4% of the 460px-wide player) past the true visual channel
        # edge -- with `device` (lo/hi, no pad) alone already ~6.5px (1.4%) past it and the M pad
        # adding the other ~4.5px on top. Dropping M removes that second, purely-additive layer
        # cleanly and uniformly for every skin/material (M was never material-aware, always +2%
        # of span) with no coverage-safety loss: `device` itself is already the outward "err wide"
        # walked estimate, so travel == device keeps the coverage-span behaviour intact --  it
        # just stops padding an already-padded number. See docs/experiments/2026-07-12-seek-
        # travel-overshoot.md for the measured before/after across the flagged roster.
        tvv = [round(lo / _W, 5), round(hi / _W, 5)]
        if VERT:
            r["device"] = [b[0], lo / _W, b[2], (hi - lo) / _W]   # expand device to the painted groove (Y)
            r["travel"] = tvv; r["vertical"] = True
        else:
            r["device"] = [lo / _W, b[1], (hi - lo) / _W, b[3]]   # expand device to the painted groove (X)
            r["travel"] = tvv; r.pop("vertical", None)
        print(f"[travel] {SLIDER} {'VERTICAL ' if VERT else ''}groove {lo}..{hi}px "
              f"(fit bbox {gx0}..{gx1}, mask cell {bx0 + mx0}..{bx0 + mx1}, "
              f"body L{bodyL:.0f}/R{bodyR:.0f} floor {Dfloor:.0f}) -> travel {r['travel']}")

        # ---- BAKED-THUMB-IN-GROOVE GATE ----
        # The #1 recurring human-review complaint (2026-07-11 round1, 6/15 skins): the model
        # bakes a thumb/knob graphic INTO the groove painting itself, on top of the empty
        # channel the player later composites its OWN cut thumb sprite onto -- the shipped
        # render then shows two thumbs (a painted one + the CSS-positioned cut one). The
        # existing EMPTINESS gate below can't see this: it shrinks the SLIDER's device bbox by
        # 18% per side, and worse, the travel-WALK above never visits the region BETWEEN mx0
        # and mx1 (the model's own declared slot cell) by design ("baked-handle-proof for
        # free" -- see the SEEK GROOVE EXTENT docstring) -- so a thumb sitting inside that
        # interior sails through both existing checks untouched.
        #
        # Material-agnostic: score every column of the SAME `med` profile already computed
        # for the travel walk against bodyL/bodyR -- the RAISED, OUTSIDE-the-groove material
        # level, an independent reference (not derived from the window being scored) -- rather
        # than an absolute brightness constant. A baked thumb is a raised/lit 3D shape, so it
        # reads close to or above body level; an empty recessed channel reads near Dfloor.
        # score 0 = at the channel floor, 1 = at body level.
        #   run_frac lower bound (0.05) -- excludes single-pixel/rim noise (myst-arcanum 0.024)
        #   AND steam-porthole's bright mid-ledge specular (0.046, a stepped-recess artifact the
        #   human did NOT name as a baked thumb); true positives measure 0.080+ (fallout-vault
        #   0.080, fallout-pipboy 0.119, claymation 0.147, n64-cutscene ~0.11).
        #   run_frac upper bound (0.28) -- excludes a smooth material gradient or ambient-glow
        #   band spanning nearly the WHOLE channel (not a discrete blob): wmp-vario's glow
        #   measured 0.440 clean, wmp-quicksilver 0.286 clean. KNOWN MISS, accepted: diablo-
        #   gothic's genuinely-baked vertical thumb measures 0.516 (the baked shield-handle
        #   spans half the groove) -- indistinguishable from vario's glow by run-length alone;
        #   that skin still FAILs overall via sprite-fit:shuffle (see gate below).
        #   peak >= 1.17 -- the run must actually REACH body-level brightness (a real baked
        #   thumb catches highlights >= its surrounding material); a merely-lighter patch of
        #   channel floor (fa-sky 1.07, fa-pod 1.06, ps1-wild 0.58) stays under this.
        # Calibrated 2026-07-11 against the full 15-skin roster's LIVE extraction (not stored
        # regions) incl. the 6 human-named cases (claymation, diablo-gothic, fallout-pipboy,
        # fallout-vault, n64-cutscene, wc-goldshield); catches 4/6 -- diablo (above) and
        # wc-goldshield (its baked handle sits at the groove END CAP, outside the walked travel
        # span, run_frac 0.000) are honest misses, both independently failed by sprite-fit.
        # Full number table: docs/experiments/2026-07-11-gate-recalibration.md.
        bodyRef = min(bodyL, bodyR)
        lo_i = max(0, lo - bx0); hi_i = min(len(med), hi - bx0)
        seg = med[lo_i:hi_i]; Lseg = len(seg)
        if Lseg >= 10:
            bscore = (seg - Dfloor) / max(1.0, bodyRef - Dfloor)
            mgn = max(2, int(Lseg * 0.03))
            above = bscore > 0.40
            above[:mgn] = False; above[Lseg - mgn:] = False
            close_n = max(2, int(Lseg * 0.02))
            above_c = ndimage.binary_closing(above, structure=np.ones(close_n * 2 + 1, bool))
            _lbl, _n = ndimage.label(above_c)
            best_len, best_c = 0, None
            for _c in range(1, _n + 1):
                _ln = int((_lbl == _c).sum())
                if _ln > best_len: best_len, best_c = _ln, _c
            run_frac = best_len / Lseg
            peak = float(bscore[_lbl == best_c].max()) if best_c else float(bscore.max())
            baked = 0.05 <= run_frac <= 0.28 and peak >= 1.17
            r["bakedThumb"] = {"runFrac": round(run_frac, 3), "peak": round(peak, 2), "flag": baked}
            print(f"[baked-thumb] {SLIDER}: run_frac={run_frac:.3f} peak={peak:.2f} "
                  f"{'FAIL - baked thumb in groove' if baked else 'ok'}")
            if baked: baked_thumb_flagged.append(SLIDER)

# ---- SHUFFLE TRACK + DETENTS (TOGGLE_TRACK contract, 2026-07-12) ----
# The shuffle is a two-detent slider: a painted empty track/housing whose single loose lever
# rides between two end positions. Detect the TRACK the same way the seek groove above is
# detected — the model's own mask cell is the base span, then a level-aware walk completes
# the visual end caps (same _body/backdrop-distance/recess-continuity/rim-budget logic,
# compacted for a SHORT track; constants proportionally looser because a track is a fraction
# of the seek groove's length and its detents get inset anyway). Emits regions[toggle]:
#   track    [x,y,w,h]  the walked visual track extent (device is also expanded to it,
#                        mirroring the seek convention "expand device to the painted groove")
#   detents  [p0,p1]    lever CENTRE positions along the travel axis (normalized, full-image
#                        coords), inset 18% of the track extent per side
#   vertical bool       portrait track => vertical slide
# Collapse guard + per-side clamp-saturation fallback mirror the seek walk's (a walk that
# saturates its own clamp found no stop signal → trust the model's declared cell edge).
if TOGGLE_TRACK and TOGGLE:
    r = regs.get(TOGGLE)
    if r and r.get("device"):
        b = r["device"]; mb = r.get("maskDevice") or b
        TVERT = (b[3] * GH) > (b[2] * GW) * 1.3
        if TVERT:
            _tprgb = np.ascontiguousarray(paintrgb.transpose(1, 0, 2)); _tW, _tH = GH, GW
            _tb = [b[1], b[0], b[3], b[2]]; _tmb = [mb[1], mb[0], mb[3], mb[2]]
        else:
            _tprgb = paintrgb; _tW, _tH = GW, GH; _tb = b; _tmb = mb
        tcy = (_tb[1] + _tb[3] / 2) * _tH; thh = max(4, int(_tb[3] * _tH * 0.30))
        tby0 = int(tcy - thh); tby1 = int(tcy + thh)
        tux0 = min(_tb[0], _tmb[0]); tux1 = max(_tb[0] + _tb[2], _tmb[0] + _tmb[2])
        tpad = int((tux1 - tux0) * _tW * 0.30)
        tbx0 = max(0, int(tux0 * _tW) - tpad); tbx1 = min(_tW, int(tux1 * _tW) + tpad)
        tmed = np.median(_tprgb[tby0:tby1, tbx0:tbx1].max(2), 0)
        tmed = np.convolve(tmed, np.ones(5) / 5, mode="same")
        tcd = np.median(np.abs(_tprgb[tby0:tby1, tbx0:tbx1] - BGC).max(2), 0)
        tgx0, tgx1 = int(_tb[0] * _tW), int((_tb[0] + _tb[2]) * _tW)
        tmx0 = max(0, int(_tmb[0] * _tW) - tbx0); tmx1 = min(len(tmed), int((_tmb[0] + _tmb[2]) * _tW) - tbx0)
        if tmx1 <= tmx0: tmx0, tmx1 = max(0, tgx0 - tbx0), min(len(tmed), tgx1 - tbx0)
        tcw = max(1, tmx1 - tmx0)
        tDfloor = float(np.percentile(tmed[tmx0:tmx1], 10))
        tfw = max(20, int(tcw * 0.25))
        def _tbody(sl):
            fl = tmed[sl]; cd = tcd[sl]
            fl = fl[(cd > 30) & (fl > tDfloor + 15)]           # backdrop-distance, direction-agnostic
            return float(np.percentile(fl, 70)) if len(fl) >= 6 else None
        _tglob = _tbody(np.s_[:]) or float(np.percentile(tmed, 85))
        tbodyL = _tbody(np.s_[max(0, tmx0 - 4 - tfw):max(0, tmx0 - 4)]) or _tglob
        tbodyR = _tbody(np.s_[tmx1 + 4:tmx1 + 4 + tfw]) or _tglob
        trimcap = max(4, int(tcw * 0.05)); tstopcap = max(3, int(tcw * 0.04))
        def _twalk(edge, step, body):
            below = body - max(18.0, 0.35 * max(0.0, body - tDfloor)); rimhi = body + 20.0
            x = edge + step; last = edge; nrun = 0; rrun = 0
            while 0 <= x < len(tmed):
                if tcd[x] < 30: break                          # backdrop colour → stop hard
                if tmed[x] < below:
                    if rrun > 0 or nrun > 2: break             # recess continuity (see seek walk)
                    last = x; nrun = 0
                elif tmed[x] > rimhi:
                    last = x; rrun += 1; nrun = 0
                    if rrun > trimcap: break                   # bright end-cap budget spent
                else:
                    nrun += 1
                    if nrun > tstopcap: break                  # sustained body = past the track
                x += step
            return last
        tlo = tbx0 + _twalk(tmx0, -1, tbodyL); thi = tbx0 + _twalk(tmx1 - 1, +1, tbodyR)
        if thi - tlo < 0.5 * tcw: tlo, thi = tbx0 + tmx0, tbx0 + tmx1   # collapse → mask cell
        tloClamp = tbx0 + tmx0 - int(0.15 * tcw); thiClamp = tbx0 + tmx1 + int(0.15 * tcw)
        if tlo <= tloClamp: tlo = tbx0 + tmx0                  # clamp-saturated side → cell edge
        if thi >= thiClamp: thi = tbx0 + tmx1
        tlo = max(tlo, tloClamp); thi = min(thi, thiClamp)
        text = (thi - tlo) / _tW
        tinset = 0.18 * text
        r["detents"] = [round(tlo / _tW + tinset, 5), round(thi / _tW - tinset, 5)]
        if TVERT:
            r["track"] = [b[0], tlo / _tW, b[2], round(text, 5)]
            r["vertical"] = True
        else:
            r["track"] = [tlo / _tW, b[1], round(text, 5), b[3]]
            r.pop("vertical", None)
        r["device"] = r["track"]                               # seek convention: device = walked span
        print(f"[track] {TOGGLE} {'VERTICAL ' if TVERT else ''}track {tlo}..{thi}px "
              f"(mask cell {tbx0 + tmx0}..{tbx0 + tmx1}, body L{tbodyL:.0f}/R{tbodyR:.0f} "
              f"floor {tDfloor:.0f}) -> detents {r['detents']}")

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

# ---- ORIENTATION GATE (orientation:device) ----
# n64-prerender-character shipped a visibly mis-oriented device ("what the fuck is this
# orientation?"). Investigated 2026-07-11: that specific skin's device-body silhouette PCA
# angle measures 86.5deg (3.5deg off vertical) -- NOT tilted; its "orientation" complaint
# traces to a control-substitution defect (a toggle sprite rendered into the "next" button's
# slot) that the missing/state-align/emptiness/guide-ring gates ALREADY catch, not a whole-
# body rotation. So this gate does NOT reproduce that specific human catch -- said plainly,
# per verify-outputs-rule, rather than forcing a metric to fit.
#
# It DOES catch a genuine, different orientation failure mode found while investigating:
# ps1-wild ("absulute falire") is painted in a rotated 3/4 side-profile (vehicle-style) view
# instead of the expected top-down frontal layout -- its device silhouette measures 43.1deg
# off vertical, a real geometric outlier (next-worst in the roster is claymation at 11.7deg,
# a >3x margin). Deterministic signal: PCA major-axis angle of the device-region foreground
# silhouette (paint pixels far from the backdrop colour, y < devFrac) vs vertical, gated on
# elongation >= 1.15 (a near-square/round device has no meaningful axis -- same guard as the
# TOGGLE slot-angle code above). THRESH_DEG=30 sits comfortably between the roster's healthy
# ceiling (11.7deg) and the one confirmed defect (43.1deg) -- calibrated 2026-07-11.
# Explicitly scoped: this is a coarse "is the whole device tilted/sideways" safety net, not a
# semantic "does the control layout make sense" check -- that needs a VLM
# (verification-recalibration agent), not a deterministic geometry gate.
ORIENT_THRESH_DEG = 30.0
orientation_flagged = False
_pH, _pW = paintrgb.shape[:2]
_devfg = (np.abs(paintrgb - BGC).max(2) > 40)[: int(DEVF * _pH)]
_orient_r = _pca_angle(_devfg)
if _orient_r is not None:
    _oang, _oel = _orient_r
    _odev = 90.0 - abs(_oang) if abs(_oang) <= 90 else abs(_oang) - 90.0
    if _oel >= 1.15 and _odev > ORIENT_THRESH_DEG:
        orientation_flagged = True
    print(f"[orientation] device silhouette angle={_oang:+.1f}deg elong={_oel:.2f} "
          f"off-vertical={_odev:.1f}deg (thresh {ORIENT_THRESH_DEG:.0f}deg) "
          f"{'FAIL - device mis-oriented' if orientation_flagged else 'ok'}")
else:
    print("[orientation] device silhouette too sparse to measure -- skipped")

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
# Legacy two-state contract only: the TOGGLE_TRACK contract has ONE lever cut (no ON/OFF
# state pair to register), and the _off/_on cuts don't exist in its biref dir anyway.
def _alpha(path):
    if not os.path.exists(path): return None
    return np.asarray(Image.open(path).convert("RGBA"))[:, :, 3] > 30
if TOGGLE and not TOGGLE_TRACK:
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
           "roles": ROLES, "templated": TEMPLATED, "toggle_track": TOGGLE_TRACK,
           "keys": {k: list(v) for k, v in KEYS.items()}, "keyNames": RES.get("keyNames", {}),
           "regions": regs, "template": template, "art_viz_swapped": art_viz_swapped},
          open(os.path.join(OUT, "regions.json"), "w"), indent=2)

# overlay
p = Image.open(os.path.join(OUT, "paint.png")).convert("RGB")
mm = Image.open(os.path.join(OUT, "mask.png")).convert("RGB").resize(p.size)
pa = np.asarray(p).astype(float); ma = np.asarray(mm).astype(float); nb = (ma.max(2) > 45)[..., None]
Image.fromarray((pa * (1 - 0.5 * nb) + ma * (0.5 * nb)).astype("uint8")).save(os.path.join(OUT, "overlay.png"))

# ---- GUIDE-RING GATE ----
# Perimeter-band guide-hue residue scan (ported from twoimg/score_twoimg.py's bleed_ring_pct,
# the experiment that found the leak gate under-counts residue -- it only samples a narrow
# interior window and misses a thin coloured RING/bezel that's visible at full-res and is
# exactly the "ZERO RESIDUE" defect the genskin prompt bans). Promoted to mainline gen12 after
# director_review.py caught it as a real, actionable defect on diablo-gothic (every control
# wearing a neon ring in its OWN guide-key hue -- see docs/experiments and TODO.md).
#
# False-positive guard (2026-07-11 calibration against the full roster): an earlier cut
# compared the ring band's saturation to the control's own INTERIOR (e.g. a flat dark screen)
# -- that's a useless baseline for anything whose interior is legitimately near-black/flat, and
# it false-flagged steam-porthole's brass visualizer bezel + myst-arcanum's brass album_art
# frame (both have a yellow guide key, and brass is hue-adjacent to yellow -- the exact
# "gold body vs YELLOW key" trap this gate must not fall into). Fixed by comparing instead to
# a CONTEXT ring further out (the surrounding chassis material, away from the control) --
# genuine neon residue reads as a hue OUTLIER against its own neighbourhood; a body's own
# material (brass bezel, gold frame) does not. Combined with an angular ARC-COHERENCE
# requirement (hit pixels must wrap a real arc around the control, not cluster in one
# reflection/highlight) to reject specular false positives. Validated: diablo-gothic flags
# 8/10 controls (its two misses read as neighbour-key bleed, not own-key -- future work, not
# blocking); 9 other roster skins incl. both the brass/yellow-key traps above PASS clean.
# PALETTE GUARD (both this scan and the sprite scan below): a hit pixel whose hue sits within
# tolerance of one of the THEME'S OWN declared palette colours (results.json "palette", the
# director-authored material colours) is THEMATIC, not residue -- claymation's terracotta vol
# knob (h16 = clay_orange h16) and teal repeat button (h122 = clay_teal h122) are the theme's
# clay, and ps1-wild's magenta/toxic-green outlines ARE its declared palette; flagging those
# burned re-rolls on correct art (2026-07-11 adjudication: crops + palette cross-check).
# Only saturated palette entries participate (sat>=60): grey/silver palette hues are
# meaningless as hue anchors. Known blind spot, accepted: genuine residue in a hue the palette
# ALSO declares is masked -- tolerable because genskin's pickKeyColor already biases guide keys
# AWAY from the palette, so key-echo residue rarely lands on a palette hue.
PAL_TOL = 16
_pal_hues = []
for _pv in (RES.get("palette") or {}).values():
    _ph, _ps, _ = colorsys.rgb_to_hsv(*[v / 255 for v in _pv])
    if _ps * 255 >= 60: _pal_hues.append(int(_ph * 255))


def palette_mask(hsv):
    """Bool mask of pixels whose hue is within PAL_TOL of any saturated theme-palette colour."""
    m2 = np.zeros(hsv.shape[:2], dtype=bool)
    for _h in _pal_hues:
        hd = np.minimum(np.abs(hsv[..., 0].astype(int) - _h), 255 - np.abs(hsv[..., 0].astype(int) - _h))
        m2 |= hd < PAL_TOL
    return m2


RING_BAND_FRAC = 0.14      # inner band width (perimeter zone directly touching the control), frac of bbox size
RING_CTX_FRAC = 0.40       # outer context zone (surrounding chassis material), frac of bbox size
RING_HUE_TOL = 16          # degrees (0-255 space) hue tolerance vs the control's OWN guide key
RING_SAT_FLOOR, RING_VAL_FLOOR = 60, 70
RING_CTX_HUE_MARGIN = 20   # hit pixels must ALSO differ from the surrounding context hue by this much
RING_ARC_BINS = 24
RING_ARC_COHERENCE = 0.30  # fraction of angular bins around the control that must contain a hit
RING_PCT_THRESH = 2.0      # band coverage % (of the guarded hit) to flag


def guide_ring_scan(paint_rgb, bbox, key_rgb, W, H):
    """Returns (pct, arc_coherence) of the perimeter band around bbox whose hue matches
    key_rgb AND stands out from the surrounding context material (see guard note above).
    bbox is fractional [x,y,w,h] of the full paint canvas (extract12's device convention)."""
    x, y, w, h = bbox
    mx1, my1 = w * RING_BAND_FRAC, h * RING_BAND_FRAC
    mx2, my2 = w * RING_CTX_FRAC, h * RING_CTX_FRAC
    ox0, oy0 = max(0.0, x - mx2), max(0.0, y - my2)
    ox1, oy1 = min(1.0, x + w + mx2), min(1.0, y + h + my2)
    X0, Y0, X1, Y1 = int(ox0 * W), int(oy0 * H), int(ox1 * W), int(oy1 * H)
    if X1 <= X0 or Y1 <= Y0: return 0.0, 0.0
    hsv = np.asarray(Image.fromarray(paint_rgb[Y0:Y1, X0:X1]).convert("HSV")).astype(int)

    def rectmask(mxx, myy):
        ix0 = int((x - mxx - ox0) * W); iy0 = int((y - myy - oy0) * H)
        ix1 = int((x + w + mxx - ox0) * W); iy1 = int((y + h + myy - oy0) * H)
        mm2 = np.zeros(hsv.shape[:2], dtype=bool)
        mm2[max(0, iy0):max(0, iy1), max(0, ix0):max(0, ix1)] = True
        return mm2
    interior = rectmask(0, 0)
    outer1 = rectmask(mx1, my1)
    outer2 = rectmask(mx2, my2)
    band = outer1 & ~interior          # candidate ring zone, hugging the control
    ctx = outer2 & ~outer1             # surrounding-chassis reference zone, further out
    if band.sum() < 40: return 0.0, 0.0
    kh = int(colorsys.rgb_to_hsv(*[v / 255 for v in key_rgb])[0] * 255)
    hd_key = np.minimum(np.abs(hsv[..., 0].astype(int) - kh), 255 - np.abs(hsv[..., 0].astype(int) - kh))
    ctx_pool = ctx if ctx.sum() > 20 else interior
    ctx_h = float(np.median(hsv[..., 0][ctx_pool])) if ctx_pool.sum() else float(kh)
    hd_ctx = np.minimum(np.abs(hsv[..., 0].astype(int) - int(ctx_h)), 255 - np.abs(hsv[..., 0].astype(int) - int(ctx_h)))
    hit = (band & (hd_key < RING_HUE_TOL) & (hsv[..., 1] > RING_SAT_FLOOR) & (hsv[..., 2] > RING_VAL_FLOOR)
           & (hd_ctx > RING_CTX_HUE_MARGIN) & ~palette_mask(hsv))
    n_band = int(band.sum())
    pct = 100.0 * int(hit.sum()) / n_band if n_band else 0.0
    coh = 0.0
    if hit.sum() >= 8:
        ix0 = int((x - ox0) * W); iy0 = int((y - oy0) * H)
        ix1 = int((x + w - ox0) * W); iy1 = int((y + h - oy0) * H)
        cy_l, cx_l = (iy0 + iy1) / 2.0, (ix0 + ix1) / 2.0
        hy, hx = np.where(hit)
        ang = (np.degrees(np.arctan2(hy - cy_l, hx - cx_l)) % 360.0)
        bins = (ang / (360.0 / RING_ARC_BINS)).astype(int) % RING_ARC_BINS
        coh = len(set(bins.tolist())) / RING_ARC_BINS
    return pct, coh


paint_rgb_full = np.asarray(p)
PW3, PH3 = p.size
print("guide-ring gate (perimeter-band guide-hue residue around each control):")
ring_flagged = []
for k in NAMES:
    r = regs.get(k)
    if not r or not r.get("device"): continue
    rpct, rcoh = guide_ring_scan(paint_rgb_full, r["device"], KEYS[k], PW3, PH3)
    r["guideRingPct"] = round(rpct, 3)
    flag = rpct > RING_PCT_THRESH and rcoh >= RING_ARC_COHERENCE
    if flag: ring_flagged.append(k)
    print(f"  {k:12} ring={rpct:6.2f}% coh={rcoh:.2f}  {'FAIL - guide-ring residue' if flag else 'ok'}")
print(f"[guide-ring gate] {'FAIL - regenerate: ' + ','.join(ring_flagged) if ring_flagged else 'ok'}")

# ---- SPRITE GUIDE-HUE CONTAMINATION (same family as the device ring gate above, applied to
# the biref-cut moving PARTS instead of the paint-canvas socket perimeter). Only meaningful on
# pass 2, once BIREF has cut vol/seek/shuffle_off/shuffle_on -- guarded on BIREF existing. A
# sprite whose OWN visible pixels are dominated by ITS OWN guide-key hue means the model's paint
# for that PART echoed the internal guide colour (found empirically: wmp-vario's seek thumb
# painted salmon-pink against guide key (255,0,128), confirmed genuine paint-side residue by
# inspecting joint-4k.png's staged part swatch directly -- not a biref/cut artefact). Distinct
# shape from the device ring (full-fill vs thin border) so it needs its OWN scan, not a bbox-band
# reuse; folded into the SAME gate reason family ("guide-ring:<part>") since it's the same root
# defect (guide-hue leaking into the render) and the fix is the same (re-roll).
SPRITE_CONTAM_THRESH = 40.0  # % of a part's visible pixels matching its own key -- calibrated
                              # against the roster: genuine leaks measured 59-100%, clean/
                              # ambiguous parts measured 0-19% (2026-07-11 sweep)
SPRITE_PARTS = {"vol": "vol", "seek": "seek"}
if TOGGLE:
    if TOGGLE_TRACK: SPRITE_PARTS[TOGGLE + "_lever"] = TOGGLE
    else: SPRITE_PARTS[TOGGLE + "_off"] = TOGGLE; SPRITE_PARTS[TOGGLE + "_on"] = TOGGLE
sprite_flagged = []
if os.path.exists(BIREF):
    print("sprite guide-hue contamination (biref-cut PART pixels vs their own guide key):")
    for part_file, key_name in SPRITE_PARTS.items():
        if not key_name or key_name not in KEYS: continue
        pf = os.path.join(BIREF, part_file + ".png")
        if not os.path.exists(pf): continue
        sarr = np.asarray(Image.open(pf).convert("RGBA"))
        salpha = sarr[:, :, 3] > 30
        if salpha.sum() < 200: continue
        shsv = np.asarray(Image.open(pf).convert("RGB").convert("HSV")).astype(int)
        skh = int(colorsys.rgb_to_hsv(*[v / 255 for v in KEYS[key_name]])[0] * 255)
        shd = np.minimum(np.abs(shsv[..., 0] - skh), 255 - np.abs(shsv[..., 0] - skh))
        shit = salpha & (shd < 20) & (shsv[..., 1] > RING_SAT_FLOOR) & (shsv[..., 2] > RING_VAL_FLOOR) & ~palette_mask(shsv)
        spct = 100.0 * float(shit.sum()) / float(salpha.sum())
        sflag = spct > SPRITE_CONTAM_THRESH
        label = "sprite:" + part_file
        if sflag and label not in ring_flagged: ring_flagged.append(label); sprite_flagged.append(label)
        print(f"  {part_file:12} own-key-match {spct:6.1f}%  {'FAIL - sprite contamination' if sflag else 'ok'}")
    if sprite_flagged: print(f"[sprite-contam gate] FAIL - regenerate: {','.join(sprite_flagged)}")

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

# ---- FIT CHECK (diagnostic only, NOT gated) ----
# device vs raw paint-band "strip" bbox. Kept print-only: calibration against the roster
# (2026-07-11) showed this pairing is too noisy to gate on -- the strip bbox is a rough
# same-hue paint blob that on some skins includes extra reference art (e.g. a toggle's whole
# housing+lever preview icon, not just the lever), so it swings independent of the real
# rendered defect. The SPRITE-VS-SLOT FIT gate below uses the BIREF-cut asset instead (the
# actual pixels the player composites), which is the "cut sprite" the task means.
print("fit check (device slot vs strip part, w x h ratio) [diagnostic, not gated]:")
for k in KNOBS + ([TOGGLE] if TOGGLE else []):
    r = regs.get(k)
    if not r or not r.get("device") or not r.get("strip") or not r["strip"][0]: continue
    d_ = r["device"]; s = r["strip"][0]
    rw = d_[2] / s[2]; rh = d_[3] / s[3]
    flag = " <- MISMATCH >15%" if abs(1 - rw) > 0.15 or abs(1 - rh) > 0.15 else ""
    print(f"  {k:8} slot/part w={rw:.2f} h={rh:.2f}{flag}")

# ---- SPRITE-VS-SLOT FIT GATE (sprite-fit:<part>) ----
# 7/15 human-review skins named a switch (or slider thumb) that doesn't match its slot --
# "too small", "too large", "slot and switch dont match". Compares the ACTUAL rendered asset
# (the BIREF-cut PNG's alpha bbox -- the pixels build_player.py composites) against the
# detected slot, not the rough paint-band "strip" bbox above (see note there for why that
# pairing is unusable). No VLM: pure cut-vs-slot geometry.
#
# TOGGLE: symmetric area ratio r = min(slotArea,spriteArea)/max(...) in [0,1], 1=perfect.
# Calibrated 2026-07-11 against the 15-skin roster (7 human-named: claymation, fa-pod,
# fallout-pipboy, n64-cutscene, steam-porthole, wc-goldshield, wmp-vario):
#   named-mismatch r values: .20 .39 .45 .46 .73 .74 .877 (goldshield..pipboy)
#   clean/unflagged r values: .18(ps1-wild) .34(diablo) .79(quicksilver) .85(ps1-crunchy)
#                              .87(fa-sky) .99(n64-prerender-character)
# The two populations OVERLAP (ps1-wild .18 sits below goldshield's .20; diablo .34 sits
# below claymation's .39) -- bbox-area geometry alone does not cleanly separate this roster;
# several named complaints ("switch slot doesnt match sprite") likely reflect a SHAPE/style
# mismatch a w x h bbox can't see. Threshold 0.78 was chosen to maximize named-case recall
# (6/7 -- misses only pipboy at r=.877, which independently fails via baked-thumb since
# pipboy is ALSO one of the 6 baked-thumb-flagged skins, so the skin still fails gate
# overall) while limiting false positives (2/8 unflagged: ps1-wild, diablo-gothic -- see
# report table). This is an honest partial-recall gate, not a perfect classifier.
#
# SLIDER thumb: thumb cross-dim (perpendicular to travel) vs groove cross-dim. Overhang
# (thumb WIDER than the groove) is normal skeuomorphic design -- this roster's clean skins
# span ratio 0.57-4.93 with no separation at the one named case (steam-porthole "slider knob
# too large" measured 1.74, squarely mid-pack) -- so the bound here is deliberately wide and
# only catches gross degenerate cases (thumb lost inside the groove, or grotesquely
# oversized beyond anything in this roster), not steam-porthole's specific complaint. That
# skin still fails gate overall via its TOGGLE sprite-fit hit (r=.46, well under 0.78) and
# its own guide-ring/other reasons.
FIT_AREA_THRESH = 0.78
SLIDER_CROSS_LO, SLIDER_CROSS_HI = 0.55, 6.5


def _alpha_bbox(path):
    if not os.path.exists(path): return None
    a = np.asarray(Image.open(path).convert("RGBA"))[:, :, 3] > 30
    ys, xs = np.where(a)
    if len(xs) < 20: return None
    return xs.max() - xs.min() + 1, ys.max() - ys.min() + 1


if os.path.exists(BIREF):
    print("sprite-fit gate (biref-cut sprite vs detected slot, area/size ratio):")
    if TOGGLE and TOGGLE_TRACK:
        # TOGGLE_TRACK contract: the LEVER is SUPPOSED to be smaller than its track (it slides
        # within, like the seek thumb in its groove) — the legacy fill-the-slot area-ratio test
        # is wrong-shaped here. Use the slider-thumb-style CROSS-dim bounds instead: lever
        # cross-dim (perpendicular to the slide axis) vs track cross-dim. Same wide-bound
        # philosophy as SLIDER_CROSS_LO/HI (catch gross degenerates, not taste).
        r = regs.get(TOGGLE)
        dev = (r or {}).get("device")
        if dev:
            sbb = _alpha_bbox(os.path.join(BIREF, TOGGLE + "_lever.png"))
            if sbb:
                tvert = bool(r.get("vertical"))
                trackCross = dev[2] * PW3 if tvert else dev[3] * PH3
                leverCross = sbb[0] if tvert else sbb[1]
                ratio = leverCross / max(1.0, trackCross)
                flag = not (SLIDER_CROSS_LO <= ratio <= SLIDER_CROSS_HI)
                r["spriteFit"] = {"leverCrossRatio": round(ratio, 3), "flag": flag}
                print(f"  {TOGGLE:8} track-cross {trackCross:.0f}px vs lever-cross {leverCross}px "
                      f"ratio={ratio:.2f}  {'FAIL - lever size mismatch' if flag else 'ok'}")
                if flag: sprite_fit_flagged.append(TOGGLE)
    elif TOGGLE:
        r = regs.get(TOGGLE)
        dev = r.get("device") if r else None
        if dev:
            sbb = _alpha_bbox(os.path.join(BIREF, TOGGLE + "_off.png"))
            if sbb:
                dw, dh = dev[2] * PW3, dev[3] * PH3
                dArea = dw * dh; sArea = sbb[0] * sbb[1]
                ratio = min(dArea, sArea) / max(dArea, sArea)
                flag = ratio < FIT_AREA_THRESH
                r["spriteFit"] = {"areaRatio": round(ratio, 3), "flag": flag}
                print(f"  {TOGGLE:8} slot {dw:.0f}x{dh:.0f}px vs sprite {sbb[0]}x{sbb[1]}px "
                      f"area-ratio={ratio:.3f}  {'FAIL - sprite/slot mismatch' if flag else 'ok'}")
                if flag: sprite_fit_flagged.append(TOGGLE)
    if SLIDER:
        r = regs.get(SLIDER)
        dev = r.get("device") if r else None
        if dev:
            sbb = _alpha_bbox(os.path.join(BIREF, SLIDER + ".png"))
            if sbb:
                vert = bool(r.get("vertical"))
                grooveCross = dev[2] * PW3 if vert else dev[3] * PH3
                thumbCross = sbb[0] if vert else sbb[1]
                ratio = thumbCross / max(1.0, grooveCross)
                flag = not (SLIDER_CROSS_LO <= ratio <= SLIDER_CROSS_HI)
                r["spriteFit"] = {**(r.get("spriteFit") or {}), "thumbCrossRatio": round(ratio, 3), "flagThumb": flag}
                print(f"  {SLIDER:8} groove-cross {grooveCross:.0f}px vs thumb-cross {thumbCross}px "
                      f"ratio={ratio:.2f}  {'FAIL - thumb size mismatch' if flag else 'ok'}")
                if flag: sprite_fit_flagged.append(SLIDER)

# ---- TEMPLATE-DRIFT GATE (templated mode only) ----
# Per-control drift: distance (px, on THIS skin's own paint.png pixel grid) between the
# blueprint-DECLARED template centre (results.json `template`, baked at generation time) and
# the DETECTED device centre (regs[k].device bbox centre). Ported VERBATIM from
# twoimg/roster_audit.py's drift_table() -- the exact metric all three drift-suspect bisects
# used (218224f7 clause bisect, 892bf045 extraction-commit bisect, 448d8f87 serving bisect),
# per placement-invariants-rule/verify-outputs-rule "don't fork the metric". That chain closed
# CAUSE-hunting: drift is real, paint-driven, and neither the extractor, the BOLD-silhouette
# clause, nor the fal->Vertex serving switch is the driver (per-gen variance at fixed config
# measured 330-420px in the serving bisect). Its actionable conclusion (448d8f87's TODO entry)
# was to stop cause-hunting and start SURFACING drift per roll for human triage instead --
# this gate is that surface.
#
# Controls that fell back to the raw template position (regs[k].fromTemplate, already its own
# "knob-template-fallback" reason above) are EXCLUDED from the mean/worst calc: a fallback
# trivially reads ~0px drift (it's a template pass-through, not a real detection), which would
# artificially deflate the mean -- the same correction driftbisect2/README.md had to apply
# after finding 2 such fallbacks flattering the old extractor's numbers.
#
# THRESHOLD = 650px mean drift, calibrated 2026-07-11 against the live roster audit
# (twoimg/roster_audit.json) plus the bisect chain's own 150px noise floor:
#   - today's healthy/PASSing templated skins: fa-pod 502.9, ps1-crunchy 415.4,
#     wc-goldshield 461.6, wmp-quicksilver 542.2px mean drift -- 542px is the healthy ceiling.
#   - the bisect chain's own worst regressors (the reason this gate exists): fallout-pipboy
#     950.5px, steam-porthole 858.3px mean drift.
#   650px sits ~110px above the healthy ceiling and ~210px below the weakest regressor -- on
#   both sides that's outside the 150px noise floor the bisects established, so a single
#   session's per-gen variance (330-420px, per servingbisect) shouldn't flip a genuinely
#   healthy skin to FAIL or a genuine regressor to PASS. This is a TRIAGE threshold, not a
#   hard quality bar: auto-reroll is OFF by default (generation-spend-rule) -- a drift FAIL
#   here only shows up on the dashboard for a human to decide whether to spend a re-roll; it
#   never burns spend on its own.
DRIFT_THRESH_PX = 650.0
drift_info = None
if TEMPLATED and template:
    def _drift_table(tmpl, regs_, W, H):
        """Verbatim port of twoimg/roster_audit.py:drift_table() -- do not fork this metric."""
        out = {}
        for k, t in tmpl.items():
            dev = (regs_.get(k) or {}).get("device")
            if not dev:
                continue
            cx, cy = dev[0] + dev[2] / 2, dev[1] + dev[3] / 2
            dxp, dyp = (cx - t[0]) * W, (cy - t[1]) * H
            out[k] = float((dxp ** 2 + dyp ** 2) ** 0.5)
        return out
    _PW, _PH = p.size
    _dt = _drift_table(template, regs, _PW, _PH)
    _fallback_ctrls = sorted(k for k in _dt if (regs.get(k) or {}).get("fromTemplate"))
    _scored = {k: v for k, v in _dt.items() if k not in _fallback_ctrls}
    if _scored:
        _mean = float(np.mean(list(_scored.values())))
        _worst_k, _worst_v = max(_scored.items(), key=lambda kv: kv[1])
        drift_info = {
            "per_control": {k: round(v, 1) for k, v in _dt.items()},
            "excluded_fallback": _fallback_ctrls,
            "mean_px": round(_mean, 1),
            "worst": [_worst_k, round(_worst_v, 1)],
            "threshold_px": DRIFT_THRESH_PX,
        }
        print(f"[drift gate] mean={_mean:.1f}px worst={_worst_k}({_worst_v:.1f}px) "
              f"threshold={DRIFT_THRESH_PX:.0f}px "
              f"{'FAIL - regenerate' if _mean > DRIFT_THRESH_PX else 'ok'}")

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
# TOGGLE_TRACK contract has no state pair — stateAlign never exists and the gate is vacuous
sa = (regs.get(TOGGLE) or {}).get("stateAlign") if (TOGGLE and not TOGGLE_TRACK) else None
sa_ok = bool(sa and 0.7 <= sa.get("scaleX", 0) <= 1.4 and 0.7 <= sa.get("scaleY", 0) <= 1.4 and sa.get("iou", 0) >= 0.05) \
        if not TOGGLE_TRACK else True
# biref parts present (toggle contributes ONE lever under the track contract, two states legacy)
_tog_parts = ([TOGGLE + "_lever"] if TOGGLE_TRACK else [TOGGLE + "_off", TOGGLE + "_on"]) if TOGGLE else []
biref_parts = [p for p in ["vol", "seek"] + _tog_parts if TOGGLE
               and os.path.exists(os.path.join(BIREF, p + ".png"))]
need_parts = (KNOBS + ([SLIDER] if SLIDER else []) + _tog_parts)
biref_ok = all(os.path.exists(os.path.join(BIREF, p + ".png")) for p in need_parts) if os.path.exists(BIREF) else None
# region misplacement: refit landed far from the mask blob -> the model painted the display
# blob off its window; the render was rescued by the refit but the generation is visually broken
region_misplaced = []
for k in SC:
    r = regs.get(k)
    if not (r and r.get("device") and r.get("maskDevice")): continue
    if _iou(r["device"], r["maskDevice"]) < 0.5: region_misplaced.append(k)
# region degeneracy: a detected region whose AREA is implausibly small passed every other
# numeric gate while being visually broken (the burn: claymation shipped a ~143x188px
# album_art sliver, 0.42% of the device column area, that sailed through -- observation
# table 92b95e17). Material-agnostic thresholds, no absolute pixel counts:
#   * templated  -- the blueprint DECLARED this region's rect (results.json <k>_rect, the
#     same fraction-of-canvas frame the template fallback at region assignment uses); flag
#     when the detected area collapsed below 25% of the declared area (the model may
#     legitimately restyle a window somewhat; a 4x area collapse is a defect).
#   * templateless -- no declared size exists; flag when the region's area falls below 1.0%
#     of the device column area (devFrac). Calibrated on the 15-skin roster 2026-07-11:
#     healthy regions span 1.79%..13.86% of device area; the claymation burn measured
#     0.42% -- the 1.0% floor sits >2x from both sides of that gap.
region_degenerate = []
for k in SC:
    r = regs.get(k)
    if not (r and r.get("device")): continue
    area = r["device"][2] * r["device"][3]
    trect = RES.get(k + "_rect")
    if TEMPLATED and trect:
        if area < 0.25 * (trect[2] * trect[3]): region_degenerate.append(k)
    elif area / max(1e-6, DEVF) < 0.010:
        region_degenerate.append(k)
# ---- SILHOUETTE-MATCH gate (silcheck.py, d28a83ea) ----
# Deterministic geometry replacement for the VLM's 0%-recall silhouette-mismatch judgment
# (verification-recalibration lane): does each baked icon button's own painted silhouette sit
# inside and fill the device bbox build_player.py's press overlay uses? Verbatim port of the
# player's ink-silhouette extraction, calibrated on the 15-skin roster (catches steam-porthole
# + wmp-quicksilver named cases; one genuine unlabeled fa-pod/prev finding; zero other false
# positives). NOTE: silcheck must run AFTER regions.json is written below — but the gate needs
# it BEFORE. It reads regs from the file, so run it against the current regs dict via a
# temp-consistent path: regions.json on disk at this point is the pass-1/2 file WITHOUT the
# gate block, but all region geometry is already final (this summary only appends `gate`), so
# the check is valid.
try:
    import silcheck
    _sil = silcheck.run(OUT) or {}
except Exception as _e:
    _sil = {}
    print(f"[silcheck] skipped ({_e})")
sil_flagged = [b for b, mm in _sil.items() if mm.get("verdict") == "FAIL"]
if sil_flagged: print(f"[silcheck gate] FAIL - silhouette mismatch: {','.join(sil_flagged)}")
reasons = []
knob_tmpl = [k for k in KNOBS if (regs.get(k) or {}).get("fromTemplate")]
if knob_tmpl: reasons.append("knob-template-fallback:" + ",".join(knob_tmpl))
for k in region_misplaced: reasons.append(f"region-misplaced:{k}")
for k in region_degenerate: reasons.append(f"region-degenerate:{k}")
if empty_fail: reasons.append("emptiness")
if missing: reasons.append("missing:" + ",".join(missing))
if seek_cov is not None and seek_cov < 0.7: reasons.append(f"seek-cov={seek_cov}")
if TOGGLE and not sa_ok and sa is not None: reasons.append("state-align")
if biref_ok is False: reasons.append("biref-parts")
leak_val = RES.get("leak")
if leak_val is not None and leak_val > 0.003: reasons.append(f"leak={leak_val}")
if ring_flagged: reasons.append("guide-ring:" + ",".join(ring_flagged))
drift_fail = bool(drift_info and drift_info["mean_px"] > DRIFT_THRESH_PX)
if drift_fail: reasons.append(f"drift:{drift_info['worst'][0]}")
if baked_thumb_flagged: reasons.append("baked-thumb:" + ",".join(baked_thumb_flagged))
if sprite_fit_flagged: reasons.append("sprite-fit:" + ",".join(sprite_fit_flagged))
if orientation_flagged: reasons.append("orientation:device")
for k in sil_flagged: reasons.append(f"silhouette-mismatch:{k}")
gate = {"empty_ok": not empty_fail, "controls": len(NAMES) - len(missing), "controls_total": len(NAMES),
        "missing": missing, "seek_cov": seek_cov, "state_align_ok": sa_ok, "biref_ok": biref_ok,
        "leak": RES.get("leak"), "guide_ring": ring_flagged,
        "region_degenerate": region_degenerate,
        "baked_thumb": baked_thumb_flagged, "sprite_fit": sprite_fit_flagged,
        "silhouette_mismatch": sil_flagged,
        "orientation_ok": not orientation_flagged, "reasons": reasons,
        "PASS": (not empty_fail) and (not missing) and (not knob_tmpl) and (not region_misplaced)
                and (not region_degenerate)
                and (seek_cov is None or seek_cov >= 0.7)
                and (biref_ok is not False) and (RES.get("leak", 0) is None or RES.get("leak", 0) <= 0.003)
                and (not TOGGLE or sa is None or sa_ok) and (not ring_flagged) and (not drift_fail)
                and (not baked_thumb_flagged) and (not sprite_fit_flagged) and (not orientation_flagged)
                and (not sil_flagged)}
R2 = json.load(open(os.path.join(OUT, "regions.json"))); R2["gate"] = gate
if drift_info is not None: R2["drift"] = drift_info
json.dump(R2, open(os.path.join(OUT, "regions.json"), "w"), indent=2)
_drift_str = f"drift={drift_info['mean_px']}px" if drift_info else "drift=n/a"
print(f"[GATE] {'PASS' if gate['PASS'] else 'FAIL'} "
      f"controls={gate['controls']}/{gate['controls_total']} seek_cov={seek_cov} "
      f"empty={'ok' if not empty_fail else 'FAIL'} align={'ok' if sa_ok else 'x'} {_drift_str} "
      f"reasons={reasons or 'none'}")
