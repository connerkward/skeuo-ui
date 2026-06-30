#!/usr/bin/env python3
"""Shape-congruence validity gate for generated sprite-sheets.

A sheet is VALID only if every interactive control's painted shape obeys its
kind, and (for SPRITE controls) the device WELL shape matches the STRIP SPRITE
shape. Encodes the user's rule:
  - knob   -> must be a CIRCLE (rotary).
  - slider -> must be a LINE / ARC channel (straight or curved).
  - button/switch -> ARBITRARY shape, BUT the well it seats in must MATCH the
                     sprite's shape (round sprite in a square slot = FAIL).

This is NOT the rejected open-ended localization: the control rect + kind are
known, so we only CLASSIFY the painted shape inside the known rect (circle vs
rect/square vs line/arc) and compare. Coarse + robust where localization was not.

Operates on a COMBINED paint (device on top devFrac, sprite strip below) + its
template.json. For each control:
  device-well shape  = segment the painted recess/control at its device rect.
  strip-sprite shape = (sprite controls only) the matching blob in the strip.

Run:  python shape.py <paint.png> <template.json> [--overlay OUT.png] [--json]
"""
import sys, os, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from scipy import ndimage

# ---- device / strip split (mirrors blueprint.ts) -----------------------------
GEN_W, GEN_H, PAINT_ASPECT = 1024, 1536, 0.5625
COMBINED_H = round(GEN_W / PAINT_ASPECT)              # 1820
MIN_STRIP_H = round(COMBINED_H * 0.14)                # 255
DEVICE_H = min(GEN_H, COMBINED_H - MIN_STRIP_H)       # 1536
DEVICE_FRAC = DEVICE_H / COMBINED_H                   # 0.844

INTERACTIVE = {"button", "knob", "toggle",
               "slider-h", "slider-v", "slider-arc", "slider-path", "segmented", "xy"}

def sprite_kind(kind):
    if kind == "knob": return "knob"
    if kind == "toggle": return "toggle"
    if kind == "button": return "button"
    if kind in ("slider-h", "slider-v", "slider-arc", "slider-path"): return "slider"
    return None

# ---- shape classification ----------------------------------------------------
# Given a binary mask of the painted control, classify its silhouette.
def shape_descriptors(mask):
    ys, xs = np.where(mask)
    if len(xs) < 12:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    bw, bh = (x1 - x0 + 1), (y1 - y0 + 1)
    area = float(mask.sum())
    bbox_area = float(bw * bh)
    extent = area / bbox_area                       # circle~0.785, square~0.95+
    aspect = bw / bh                                # >1 wide, <1 tall
    # radial CoV: std/mean of boundary-point distance to centroid. Rotation-invariant
    # and robust (unlike pixel-perimeter circularity). circle ~0.00-0.05, square ~0.10-0.18,
    # rounded-square ~0.06-0.10, bar/blob high. This is the reliable circle discriminator.
    er = ndimage.binary_erosion(mask)
    by, bx = np.where(mask ^ er)
    cy, cx = ys.mean(), xs.mean()
    r = np.sqrt((bx - cx) ** 2 + (by - cy) ** 2)
    radial_cov = float(r.std() / (r.mean() + 1e-6)) if len(r) > 8 else 1.0
    return dict(extent=round(extent, 3), aspect=round(aspect, 3),
                radial_cov=round(radial_cov, 3),
                bw=int(bw), bh=int(bh), area=int(area))

def classify(d):
    """-> 'circle' | 'rect' | 'line' | 'blob'."""
    if d is None:
        return "none"
    a = d["aspect"]; ext = d["extent"]
    if a >= 2.2 or a <= 0.45:
        return "line"                               # elongated bar (arc handled by kind)
    near_sq = 0.7 <= a <= 1.43                       # roughly equilateral bbox
    # extent is the robust circle/rect discriminator: a disc fills pi/4=0.785 of its
    # bbox, a (rounded) square fills ~0.90-1.0. radial_cov (boundary roughness) is
    # kept in the descriptors for display but not gated — it's noise-sensitive.
    if near_sq and 0.66 <= ext <= 0.865:
        return "circle"
    if ext >= 0.865:
        return "rect"
    return "blob"

