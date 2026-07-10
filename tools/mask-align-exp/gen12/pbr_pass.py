#!/usr/bin/env python3
"""pbr_pass — per-skin PBR/emissive pass for the gen12 mainline (pbrtest3 promoted).

For one skin (assets-<id>/) this produces assets-<id>_pbr/ with everything the PBR-lit
player (build_player_pbr.py) needs:

  basecolor/normal/roughness/metalness/height .png   fal-ai/patina, ONE call = all 5 maps,
                                                     $0.01/MP (input downscaled to <=PATINA_MP)
  emissive.png (RGBA)      glyph-shaped emissive — chroma x luminance gated by two-scale
                           morphological TOP-HAT (only thin locally-bright features survive)
                           + erode + component-area cap. Hue window comes from the DIRECTOR:
                           theme spec "lighting.emissive_color" ([r,g,b] bias or "auto").
  glass.png                full-frame feathered glass mask (viz + album-art panes) for the
                           shader's fresnel/env path.
  viz-mask.png/art-mask.png  PAINT-DERIVED per-region glass masks: the actual dark-glass
                           interior shape (adaptive dark-CC relative to local body level,
                           largest CC, closing, erode inside the bezel lip, slight feather).
                           Used as the visualizer/art canvas CLIP and as the emissive-source
                           shape in the player registry — bars can never cross the bezel.
                           Generic for any pane shape (rounded rects, arches, portholes).
  btn-ids.png              L-mode button-silhouette id mask (idx+1)*36, drift-corrected.
  meta.json                knob seat, seek travel, shuffle rect+stateAlign, button rects+ids,
                           viz/art rects + mask rects, emissive point lights, glassFill,
                           the spec's lighting section, cost + model annotations, src hash.

FEATURE FLAG — the pass is gated at BOTH ends (feature-flag-rule):
  * pipeline: PBR_PASS_ENABLED below gates the wire-in hook (orchestrate12 checks it; see
    WIRE-pbr.md). Default False: experimental features ship OFF until proven — flipping it
    on adds ~$0.02-0.03/skin patina spend per generation. Running this script DIRECTLY is
    an explicit opt-in and ignores the flag.
  * per-spec: "lighting": {"enabled": false} in a theme spec skips the pass entirely for
    that skin (no patina call, no extraction, no player build) even when run directly.
  * player/UI: the PBR player is a separate player-pbr.html the user opts into from the
    plain player / dashboard (default remains player.html).

All coords in meta.json are SRC-UV (x / W, y / srcH) where src = the device slice
(top devFrac rows of paint.png) — same convention as pbrtest3.

Usage: python3 pbr_pass.py <assets-dir> [--force] [--no-patina]
"""
import hashlib
import json
import os
import re
import sys
import time

import numpy as np
import requests
from PIL import Image, ImageFilter
from scipy import ndimage

PBR_PASS_ENABLED = False  # pipeline wire-in gate (see WIRE-pbr.md). OFF until the pass is
                          # proven across the roster: it adds hosted spend (~$0.02-0.03/skin
                          # patina) + ~1min/skin to every orchestrate roll. Direct CLI runs
                          # of this script are explicit opt-ins and ignore this flag.

PATINA_MODEL = "fal-ai/patina"
PATINA_MP = 1.6           # downscale patina input to <= this many megapixels (cost control)
PATINA_USD_PER_MP = 0.01
MAPS = ["basecolor", "normal", "roughness", "metalness", "height"]

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
SID = os.path.basename(OUT).replace("assets-", "")
PBR = os.path.join(HERE, f"assets-{SID}_pbr")
BIREF = os.path.join(HERE, f"assets-{SID}_biref")
FORCE = "--force" in sys.argv


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def load_fal():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    sys.exit("no FAL_KEY")


# ---------------------------------------------------------------- inputs
R = json.load(open(os.path.join(OUT, "regions.json")))
RES = json.load(open(os.path.join(OUT, "results.json")))
regs, keys = R["regions"], R["keys"]
DF = R["devFrac"]

# lighting: prefer the passthrough in results.json (genskin hook), else the spec itself
spec_path = os.path.join(HERE, "theme_specs", f"{SID}.json")
lighting = RES.get("lighting") or {}
if not lighting and os.path.exists(spec_path):
    lighting = json.load(open(spec_path)).get("lighting", {})
