#!/usr/bin/env python3
"""annotate2.py — draw the detected knob_zero_deg pointer angle onto the raw cut cap sprite,
reading the angle AND the center/radius geometry FROM regions.json's stored knob_zero_deg /
knob_zero_geo — never re-derived. Replaces the old annotate.py, which reimplemented the
centroid/radius math independently of extract12.py (a verify-outputs-rule §7 proxy-trap on
principle, even though it happened to reproduce near-identical numbers here). This script draws
whatever the pipeline ACTUALLY computed and stored, full stop.
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
OUT = HERE

SKINS = ["steam-porthole", "ps1-crunchy", "myst-arcanum", "fallout-vault", "fa-pod", "n64-cutscene"]
UPSCALE = 4


def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def angle_to_xy(cx, cy, R, deg, frac=1.0):
    theta = math.radians(deg)
    return cx + R * frac * math.sin(theta), cy - R * frac * math.cos(theta)


def draw_pointer(draw, cx, cy, R, deg, color, width, r_lo_frac=0.0):
    x0, y0 = angle_to_xy(cx, cy, R, deg, r_lo_frac)
    x1, y1 = angle_to_xy(cx, cy, R, deg, 1.02)
    draw.line([(x0, y0), (x1, y1)], fill=color, width=width)
    ah = 14
    theta = math.radians(deg)
    perp = theta + math.pi / 2
    ax1 = x1 - ah * math.sin(theta) + ah * 0.5 * math.sin(perp)
    ay1 = y1 + ah * math.cos(theta) - ah * 0.5 * math.cos(perp)
    ax2 = x1 - ah * math.sin(theta) - ah * 0.5 * math.sin(perp)
    ay2 = y1 + ah * math.cos(theta) + ah * 0.5 * math.cos(perp)
    draw.polygon([(x1, y1), (ax1, ay1), (ax2, ay2)], fill=color)


def process(sid):
    regs = json.load(open(os.path.join(GEN12, f"assets-{sid}", "regions.json")))["regions"]
    kn = next(k for k, v in json.load(open(os.path.join(GEN12, f"assets-{sid}", "regions.json"))).get("roles", {}).items() if v == "knob")
    r = regs[kn]
    zero = r["knob_zero_deg"]
    geo = r.get("knob_zero_geo")
    src = os.path.join(GEN12, f"assets-{sid}_biref", f"{kn}.png")
    im = Image.open(src).convert("RGBA")
    if geo is None:
        cx, cy = im.width / 2.0, im.height / 2.0
        R = min(im.width, im.height) / 2.0
    else:
        cx, cy, R = geo

    im2 = im.resize((im.width * UPSCALE, im.height * UPSCALE), Image.LANCZOS)
    cx2, cy2, R2 = cx * UPSCALE, cy * UPSCALE, R * UPSCALE
    canvas = Image.new("RGBA", im2.size, (18, 18, 22, 255))
    canvas.alpha_composite(im2)
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.ellipse([cx2 - R2 * 0.28, cy2 - R2 * 0.28, cx2 + R2 * 0.28, cy2 + R2 * 0.28], outline=(0, 220, 140, 150), width=2)
    draw.ellipse([cx2 - R2 * 0.94, cy2 - R2 * 0.94, cx2 + R2 * 0.94, cy2 + R2 * 0.94], outline=(0, 220, 140, 150), width=2)
    draw.ellipse([cx2 - 5, cy2 - 5, cx2 + 5, cy2 + 5], fill=(255, 255, 255, 255))

    if zero is not None:
        draw_pointer(draw, cx2, cy2, R2, zero, (255, 60, 60, 255), 6)

    band_h = 56
    cap = Image.new("RGBA", (canvas.width, band_h), (12, 12, 16, 235))
    cd = ImageDraw.Draw(cap)
    cd.text((14, 10), f"{sid} — raw cut sprite, geometry read from regions.json (stored, not re-derived)",
             fill=(220, 220, 225, 255), font=font(18))

    leg_h = 40
    leg = Image.new("RGBA", (canvas.width, leg_h), (12, 12, 16, 235))
    ld = ImageDraw.Draw(leg)
    ztxt = "no anomaly found (null)" if zero is None else f"{zero:.2f}°"
    ld.text((14, 8), f"stored regions[{kn}].knob_zero_deg = {ztxt}", fill=(255, 120, 120, 255), font=font(18))

    out = Image.new("RGBA", (canvas.width, canvas.height + band_h + leg_h), (0, 0, 0, 0))
    out.paste(canvas, (0, 0))
    out.paste(cap, (0, canvas.height), cap)
    out.paste(leg, (0, canvas.height + band_h), leg)
    dst = os.path.join(OUT, f"{sid}-raw-annotated.png")
    out.convert("RGB").save(dst, quality=95)
    print("wrote", dst, out.size)


if __name__ == "__main__":
    for s in SKINS:
        process(s)