# ---- segmentation ------------------------------------------------------------
# Foreground = pixels inside the rect that DIFFER from the surrounding body plate.
# Body colour = median of a thin ring just OUTSIDE the rect. The control (dark
# recessed well OR beveled baked control) differs from that flat plate; take the
# connected component covering the rect centre.
def segment_control(rgb, box, pad=0.18):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    px, py = int(w * pad), int(h * pad)
    cx0, cy0 = max(0, x0 - px), max(0, y0 - py)
    cx1, cy1 = min(rgb.shape[1], x1 + px), min(rgb.shape[0], y1 + py)
    patch = rgb[cy0:cy1, cx0:cx1].astype(np.float32)
    ph, pw = patch.shape[:2]
    if ph < 6 or pw < 6:
        return None, (cx0, cy0, cx1, cy1)
    # body colour from the outer ring (the pad border region)
    ring = np.ones((ph, pw), bool)
    iy0, ix0 = int(py * 0.6), int(px * 0.6)
    ring[iy0:ph - iy0, ix0:pw - ix0] = False
    body = np.median(patch[ring], axis=0) if ring.sum() > 20 else np.median(patch.reshape(-1, 3), axis=0)
    dist = np.sqrt(((patch - body) ** 2).sum(axis=2))
    thr = max(28.0, np.percentile(dist, 60))        # adaptive
    fg = dist > thr
    fg = ndimage.binary_closing(fg, iterations=2)
    fg = ndimage.binary_opening(fg, iterations=1)
    lab, n = ndimage.label(fg)
    if n == 0:
        return None, (cx0, cy0, cx1, cy1)
    # component nearest patch centre with decent area
    ccx, ccy = pw / 2, ph / 2
    best, bestscore = None, -1
    for i in range(1, n + 1):
        comp = lab == i
        a = comp.sum()
        if a < 0.04 * ph * pw:
            continue
        yy, xx = np.where(comp)
        d = math.hypot(xx.mean() - ccx, yy.mean() - ccy)
        score = a - d * d * 4
        if score > bestscore:
            bestscore, best = score, comp
    if best is None:
        return None, (cx0, cy0, cx1, cy1)
    return best, (cx0, cy0, cx1, cy1)

# ---- strip sprite extraction -------------------------------------------------
def strip_sprites(rgb, dev_frac):
    H, W = rgb.shape[:2]
    sy = int(dev_frac * H)
    strip = rgb[sy:H].astype(np.float32)
    # non-white blobs (white strip background)
    nonwhite = strip.min(axis=2) < 225
    nonwhite = ndimage.binary_closing(nonwhite, iterations=2)
    lab, n = ndimage.label(nonwhite)
    blobs = []
    sh, sw = strip.shape[:2]
    for i in range(1, n + 1):
        comp = lab == i
        if comp.sum() < 0.01 * sh * sw:
            continue
        yy, xx = np.where(comp)
        blobs.append(dict(mask=comp, cx=xx.mean(),
                          box=(xx.min(), yy.min() + sy, xx.max(), yy.max() + sy)))
    blobs.sort(key=lambda b: b["cx"])
    return blobs, sy

# ---- per-skin grade ----------------------------------------------------------
# ---- sprite COMPONENT silhouette ---------------------------------------------
# Prefer the REAL stored cut sprite (<base>-sprite-<bind>.png — the shipped artifact).
# Else recut from the real strip cellRect in <base>-layout.json (the actual cell the
# pipeline cuts, not a blob guess): near-white key -> largest central component.
def sprite_from_png(path):
    a = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
    return a > 40, Image.open(path).convert("RGBA")