lighting = {"emissive_hint": "", "emissive_color": "auto", "pulse": "breathe",
            "intensity": 0.8, "viz_emissive": True, "beat_couple": 0.05,
            "enabled": True, **lighting}
if not lighting.get("enabled", True):
    print(f"[pbr:{SID}] lighting.enabled=false in spec — pass skipped (no cost, no output)")
    sys.exit(0)

paint = Image.open(os.path.join(OUT, "paint.png")).convert("RGB")
PW, PH = paint.size
SRC_H = round(PH * DF)
YS = PH / SRC_H                              # paint-frac-y -> src-frac-y
src_im = paint.crop((0, 0, PW, SRC_H))
W, H = src_im.size
src = np.asarray(src_im, np.float32) / 255.0
paint_sha = hashlib.sha1(open(os.path.join(OUT, "paint.png"), "rb").read()).hexdigest()[:12]
os.makedirs(PBR, exist_ok=True)

meta_path = os.path.join(PBR, "meta.json")
prev = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
if prev.get("src", {}).get("sha1") == paint_sha and not FORCE:
    print(f"[pbr:{SID}] up to date (paint sha {paint_sha}) — use --force to redo")
    sys.exit(0)

# ---------------------------------------------------------------- 1. patina maps (one call)
patina_cost = 0.0
have_maps = all(os.path.exists(os.path.join(PBR, f"{m}.png")) for m in MAPS)
maps_fresh = have_maps and prev.get("src", {}).get("sha1") == paint_sha
if "--no-patina" in sys.argv or maps_fresh:
    print(f"[pbr:{SID}] patina maps {'reused (fresh)' if maps_fresh else 'SKIPPED (--no-patina)'}")
else:
    FAL = load_fal()
    scale = min(1.0, (PATINA_MP * 1e6 / (W * H)) ** 0.5)
    ds = src_im.resize((round(W * scale), round(H * scale)), Image.LANCZOS)
    mp = ds.width * ds.height / 1e6
    patina_cost = round(mp * PATINA_USD_PER_MP, 4)
    tmp = os.path.join(PBR, "_patina_in.png")
    ds.save(tmp)
    init = requests.post("https://rest.alpha.fal.ai/storage/upload/initiate",
                         headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
                         json={"file_name": f"{SID}-src.png", "content_type": "image/png"}).json()
    requests.put(init["upload_url"], headers={"Content-Type": "image/png"}, data=open(tmp, "rb").read())
    os.remove(tmp)
    print(f"[pbr:{SID}] patina: {ds.width}x{ds.height} ({mp:.2f}MP, ~${patina_cost}) …", flush=True)
    job = requests.post(f"https://queue.fal.run/{PATINA_MODEL}",
                        headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
                        json={"image_url": init["file_url"], "maps": MAPS, "output_format": "png"}).json()
    t0 = time.time()
    while True:
        s = requests.get(job["status_url"], headers={"Authorization": f"Key {FAL}"}).json().get("status")
        if s == "COMPLETED":
            break
        if s in ("FAILED", "ERROR") or time.time() - t0 > 420:
            raise RuntimeError(f"patina {s}")
        time.sleep(3)
    r = requests.get(job["response_url"], headers={"Authorization": f"Key {FAL}"}).json()
    imgs = r["images"]
    for i, m in enumerate(MAPS):
        # map by file_name when present, else by request order
        pick = next((im for im in imgs if m in (im.get("file_name") or im.get("url", ""))), None) \
            or (imgs[i] if i < len(imgs) else None)
        if pick is None:
            raise RuntimeError(f"patina returned no '{m}' map: {imgs}")
        open(os.path.join(PBR, f"{m}.png"), "wb").write(requests.get(pick["url"]).content)
    print(f"[pbr:{SID}] patina maps saved ({time.time()-t0:.0f}s)")

# ---------------------------------------------------------------- 2. glyph emissive (local, $0)
mx = src.max(axis=-1)
mn = src.min(axis=-1)
val = mx
sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
r_, g_, b_ = src[..., 0], src[..., 1], src[..., 2]
d = np.maximum(mx - mn, 1e-6)
hue = np.zeros((H, W), np.float32)
m = mx == r_
hue[m] = (60 * ((g_ - b_) / d) % 360)[m]
m = mx == g_
hue[m] = (60 * ((b_ - r_) / d) + 120)[m]
m = mx == b_
hue[m] = (60 * ((r_ - g_) / d) + 240)[m]

