#!/usr/bin/env python3
"""pbrtest2 — extract EMISSIVE maps, GLASS masks, and emissive point-light clusters
from the lit paint crops. All local/classical ($0).

Emissive: high-chroma × high-value pixels inside a theme hue window (diablo: warm
ember reds/oranges; vario: any high-chroma — electric blue rim + backlit glyphs),
soft-thresholded, feathered. Output RGBA: RGB = paint colour, A = emissive mask.

Glass: visualizer/album_art rects from the skin's regions.json (device coords are
fractions of paint W/H), inset + feathered into a grayscale "glassiness" mask.

Lights: connected components of the emissive mask (BFS on a downsampled grid),
top-4 by energy → uv centroid, mean colour, relative energy → <skin>-meta.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
GEN12 = HERE.parent

SKINS = {
    "diablo": {
        "asset": "assets-diablo-gothic",
        # warm hue window (degrees), chroma/value knees
        "hue": [(0, 45), (330, 360)],
        "sat_knee": (0.45, 0.65),
        "val_knee": (0.22, 0.45),
        "pulse": "ember",
    },
    "vario": {
        "asset": "assets-wmp-vario",
        "hue": None,  # any hue — blue ring + multicolour backlit glyphs
        "sat_knee": (0.50, 0.72),
        "val_knee": (0.30, 0.55),
        "pulse": "phosphor",
    },
}


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def extract(skin, cfg):
    src = np.asarray(Image.open(HERE / f"{skin}-src.png").convert("RGB"), dtype=np.float32) / 255.0
    H, W = src.shape[:2]
    mx = src.max(axis=-1)
    mn = src.min(axis=-1)
    val = mx
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    # hue in degrees
    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    d = np.maximum(mx - mn, 1e-6)
    hue = np.zeros((H, W), np.float32)
    m = mx == r
    hue[m] = (60 * ((g - b) / d) % 360)[m]
    m = mx == g
    hue[m] = (60 * ((b - r) / d) + 120)[m]
    m = mx == b
    hue[m] = (60 * ((r - g) / d) + 240)[m]

    score = smoothstep(*cfg["sat_knee"], sat) * smoothstep(*cfg["val_knee"], val)
    if cfg["hue"]:
        hmask = np.zeros((H, W), np.float32)
        for h0, h1 in cfg["hue"]:
            hmask = np.maximum(hmask, ((hue >= h0) & (hue <= h1)).astype(np.float32))
        score *= hmask

    # feather: small blur + soft knee
    sc = Image.fromarray((score * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.5))
    mask = np.asarray(sc, np.float32) / 255.0
    mask = smoothstep(0.12, 0.55, mask)

    # emissive RGBA: colour = paint pushed toward its chroma (normalise value a bit)
    em = src / np.maximum(val[..., None], 0.35)
    em = np.clip(em, 0, 1)
    rgba = np.dstack([(em * 255).astype(np.uint8), (mask * 255).astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(HERE / f"{skin}-emissive.png")

    # ---- glass mask from regions.json screen rects ----
    regions = json.load(open(GEN12 / cfg["asset"] / "regions.json"))["regions"]
    paint_h = Image.open(GEN12 / cfg["asset"] / "paint.png").height
    gm = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(gm)
    glass_px = []
    for key in ("visualizer", "album_art"):
        if key not in regions or not regions[key].get("device"):
            continue
        x, y, w, h = regions[key]["device"]
        px = [x * W, y * paint_h, (x + w) * W, (y + h) * paint_h]
        inset = 0.06 * min(px[2] - px[0], px[3] - px[1])
        box = [px[0] + inset, px[1] + inset, px[2] - inset, px[3] - inset]
        rad = 0.12 * min(box[2] - box[0], box[3] - box[1])
        dr.rounded_rectangle(box, radius=rad, fill=255)
        glass_px.append([int(v) for v in box])
    gm = gm.filter(ImageFilter.GaussianBlur(9))
    gm.save(HERE / f"{skin}-glass.png")
    gmask = np.asarray(gm, np.float32) / 255.0

    # glass fill colour: 20th percentile of pixels inside glass (dark clean tone)
    if gmask.max() > 0:
        sel = src[gmask > 0.6]
        gfill = [float(np.percentile(sel[:, i], 20)) for i in range(3)]
    else:
        gfill = [0.05, 0.05, 0.06]

    # ---- point-light clusters (BFS on 1/8-res binary mask) ----
    ds = 8
    small = mask[::ds, ::ds] > 0.4
    en_small = (mask * val)[::ds, ::ds]
    lab = np.zeros(small.shape, np.int32)
    nlab = 0
    comps = []
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
                pts = np.array(pix)
                e = en_small[pts[:, 0], pts[:, 1]]
                comps.append((float(e.sum()), pts, e))
    comps.sort(key=lambda c: -c[0])
    total_e = sum(c[0] for c in comps) or 1.0
    lights = []
    for e_sum, pts, e in comps[:4]:
        w_ = e / max(e.sum(), 1e-6)
        cy = float((pts[:, 0] * w_).sum()) * ds / H
        cx = float((pts[:, 1] * w_).sum()) * ds / W
        # mean emissive colour at those pixels (full-res nearest)
        ys = np.clip((pts[:, 0] * ds), 0, H - 1)
        xs = np.clip((pts[:, 1] * ds), 0, W - 1)
        col = em[ys, xs].mean(axis=0)
        lights.append({
            "uv": [round(cx, 4), round(cy, 4)],
            "color": [round(float(c), 3) for c in col],
            "energy": round(e_sum / total_e, 3),
        })

    meta = {
        "size": [W, H],
        "pulse": cfg["pulse"],
        "glassFill": [round(c, 4) for c in gfill],
        "glassRects": glass_px,
        "lights": lights,
        "emissiveCoverage": round(float(mask.mean()), 4),
    }
    json.dump(meta, open(HERE / f"{skin}-meta.json", "w"), indent=1)
    print(skin, "emissive coverage", round(float(mask.mean()), 4), "lights:")
    for L in lights:
        print("  ", L)


if __name__ == "__main__":
    for skin, cfg in SKINS.items():
        if len(sys.argv) > 1 and skin != sys.argv[1]:
            continue
        extract(skin, cfg)