def sprite_from_cell(rgb, cellrect, W, H):
    x0, y0 = int(cellrect[0] * W), int(cellrect[1] * H)
    x1, y1 = int((cellrect[0] + cellrect[2]) * W), int((cellrect[1] + cellrect[3]) * H)
    patch = rgb[y0:y1, x0:x1]
    if patch.shape[0] < 6 or patch.shape[1] < 6:
        return None, None
    nonwhite = ndimage.binary_closing(patch.min(axis=2) < 225, iterations=2)
    lab, n = ndimage.label(nonwhite)
    if n == 0:
        return None, None
    ph, pw = patch.shape[:2]; ccx, ccy = pw / 2, ph / 2
    best, bs = None, -1
    for i in range(1, n + 1):
        comp = lab == i; a = comp.sum()
        if a < 0.03 * ph * pw:
            continue
        yy, xx = np.where(comp); s = a - math.hypot(xx.mean() - ccx, yy.mean() - ccy) ** 2 * 4
        if s > bs:
            bs, best = s, comp
    if best is None:
        return None, None
    return best, Image.fromarray(np.dstack([patch, (best * 255).astype(np.uint8)]))

def grade(paint_path, template_path, save_sprite_dir=None):
    tpl = json.load(open(template_path))
    im = Image.open(paint_path).convert("RGB")
    W, H = im.size
    rgb = np.asarray(im)
    DH = DEVICE_FRAC * H
    base = paint_path[:-len("-paint.png")] if paint_path.endswith("-paint.png") else paint_path

    layout = None
    cand = base + "-layout.json"
    if os.path.exists(cand):
        layout = json.load(open(cand))

    controls = [r for r in tpl["regions"] if r.get("kind") in INTERACTIVE]
    sprite_ctrls = [r for r in controls if sprite_kind(r["kind"]) and not r.get("baked")]
    # pair each template sprite-control (in order) with the real layout control + cell
    pairing = {}
    if layout and len(layout.get("controls", [])) == len(sprite_ctrls) == len(layout.get("cells", [])):
        for r, lc, cell in zip(sprite_ctrls, layout["controls"], layout["cells"]):
            pairing[r["id"]] = dict(cellbind=cell["bind"], cellrect=cell["cellRect"], devrect=lc["rect"])

    out = []
    for r in controls:
        rc = r["rect"]; kind = r["kind"]; sk = sprite_kind(kind); baked = bool(r.get("baked"))
        pr = pairing.get(r["id"])
        drect = pr["devrect"] if pr else (rc["x"], rc["y"], rc["w"], rc["h"])  # real layout rect if known
        box = (int(drect[0] * W), int(drect[1] * DH),
               int((drect[0] + drect[2]) * W), int((drect[1] + drect[3]) * DH))
        mask, patchbox = segment_control(rgb, box)
        dev_class = classify(shape_descriptors(mask) if mask is not None else None)
        dev_desc = shape_descriptors(mask) if mask is not None else None
        if sk == "slider":
            ra = (drect[2] * W) / (drect[3] * DH + 1e-6)
            dev_class = "arc" if kind in ("slider-arc", "slider-path") else ("line" if (ra >= 2.0 or ra <= 0.5) else dev_class)

        # ---- the REAL sprite COMPONENT (stored artifact, else recut from real cell) ----
        spr_class = spr_src = spr_thumb = None
        if sk and not baked and pr:
            stored = f"{base}-sprite-{pr['cellbind']}.png"
            if os.path.exists(stored):
                smask, simg = sprite_from_png(stored); spr_src = "stored"
            else:
                smask, simg = sprite_from_cell(rgb, pr["cellrect"], W, H); spr_src = "recut"
            if smask is not None:
                spr_class = classify(shape_descriptors(smask))
                if save_sprite_dir and simg is not None:
                    spr_thumb = f"{tpl.get('id')}__{r['id']}.png"
                    simg.save(os.path.join(save_sprite_dir, spr_thumb))

        # ---- per-kind gate, now CROSS-CHECKED against the component ----
        ok = True; reason = ""
        if kind == "knob":
            if dev_class != "circle":
                ok = False; reason = f"knob well is '{dev_class}', must be circle"
            elif spr_class == "rect":
                ok = False; reason = "knob component is 'rect', must be circle"
            elif spr_class:
                reason = f"well+component both round ({spr_src})"
        elif sk == "slider":
            if dev_class not in ("line", "arc"):
                ok = False; reason = f"slider well is '{dev_class}', must be line/arc"
            elif spr_class:
                reason = f"track {dev_class}; component present ({spr_src})"
        elif kind in ("button", "toggle"):
            if baked:
                reason = "baked (arbitrary shape allowed)"
            elif not pr:
                reason = "no stored component / layout — unverified"
            elif spr_class and dev_class not in ("none", "blob") and spr_class != dev_class:
                ok = False; reason = f"component '{spr_class}' != well '{dev_class}' shape mismatch ({spr_src})"
            else:
                reason = f"component matches well: {dev_class} ({spr_src})"
        out.append(dict(id=r["id"], bind=r.get("bind", r["id"]), kind=kind, baked=baked,
                        dev_class=dev_class, sprite_class=spr_class, sprite_src=spr_src,
                        sprite_thumb=spr_thumb, ok=ok, reason=reason, dev=dev_desc,
                        box=box, patchbox=patchbox, mask=mask))
    valid = all(c["ok"] for c in out)
    return dict(id=tpl.get("id"), valid=valid, has_layout=bool(layout),
                n_sprite_ctrls=len(sprite_ctrls),
                n_stored=sum(1 for c in out if c["sprite_src"] == "stored"),
                n_recut=sum(1 for c in out if c["sprite_src"] == "recut"),
                controls=out)

