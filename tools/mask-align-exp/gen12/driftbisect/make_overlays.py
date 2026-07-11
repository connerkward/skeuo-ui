#!/usr/bin/env python3
"""make_overlays — per-gen drift overlay: authored template centre (circle) vs extract12
detected device centre (cross), a line between them, per-control label + drift px. Studio
annotation only — never fed to any model (label-overlays-rule). Writes overlay-drift.png
into each assets-bisect-* dir at half paint res."""
import os, json, glob
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    FONT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
    FONT_S = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
except Exception:
    FONT = FONT_S = ImageFont.load_default()

for d in sorted(glob.glob(os.path.join(HERE, "assets-bisect-*"))):
    if d.endswith("_biref"): continue
    rj, resj, pp = (os.path.join(d, f) for f in ("regions.json", "results.json", "paint.png"))
    if not all(os.path.exists(p) for p in (rj, resj, pp)): continue
    regions = json.load(open(rj)); results = json.load(open(resj))
    template = regions.get("template") or results.get("template") or {}
    regs = regions.get("regions", {})
    im = Image.open(pp).convert("RGB")
    W, H = im.size
    im = im.resize((W // 2, H // 2))
    w, h = im.size
    dr = ImageDraw.Draw(im)
    for k, t in template.items():
        dev = (regs.get(k) or {}).get("device")
        if not dev: continue
        tx, ty = t[0] * w, t[1] * h
        cx, cy = (dev[0] + dev[2] / 2) * w, (dev[1] + dev[3] / 2) * h
        drift = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5 * 2  # px on full-res grid
        col = (0, 220, 90) if drift < 300 else ((255, 190, 0) if drift < 700 else (255, 60, 60))
        dr.line([tx, ty, cx, cy], fill=col, width=3)
        r = 14
        dr.ellipse([tx - r, ty - r, tx + r, ty + r], outline=(90, 160, 255), width=4)  # template = blue circle
        dr.line([cx - r, cy - r, cx + r, cy + r], fill=col, width=4)                     # detected = X
        dr.line([cx - r, cy + r, cx + r, cy - r], fill=col, width=4)
        label = f"{k} {drift:.0f}px"
        tb = dr.textbbox((0, 0), label, font=FONT_S)
        lx, ly = min(cx + r + 4, w - (tb[2] - tb[0]) - 8), max(0, cy - 12)
        dr.rectangle([lx - 3, ly - 2, lx + tb[2] - tb[0] + 3, ly + tb[3] - tb[1] + 6], fill=(0, 0, 0))
        dr.text((lx, ly), label, fill=(255, 255, 255), font=FONT_S)
    legend = "STUDIO OVERLAY (not sent to any model) — blue circle = authored template centre, X = extract12 detected centre; green<300px amber<700px red>=700px"
    tb = dr.textbbox((0, 0), legend, font=FONT_S)
    dr.rectangle([0, h - (tb[3] - tb[1]) - 14, w, h], fill=(0, 0, 0))
    dr.text((8, h - (tb[3] - tb[1]) - 8), legend, fill=(255, 230, 120), font=FONT_S)
    out = os.path.join(d, "overlay-drift.png")
    im.save(out)
    print("->", os.path.basename(d))
