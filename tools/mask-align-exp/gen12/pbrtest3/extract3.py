#!/usr/bin/env python3
"""pbrtest3 — GLYPH-shaped emissive extraction + interactivity metadata (all local, $0).

Round-2 failure (human verdict): HSV chroma/value windows caught broad orange specular
splatter on stone instead of the rune GLYPHS. Fix: the glow score must ALSO pass a
LOCAL-CONTRAST gate — glowing glyphs/cracks are THIN bright features against darker
surroundings, splatter is broad low-frequency warmth. Implementation: morphological
TOP-HAT (score - grey_opening(score, k)) at two scales (stroke k=31, crack k=61),
tighter sat/val knees, component-area cap, light erode, tight feather.

Also emits everything the interactive page needs, precomputed in SRC-UV space
(diablo-src.png = top 3016 rows of paint.png, 2304x3712):
  - btn-ids.png       L-mode: each button silhouette painted (idx+1)*36, drift-corrected
  - sprite-seek.png / sprite-shuffle-off/on.png  tight-cropped moving parts
  - diablo-meta3.json knob seat, seek travel+home, shuffle rect, button rects+ids,
                      viz/glass rects, emissive point lights, glassFill
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).parent
GEN12 = HERE.parent
ASSET = GEN12 / "assets-diablo-gothic"
BIREF = GEN12 / "assets-diablo-gothic_biref"
P2 = GEN12 / "pbrtest2"

SRC = P2 / "diablo-src.png"
src_im = Image.open(SRC).convert("RGB")
W, H = src_im.size                      # 2304 x 3016
PAINT_H = Image.open(ASSET / "paint.png").height  # 3712
YS = PAINT_H / H                        # paint-frac-y -> src-frac-y multiplier
src = np.asarray(src_im, np.float32) / 255.0


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def opening(img_l, k):
    return img_l.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))


# ---------------- knob-socket detector (2026-07-10 fix) ----------------
# WHY this exists instead of regions.json's vol.seat: assets-diablo-gothic/regions.json
# has been REWRITTEN TWICE since diablo-src.png was captured for pbrtest2/pbrtest3 (a
# 15-skin regen-all run produced an entirely different diablo-gothic paint layout — see
# the WARNING above the button-id block). Re-deriving the knob seat from the CURRENT
# regions.json would misplace it into the button cluster (verified: vol.seat converts to
# ~(0.50, 0.53), which sits on the repeat/queue icons, not either round socket). Per
# placement-invariants-rule ("compute from the paint, don't hand-nudge"), this detector
# finds BOTH round recessed sockets directly in the ACTUAL rendered image (diablo-src.png)
# by darkness + shape, independent of any regions.json — future paint regens can't
# re-break it because it no longer depends on stale mainline metadata at all.
def _radial_probe(lum_img, cx0, cy0, max_r, nang=32, jump=0.22):
    Wp, Hp = lum_img.shape[1], lum_img.shape[0]
    core = float(lum_img[int(round(cy0)), int(round(cx0))])
    radii = []
    for k in range(nang):
        ang = 2 * np.pi * k / nang
        dx, dy = np.cos(ang), np.sin(ang)
        found = None
        for r in range(5, max_r):
            x = int(round(cx0 + dx * r)); y = int(round(cy0 + dy * r))
            if not (0 <= x < Wp and 0 <= y < Hp):
                break
            if lum_img[y, x] > core + jump:
                found = r
                break
        radii.append(found)
    return radii


def find_knob_sockets(src_rgb, n=2):
    """Return up to `n` round, near-black recessed sockets in src_rgb (RGB, 0..1),
    sorted left-to-right. Each: {c:[x/W, y/H], r: r/W}. Pure shape/darkness detection —
    no coordinates from regions.json, no hand-typed pixel positions."""
    from scipy import ndimage

    Hp, Wp = src_rgb.shape[:2]
    lum = src_rgb.mean(axis=-1)
    lum_s = np.asarray(
        Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)),
        np.float32) / 255.0

    dark = lum_s < 0.16   # sockets measure ~0.12-0.15; body/buttons/runes are brighter
    lab, ncomp = ndimage.label(dark)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, ncomp + 1))
    coms = ndimage.center_of_mass(dark, lab, range(1, ncomp + 1))

    cands = []
    for i in range(ncomp):
        area = sizes[i]
        if area < 8000:
            continue
        cy, cx = coms[i]
        ys, xs = np.where(lab == i + 1)
        bw, bh = xs.max() - xs.min(), ys.max() - ys.min()
        if bw == 0 or bh == 0 or not (0.85 <= bw / bh <= 1.18):
            continue          # knobs are round -> near-square bbox; screens/slots aren't
        naive_r = (area / np.pi) ** 0.5
        if not (0.035 * Wp <= naive_r <= 0.115 * Wp):
            continue          # plausible knob-cap size band (fraction of image width)
        max_r = int(naive_r * 2.2)
        radii = _radial_probe(lum_s, cx, cy, max_r)
        found = [r for r in radii if r is not None]
        if len(found) / len(radii) < 0.8:
            continue          # no consistent bright rim nearby -> not a round bezel (rejects screens)
        rr = np.array(found)
        cv = rr.std() / rr.mean()
        if cv >= 0.35:
            continue          # too irregular to be a true circular socket
        pts = np.array([(cx + np.cos(2 * np.pi * k / len(radii)) * r,
                          cy + np.sin(2 * np.pi * k / len(radii)) * r)
                         for k, r in enumerate(radii) if r is not None])
        cx_ref, cy_ref = float(pts[:, 0].mean()), float(pts[:, 1].mean())
        # coverage-safe bias (placement-invariants-rule): the diamond-tab decoration
        # pulls some rays' rim-crossing radius short of the true bezel edge, so the
        # raw median slightly undershoots on the tab-recessed sides — bump 6% so the
        # cap sprite fully covers the recess rather than exposing a socket crescent.
        r_ref = float(np.median(rr)) * 1.06
        cands.append((cv, cx_ref, cy_ref, r_ref))

    cands.sort(key=lambda c: c[0])           # best circularity first
    cands = cands[:n]
    cands.sort(key=lambda c: c[1])           # then left-to-right for stable ordering
    return [{"c": [round(cx_ref / Wp, 4), round(cy_ref / Hp, 4)], "r": round(r_ref / Wp, 4)}
            for _, cx_ref, cy_ref, r_ref in cands]


# ---------------- 1. glyph-shaped emissive ----------------
mx = src.max(axis=-1)
mn = src.min(axis=-1)
val = mx
sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
r, g, b = src[..., 0], src[..., 1], src[..., 2]
d = np.maximum(mx - mn, 1e-6)
hue = np.zeros((H, W), np.float32)
m = mx == r
hue[m] = (60 * ((g - b) / d) % 360)[m]
m = mx == g
hue[m] = (60 * ((b - r) / d) + 120)[m]
m = mx == b
hue[m] = (60 * ((r - g) / d) + 240)[m]
hmask = ((hue <= 50) | (hue >= 330)).astype(np.float32)

# tighter knees than round 2 — emissive cores are near-saturated and bright
score = smoothstep(0.55, 0.78, sat) * smoothstep(0.30, 0.55, val) * hmask
sc_img = to_img(score)

# local-contrast gate: two-scale top-hat (thin strokes k=31, lava cracks k=61)
th31 = np.asarray(sc_img, np.float32) / 255 - np.asarray(opening(sc_img, 31), np.float32) / 255
th61 = np.asarray(sc_img, np.float32) / 255 - np.asarray(opening(sc_img, 61), np.float32) / 255
tophat = np.maximum(th31, 0.75 * th61)
glow = score * smoothstep(0.10, 0.35, tophat)

# clean: light erode (kills 1px fringe), then component-area cap (no broad splatter)
gl_img = to_img(glow).filter(ImageFilter.MinFilter(3))
glow = np.asarray(gl_img, np.float32) / 255

# connected components at 1/4 res; drop huge blobs (splatter) + dust
ds = 4
small = glow[::ds, ::ds] > 0.25
lab = np.zeros(small.shape, np.int32)
comps = []
nlab = 0
for yy in range(small.shape[0]):
    for xx in range(small.shape[1]):
        if small[yy, xx] and lab[yy, xx] == 0:
            nlab += 1
            stack = [(yy, xx)]
            lab[yy, xx] = nlab
            pix = []
            while stack:
                cy, cx = stack.pop()
                pix.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < small.shape[0] and 0 <= nx < small.shape[1] \
                           and small[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = nlab
                            stack.append((ny, nx))
            comps.append((nlab, np.array(pix)))

A_MAX = 5200   # 1/4-res px -> ~83k full-res px; biggest legit crack chain ~2-3k
A_MIN = 4      # dust
kill = np.zeros(small.shape, bool)
kept = []
for lid, pts in comps:
    a = len(pts)
    if a < A_MIN or a > A_MAX:
        kill[pts[:, 0], pts[:, 1]] = True
    else:
        kept.append((lid, pts))
kill_full = np.kron(kill, np.ones((ds, ds), bool))[:H, :W]
glow[kill_full] = 0

# tight feather: tiny blur, steep knee — the CORE stays hot, halo is the shader's job
fe = to_img(glow).filter(ImageFilter.GaussianBlur(1.6))
mask = smoothstep(0.18, 0.60, np.asarray(fe, np.float32) / 255)

# emissive colour: src pushed toward its chroma + a hot core ramp (near-white cores)
em = src / np.maximum(val[..., None], 0.30)
core = smoothstep(0.75, 1.0, mask * val)[..., None]
em = np.clip(em + core * np.array([0.9, 0.55, 0.30]), 0, 1)
rgba = np.dstack([(em * 255).astype(np.uint8), (mask * 255).astype(np.uint8)])
Image.fromarray(rgba, "RGBA").save(HERE / "diablo-emissive3.png")
print("emissive coverage:", round(float(mask.mean()), 5), f"(round2 was 0.0144) — {len(kept)} components kept")

# ---------------- 2. point lights from kept clusters ----------------
en = mask * val
lights = []
comp_e = []
for lid, pts in kept:
    ys = np.clip(pts[:, 0] * ds, 0, H - 1)
    xs = np.clip(pts[:, 1] * ds, 0, W - 1)
    e = en[ys, xs]
    comp_e.append((float(e.sum()), pts, e))
comp_e.sort(key=lambda c: -c[0])
tot = sum(c[0] for c in comp_e) or 1.0
for e_sum, pts, e in comp_e[:6]:
    w_ = e / max(e.sum(), 1e-6)
    cy = float((pts[:, 0] * w_).sum()) * ds / H
    cx = float((pts[:, 1] * w_).sum()) * ds / W
    ys = np.clip(pts[:, 0] * ds, 0, H - 1)
    xs = np.clip(pts[:, 1] * ds, 0, W - 1)
    col = em[ys, xs].mean(axis=0)
    lights.append({"uv": [round(cx, 4), round(cy, 4)],
                   "color": [round(float(c), 3) for c in col],
                   "energy": round(e_sum / tot, 3)})

# ---------------- 3. button id mask (drift-corrected into paint/src space) ----------------
# WARNING: assets-diablo-gothic/regions.json was REWRITTEN by the batch re-cut
# (86bbb3aa) AFTER diablo-meta3.json was generated (7369dc34) — its rects no longer
# match diablo-src.png. Re-running this script against current regions.json will
# MISPLACE everything. The 2026-07-09 switch-orientation fix was therefore applied
# to the on-disk sprites + meta3.json directly with the same slot_walk math below.
R = json.load(open(ASSET / "regions.json"))
regs, keys = R["regions"], R["keys"]
mask_im = np.asarray(Image.open(ASSET / "mask.png").convert("RGB"), np.int32)
MH_, MW_ = mask_im.shape[:2]
ids = np.zeros((H, W), np.uint8)
btn_meta = []
for i, bname in enumerate(R["buttons"]):
    reg = regs.get(bname)
    if not reg or not reg.get("device"):
        continue
    db, mb = reg["device"], reg.get("maskDevice", reg["device"])
    k = np.array(keys[bname])
    pad = 0.10
    x0 = int((mb[0] - mb[2] * pad) * MW_); x1 = int((mb[0] + mb[2] * (1 + pad)) * MW_)
    y0 = int((mb[1] - mb[3] * pad) * MH_); y1 = int((mb[1] + mb[3] * (1 + pad)) * MH_)
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(MW_, x1), min(MH_, y1)
    crop = mask_im[y0:y1, x0:x1]
    hit = ((crop - k) ** 2).sum(axis=-1) < 7000
    # drift: device centre - mask centre (fractions of paint W/H)
    dxp = int(round(((db[0] + db[2] / 2) - (mb[0] + mb[2] / 2)) * MW_))
    dyp = int(round(((db[1] + db[3] / 2) - (mb[1] + mb[3] / 2)) * MH_))
    ty0, tx0 = y0 + dyp, x0 + dxp
    hh, ww = hit.shape
    sy0, sx0 = max(0, ty0), max(0, tx0)
    sy1, sx1 = min(H, ty0 + hh), min(W, tx0 + ww)
    if sy1 > sy0 and sx1 > sx0:
        sub = hit[sy0 - ty0:sy1 - ty0, sx0 - tx0:sx1 - tx0]
        region = ids[sy0:sy1, sx0:sx1]
        region[sub] = (i + 1) * 36
    # device rect in src-uv
    btn_meta.append({"name": bname, "id": (i + 1) * 36,
                     "rect": [round(db[0], 4), round(db[1] * YS, 4),
                              round(db[2], 4), round(db[3] * YS, 4)]})
# CAVEAT: this mask is cropped from the LIVE mainline regions.json/mask.png — the same
# moving target the end-of-script drift guard protects the JSON fields from. If that
# guard prints a "drifted" warning for 'buttons' on a future run, this PNG (and the
# seek/shuffle sprites below) were ALSO just overwritten from the wrong snapshot even
# though the JSON self-healed — `git checkout HEAD -- btn-ids.png sprite-*.png` to match.
Image.fromarray(ids, "L").save(HERE / "btn-ids.png")

# ---------------- 4. moving-part sprites (tight-crop) ----------------
def tight(name):
    im = Image.open(BIREF / f"{name}.png").convert("RGBA")
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > 12)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    t = im.crop((x0, y0, x1 + 1, y1 + 1))
    return t

sk = tight("seek"); sk.save(HERE / "sprite-seek.png")
so = tight("shuffle_off")
sn = tight("shuffle_on")
mirror_on = np.array_equal(np.asarray(so), np.asarray(sn))


# ---- switch orientation must MATCH THE PAINTED SLOT, not the biref cut frame.
# The biref sprite is tight-cropped in whatever orientation the model painted the
# donor strip; the slot on the body can be the other way (diablo: vertical slot,
# horizontal strip sprite -> rendered 90° wrong). Measure the slot's long axis in
# the PAINT with a relative rim-walk (percentile-scaled threshold, no absolute
# luminance) and rotate the sprite to match. Per-side outer walk (dark core PLUS
# bright bezel rim) also gives the coverage rect + true slot centre.
def slot_walk(cx_px, cy_px, win=340):
    lum = Image.open(SRC).convert("L").filter(ImageFilter.GaussianBlur(6))
    sm_ = np.asarray(lum, np.float32)
    w_ = sm_[cy_px - win:cy_px + win, cx_px - win:cx_px + win]
    lo, hi = np.percentile(w_, 10), np.percentile(w_, 90)
    thr = sm_[cy_px, cx_px] + 0.5 * (hi - lo)     # rim = clearly brighter than core

    def outer(dx, dy):
        d = 0; x, y = cx_px, cy_px; hit = False; inner = None
        while d < win:
            x += dx; y += dy; d += 1
            bright = sm_[y, x] > thr
            if bright and not hit: hit = True; inner = d
            elif not bright and hit: return d    # bezel outer edge
        return inner or d
    ol, orr = outer(-1, 0), outer(1, 0)
    ou, od = outer(0, -1), outer(0, 1)
    return {"w": ol + orr, "h": ou + od,
            "cx": cx_px + (orr - ol) // 2, "cy": cy_px + (od - ou) // 2}

# ---------------- 5. placement meta (all in SRC-UV: x/W, y/src_H) ----------------
def ctr(bx):
    return [bx[0] + bx[2] / 2, bx[1] + bx[3] / 2]

seek = regs["seek"]; shuf = regs["shuffle"]
# knob seat(s): detected directly in diablo-src.png (see find_knob_sockets above) —
# NOT from regions.json's vol.seat, which no longer matches this paint. Two round
# sockets exist in the paint; the RIGHT one is the original interactive "knob", the
# LEFT one was previously left empty (2026-07-10: filled with a second knob, same
# detection + same cap sprite, reusing the circle-fit here rather than hand-placing it).
sockets = find_knob_sockets(src, n=2)
if len(sockets) < 2:
    raise SystemExit(f"find_knob_sockets: expected 2 round sockets, found {len(sockets)} — "
                      "check the darkness/shape thresholds against the current paint")
knob2, knob = sockets                    # left-to-right: knob2 (left), knob (right, original)

tk = seek["device"]; tv = seek.get("travel", [tk[0], tk[0] + tk[2]])
thw = sk.width / W; thh = sk.height / PAINT_H            # sprite frac of paint
seek_m = {
    "cy": round((tk[1] + tk[3] / 2) * YS, 4),
    "w": round(thw, 4), "h": round(thh * YS, 4),
    "x0": round(tv[0], 4), "x1": round(tv[1] - thw, 4),   # left-edge travel clamp
    "track": [round(tk[0], 4), round(tk[1] * YS, 4), round(tk[2], 4), round(tk[3] * YS, 4)],
}
tc = ctr(shuf["device"])
slot = slot_walk(int(tc[0] * W), int(tc[1] * YS * H))
slot_vertical = slot["h"] > slot["w"]
sprite_vertical = so.height > so.width
if slot_vertical != sprite_vertical:
    # ROTATE_270 = clockwise: a right-side lever lands at the BOTTOM (off = down)
    so = so.transpose(Image.ROTATE_270)
    sn = sn.transpose(Image.ROTATE_270)
if mirror_on:
    # state change = lever flips ends, along the slot's LONG axis
    sn = so.transpose(Image.FLIP_TOP_BOTTOM if slot_vertical else Image.FLIP_LEFT_RIGHT)
so.save(HERE / "sprite-shuffle-off.png")
sn.save(HERE / "sprite-shuffle-on.png")

# coverage rect: sprite scaled uniformly to COVER the measured slot (never leave
# exposed slot ends), centred on the measured slot centre — all computed, no
# hand-authored numbers (placement-invariants-rule)
cov = max(slot["w"] / so.width, slot["h"] / so.height)
sw = so.width * cov / W; sh_ = so.height * cov / H
shuf_m = {"rect": [round(slot["cx"] / W - sw / 2, 4), round(slot["cy"] / H - sh_ / 2, 4),
                   round(sw, 4), round(sh_, 4)]}

m2 = json.load(open(P2 / "diablo-meta.json"))
viz = regs["visualizer"]["device"]; art = regs["album_art"]["device"]
meta = {
    "size": [W, H],
    "glassFill": m2["glassFill"],
    "glassRects": m2["glassRects"],           # px in src space (from round 2)
    "viz": [round(viz[0], 4), round(viz[1] * YS, 4), round(viz[2], 4), round(viz[3] * YS, 4)],
    "art": [round(art[0], 4), round(art[1] * YS, 4), round(art[2], 4), round(art[3] * YS, 4)],
    "knob": knob,
    "knob2": knob2,
    "seek": seek_m,
    "shuffle": shuf_m,
    "buttons": btn_meta,
    "lights": lights,
    "emissiveCoverage": round(float(mask.mean()), 5),
}

# ---- guard against mainline regions.json drift (2026-07-10 incident) ----------
# assets-diablo-gothic/regions.json is a LIVE, concurrently-edited mainline file (other
# gen12 sessions regen it independently of pbrtest3). Discovered while fixing the knob:
# a plain re-run of this script silently shifted seek/shuffle/viz/art/buttons to a
# DIFFERENT regions.json snapshot than the one that produced the last verified-good
# diablo-meta3.json — same failure class as [[human-labeled-data-rule]] (silently
# clobbering good data with a stale/moving external source). Only 'knob'/'knob2' are
# immune (detected straight from the paint, no regions.json dependency). For every other
# regions.json-derived field, keep the ON-DISK value unless FORCE_REGEN=1 is set —
# re-deriving those fields for real needs a deliberate, verified re-cut, not an
# incidental side effect of running this script for something else.
import os
PINNED_KEYS = ["viz", "art", "seek", "shuffle", "buttons", "glassFill", "glassRects"]
old_path = HERE / "diablo-meta3.json"
if old_path.exists() and not os.environ.get("FORCE_REGEN"):
    old = json.load(open(old_path))
    for k in PINNED_KEYS:
        if k in old and meta.get(k) != old[k]:
            print(f"guard: '{k}' drifted from the on-disk value (regions.json moved under us) "
                  "— keeping the pinned on-disk value. Set FORCE_REGEN=1 to accept a real re-cut.")
            meta[k] = old[k]

json.dump(meta, open(HERE / "diablo-meta3.json", "w"), indent=1)
print("lights:")
for L in lights:
    print("  ", L)
print("meta3 written; sprites:", sk.size, so.size, sn.size)