K1 = max(9, int(31 * W / 2304) | 1)          # stroke-scale top-hat kernel
K2 = max(19, int(61 * W / 2304) | 1)         # crack-scale


def tophat_gate(score):
    th1 = score - ndimage.grey_opening(score, size=(K1, K1))
    th2 = score - ndimage.grey_opening(score, size=(K2, K2))
    return score * smoothstep(0.10, 0.35, np.maximum(th1, 0.75 * th2))


def hue_window(hc, half):
    dd = np.abs(((hue - hc + 180) % 360) - 180)
    return smoothstep(half, half * 0.55, dd)   # 1 inside, feathered edge


# RELATIVE/LOCAL gating, not an absolute sat/val threshold. An absolute threshold saturates on
# any material whose OWN base colour is already bright+saturated (a translucent aqua/teal shell,
# a vivid lacquer) — every micro-specular glint on that material passes the same gate a genuine
# glyph would, producing scattered "splatter" across the whole body (measured 2026-07-10,
# fa-pod: 502590 candidate px, coverage 0.036 vs diablo-gothic's 0.023 on a much duller body).
# Fix: gate on how much a pixel EXCEEDS its own local neighbourhood's sat/val baseline (a
# material-scale morphological opening, coarser than the stroke/crack top-hat below) — a
# uniformly bright/saturated material has near-zero local excess everywhere (baseline == value),
# while a genuine glyph/rune is measurably brighter+more-saturated than the duller material
# immediately around it. Material-agnostic: no hue special-case, no absolute constant.
K3 = max(41, int(101 * W / 2304) | 1)                    # material-scale kernel (> K2, the crack scale)
sat_base = ndimage.grey_opening(sat, size=(K3, K3))
val_base = ndimage.grey_opening(val, size=(K3, K3))
sat_excess = np.clip(sat - sat_base, 0, 1)
val_excess = np.clip(val - val_base, 0, 1)
score_nh = smoothstep(0.30, 0.55, sat_excess) * smoothstep(0.22, 0.42, val_excess)
emc = lighting["emissive_color"]
if isinstance(emc, (list, tuple)):
    cr, cg, cb = [c / 255 for c in emc]
    cmx, cmn = max(cr, cg, cb), min(cr, cg, cb)
    dd_ = max(cmx - cmn, 1e-6)
    hc = (60 * ((cg - cb) / dd_) % 360) if cmx == cr else \
         (60 * ((cb - cr) / dd_) + 120) if cmx == cg else (60 * ((cr - cg) / dd_) + 240)
    hue_used = {"mode": "director", "center": round(float(hc), 1), "half_width": 45}
    hmask = hue_window(hc, 45)
else:                                        # "auto": dominant hue of thin bright features
    cand = tophat_gate(score_nh) > 0.30
    if cand.sum() >= 400:
        hist, _ = np.histogram(hue[cand], bins=36, range=(0, 360), weights=score_nh[cand])
        k = np.array([0.25, 0.5, 1, 0.5, 0.25])
        hist = np.convolve(np.r_[hist[-2:], hist, hist[:2]], k, "same")[2:-2]
        hc = float(np.argmax(hist) * 10 + 5)
        hue_used = {"mode": "auto", "center": hc, "half_width": 40, "px": int(cand.sum())}
        hmask = hue_window(hc, 40)
    else:
        hue_used = {"mode": "auto", "center": None, "px": int(cand.sum())}
        hmask = np.zeros((H, W), np.float32)   # nothing emits

glow = tophat_gate(score_nh * hmask)
glow = np.asarray(to_img(glow).filter(ImageFilter.MinFilter(3)), np.float32) / 255