# ---- overlay -----------------------------------------------------------------
def _font(sz):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/SFNSDisplay.ttf"):
        try: return ImageFont.truetype(p, sz)
        except: pass
    return ImageFont.load_default()

def overlay(paint_path, res, out_path):
    im = Image.open(paint_path).convert("RGB")
    W, H = im.size
    dev = im.crop((0, 0, W, int(DEVICE_FRAC * H))).copy()
    d = ImageDraw.Draw(dev, "RGBA")
    f = _font(max(20, W // 60)); fs = _font(max(16, W // 78))
    for c in res["controls"]:
        x0, y0, x1, y1 = c["box"]
        col = (60, 220, 90) if c["ok"] else (255, 50, 90)
        # draw segmented silhouette
        if c["mask"] is not None:
            px0, py0, _, _ = c["patchbox"]
            m = c["mask"]
            edge = m ^ ndimage.binary_erosion(m)
            yy, xx = np.where(edge)
            for X, Y in zip(xx[::3], yy[::3]):
                d.point((px0 + X, py0 + Y), fill=col + (255,))
        d.rectangle([x0, y0, x1, y1], outline=col + (255,), width=5)
        lbl = f'{c["bind"]}·{c["kind"]}'
        sub = f'well:{c["dev_class"]}' + (f' sprite:{c["sprite_class"]}' if c["sprite_class"] else (' baked' if c["baked"] else ''))
        mark = "OK" if c["ok"] else "FAIL"
        d.rectangle([x0, y0 - 46, x0 + max(f.getlength(lbl), fs.getlength(sub)) + 16, y0], fill=(0, 0, 0, 200))
        d.text((x0 + 6, y0 - 44), lbl, fill=col + (255,), font=fs)
        d.text((x0 + 6, y0 - 26), f'{mark} {sub}', fill=(255, 255, 255, 255), font=fs)
    # header
    badge = "VALID" if res["valid"] else "INVALID"
    bcol = (60, 200, 90) if res["valid"] else (255, 60, 90)
    d.rectangle([0, 0, W, 54], fill=(0, 0, 0, 210))
    d.text((14, 12), f'{res["id"]}   {badge}', fill=bcol + (255,), font=f)
    dev.save(out_path)
    return out_path

def _clean(res):
    cs = []
    for c in res["controls"]:
        c = dict(c); c.pop("mask"); cs.append(c)
    r = dict(res); r["controls"] = cs; return r

if __name__ == "__main__":
    a = sys.argv
    paint, tpl = a[1], a[2]
    res = grade(paint, tpl)
    if "--overlay" in a:
        overlay(paint, res, a[a.index("--overlay") + 1])
    if "--json" in a or "--overlay" not in a:
        print(json.dumps(_clean(res), indent=2, default=str))