# component-area cap at 1/4 res (kills broad splatter + dust) — scipy CC, not the slow loop
ds4 = 4
small = glow[::ds4, ::ds4] > 0.25
lab, nlab = ndimage.label(small, structure=np.ones((3, 3)))
kept = []
if nlab:
    areas = ndimage.sum_labels(np.ones_like(small, np.int32), lab, index=np.arange(1, nlab + 1))
    A_MAX = 5200 * (W / 2304) ** 2
    ok = (areas >= 4) & (areas <= A_MAX)
    # RING/RIM rejector — a polished metal bezel rim reads as a thin bright warm outline and
    # passes every pixel gate (steam-porthole: the viz window's brass rim became a glowing
    # rectangle). Shape separates them cleanly (measured 2026-07-09): legit glyphs/cracks
    # fill 0.30-0.57 of their bbox at <=0.3% of the image; the rim ring filled 0.074 of a
    # 5.9%-of-image bbox. Kill large hollow components.
    for i, sl_ in enumerate(ndimage.find_objects(lab)):
        if sl_ is None or not ok[i]:
            continue
        bb = (sl_[0].stop - sl_[0].start) * (sl_[1].stop - sl_[1].start)
        if bb > 0.01 * small.size and areas[i] / bb < 0.15:
            ok[i] = False
    bad = np.isin(lab, np.where(~ok)[0] + 1)
    glow[np.kron(bad, np.ones((ds4, ds4), bool))[:H, :W]] = 0
    kept = [i + 1 for i in np.where(ok)[0]]

fe = to_img(glow).filter(ImageFilter.GaussianBlur(1.6))
emask = smoothstep(0.18, 0.60, np.asarray(fe, np.float32) / 255)
em = src / np.maximum(val[..., None], 0.30)
core = smoothstep(0.75, 1.0, emask * val)[..., None]
em = np.clip(em + core * np.array([0.9, 0.55, 0.30]), 0, 1)
Image.fromarray(np.dstack([(em * 255).astype(np.uint8), (emask * 255).astype(np.uint8)]),
                "RGBA").save(os.path.join(PBR, "emissive.png"))
cov = float(emask.mean())
print(f"[pbr:{SID}] emissive coverage {cov:.5f}, {len(kept)} components, hue {hue_used}")

# point lights from the kept clusters (energy-weighted centroids, top 6)
lights = []
if kept:
    en = emask * val
    en4 = en[::ds4, ::ds4]
    esum = ndimage.sum_labels(en4, lab, index=kept)
    order = np.argsort(-esum)[:6]
    tot = float(esum.sum()) or 1.0
    cyx = ndimage.center_of_mass(en4, lab, index=[kept[i] for i in order])
    for oi, (cy, cx) in zip(order, cyx):
        if esum[oi] <= 0:
            continue
        ys, xs = np.where(lab == kept[oi])
        col = em[np.clip(ys * ds4, 0, H - 1), np.clip(xs * ds4, 0, W - 1)].mean(axis=0)
        lights.append({"uv": [round(cx * ds4 / W, 4), round(cy * ds4 / H, 4)],
                       "color": [round(float(c), 3) for c in col],
                       "energy": round(float(esum[oi]) / tot, 3)})

# ---------------------------------------------------------------- 3. paint-derived glass masks
paintg = np.asarray(src_im.convert("L"), np.float32)


def _inset_rrect(shape, inset=0.04):
    """Sane fallback pane shape: the region rect inset a little, with rounded corners."""
    hh, ww = shape
    ix, iy = int(ww * inset), int(hh * inset)
    pad_frac = 0.12 / (1 + 2 * 0.12)           # the crop's pad band
    px, py = int(ww * pad_frac), int(hh * pad_frac)
    m = Image.new("L", (ww, hh), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(m).rounded_rectangle(
        [px + ix, py + iy, ww - px - ix, hh - py - iy],
        radius=max(4, int(min(ww, hh) * 0.08)), fill=255)
    return m


def region_glass_mask(b_paint):
    """Extract the glass-pane interior SHAPE inside display rect b (paint fracs), so the
    visualizer/album-art content (and its emissive source) is CLIPPED to the actual painted
    glass — bars can never cross the bezel. Generic for any pane shape (rounded rects,
    arches, portholes) and any glass TONE (dark CRT, teal, amber): seeded COLOR-SIMILARITY
    region-grow from the rect centre (not a dark-only threshold — a dark-CC misses teal
    glass, see steam-porthole), closing to swallow glints/painted content, fill holes,
    erode so the mask sits INSIDE the bezel lip, slight feather. If the grown CC is
    implausible (<35% or >99.5% of the rect) fall back to an inset rounded-rect of the
    refit rect — never worse than the rect the plain player uses.
    Returns (mask_img L, crop rect [x,y,w,h] in src-uv) or (None, None)."""
    pad = 0.12
    x0 = max(0, int((b_paint[0] - b_paint[2] * pad) * PW))
    x1 = min(W, int((b_paint[0] + b_paint[2] * (1 + pad)) * PW))
    y0 = max(0, int((b_paint[1] - b_paint[3] * pad) * PH))
    y1 = min(H, int((b_paint[1] + b_paint[3] * (1 + pad)) * PH))
    win = src[y0:y1, x0:x1]                    # float rgb 0..1
    if win.size < 1200:
        return None, None
    hh, ww = win.shape[:2]
    # seed: central 30% of the pane — its colour distribution defines "glass"
    sy0, sy1 = int(hh * 0.35), int(hh * 0.65)
    sx0, sx1 = int(ww * 0.35), int(ww * 0.65)
    seed = win[sy0:sy1, sx0:sx1].reshape(-1, 3)
    med = np.median(seed, axis=0)
    sig = float(np.percentile(np.abs(seed - med).max(axis=1), 90))
    tol = max(0.10, min(0.30, sig * 2.2))
    sim = np.abs(win - med).max(axis=-1) < tol
    k = max(3, int(min(hh, ww) * 0.04) | 1)
    sim = ndimage.binary_closing(sim, structure=np.ones((k, k)))   # swallow glints/content
    sim = ndimage.binary_fill_holes(sim)
    lab2, n2 = ndimage.label(sim)
    keep = None
    if n2:
        cid = lab2[hh // 2, ww // 2]
        if cid == 0:                            # centre not similar? take largest CC
            areas2 = ndimage.sum_labels(np.ones_like(sim, np.int32), lab2, np.arange(1, n2 + 1))
            cid = int(np.argmax(areas2)) + 1
        keep = lab2 == cid
        er = max(2, int(min(hh, ww) * 0.015))
        keep = ndimage.binary_erosion(keep, iterations=er)          # inside the bezel lip
        rect_area = (ww / (1 + 2 * pad)) * (hh / (1 + 2 * pad))
        frac = keep.sum() / max(1.0, rect_area)
        if frac < 0.35 or frac > 0.995:
            keep = None                          # implausible grow — fall back
    mimg = (to_img(keep.astype(np.float32)).filter(ImageFilter.GaussianBlur(1.5))
            if keep is not None else _inset_rrect((hh, ww)))
    rect = [x0 / PW, y0 / PH * YS, (x1 - x0) / PW, (y1 - y0) / PH * YS]
    return mimg, rect


glass_full = Image.new("L", (W // 2, H // 2), 0)
region_meta = {}
for rname, fname in (("visualizer", "viz-mask.png"), ("album_art", "art-mask.png")):
    reg = regs.get(rname)
    if not reg or not reg.get("device"):
        continue
    b = reg.get("regionRefit", {}).get("rect") or reg["device"]
    mimg, mrect = region_glass_mask(reg["device"])
    if mimg is None:
        continue
    mimg.save(os.path.join(PBR, fname))
    gx = int(mrect[0] * W / 2)
    gy = int(mrect[1] / YS * PH / 2)
    gm = mimg.resize((max(1, int(mrect[2] * W / 2)), max(1, int(mrect[3] / YS * PH / 2))))
    glass_full.paste(gm, (gx, gy), gm)
    region_meta[rname] = {
        "rect": [round(b[0], 4), round(b[1] * YS, 4), round(b[2], 4), round(b[3] * YS, 4)],
        "mask": fname, "maskRect": [round(v, 4) for v in mrect]}
glass_full = glass_full.filter(ImageFilter.GaussianBlur(2))
glass_full.save(os.path.join(PBR, "glass.png"))

# glassFill = mean of the darkest half of the glass interiors (the pane's own tone)
gvals = []
for rname in region_meta:
    b = regs[rname]["device"]
    crop = src[int(b[1] * PH):int((b[1] + b[3]) * PH), int(b[0] * PW):int((b[0] + b[2]) * PW)]
    if crop.size:
        lum = crop.mean(axis=-1)
        gvals.append(crop[lum <= np.percentile(lum, 50)].reshape(-1, 3))
glass_fill = [round(float(v), 4) for v in (np.concatenate(gvals).mean(axis=0) if gvals else [0.1, 0.1, 0.12])]

# ---------------------------------------------------------------- 4. button id mask
mask_im = np.asarray(Image.open(os.path.join(OUT, "mask.png")).convert("RGB"), np.int32)
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
    x0 = max(0, int((mb[0] - mb[2] * pad) * MW_)); x1 = min(MW_, int((mb[0] + mb[2] * (1 + pad)) * MW_))
    y0 = max(0, int((mb[1] - mb[3] * pad) * MH_)); y1 = min(MH_, int((mb[1] + mb[3] * (1 + pad)) * MH_))
    hit = ((mask_im[y0:y1, x0:x1] - k) ** 2).sum(axis=-1) < 7000
    dxp = int(round(((db[0] + db[2] / 2) - (mb[0] + mb[2] / 2)) * MW_))
    dyp = int(round(((db[1] + db[3] / 2) - (mb[1] + mb[3] / 2)) * MH_))
    ty0, tx0 = y0 + dyp, x0 + dxp
    hh, ww = hit.shape
    sy0, sx0 = max(0, ty0), max(0, tx0)
    sy1, sx1 = min(H, ty0 + hh), min(W, tx0 + ww)
    if sy1 > sy0 and sx1 > sx0:
        ids[sy0:sy1, sx0:sx1][hit[sy0 - ty0:sy1 - ty0, sx0 - tx0:sx1 - tx0]] = (i + 1) * 36
    btn_meta.append({"name": bname, "id": (i + 1) * 36,
                     "rect": [round(db[0], 4), round(db[1] * YS, 4),
                              round(db[2], 4), round(db[3] * YS, 4)]})
Image.fromarray(ids, "L").save(os.path.join(PBR, "btn-ids.png"))

# ---------------------------------------------------------------- 5. placement meta
def rect_src(b):
    return [round(b[0], 4), round(b[1] * YS, 4), round(b[2], 4), round(b[3] * YS, 4)]


knob = None
vol = regs.get("vol")
if vol and vol.get("seat"):
    s = vol["seat"]
    knob = {"c": [round(s[0], 4), round(s[1] * YS, 4)], "r": round(s[2], 4)}

seek_m = None
seek = regs.get("seek")
if seek and seek.get("device"):
    tk = seek["device"]
    vert = bool(seek.get("vertical"))
    tv = seek.get("travel") or ([tk[1], tk[1] + tk[3]] if vert else [tk[0], tk[0] + tk[2]])
    seek_m = {"track": rect_src(tk), "vertical": vert,
              "travel": [round(tv[0] * (YS if vert else 1), 4), round(tv[1] * (YS if vert else 1), 4)]}

shuf_m = None
shuf = regs.get("shuffle")
if shuf and shuf.get("device"):
    sa = shuf.get("stateAlign") or {}
    shuf_m = {"rect": rect_src(shuf["device"]), "angle": shuf.get("angle", 0),
              "stateAlign": {"dx": sa.get("dx", 0), "dy": sa.get("dy", 0)}}

meta = {
    "id": SID, "size": [W, H], "paintSize": [PW, PH], "devFrac": DF,
    "lighting": lighting,
    "glassFill": glass_fill,
    "regions": region_meta,                      # visualizer / album_art: rect+mask+maskRect
    "knob": knob, "seek": seek_m, "shuffle": shuf_m, "buttons": btn_meta,
    "lights": lights, "emissiveCoverage": round(cov, 5), "emissiveHue": hue_used,
    "cost": {"patina_model": PATINA_MODEL, "patina_usd": patina_cost,
             "paint_model": RES.get("model", ""), "emissive": "classical local $0"},
    "src": {"sha1": paint_sha, "paint_mtime": int(os.path.getmtime(os.path.join(OUT, "paint.png")))},
}
json.dump(meta, open(meta_path, "w"), indent=1)
print(f"[pbr:{SID}] meta written — knob={bool(knob)} seek={bool(seek_m)} shuffle={bool(shuf_m)} "
      f"buttons={len(btn_meta)} regions={list(region_meta)} lights={len(lights)} cost=${patina_cost}")
