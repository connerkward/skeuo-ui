#!/usr/bin/env python3
"""annotate.py — draw the detected knob_zero_deg pointer angle onto the raw cut cap sprite
(assets-<id>_biref/vol.png) for the knob-zero-fix proof page. Reimplements ONLY the centroid/
radius geometry from extract12.py's detect_knob_zero_deg() (same alpha>40, R=p97 radius) so the
drawn circle/line land exactly where the real detector measured — no separate guess at center.

Not a pipeline file: throwaway proof-page asset generator, output lives in knobzero-proof/.
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
OUT = HERE

SKINS = [
    dict(id="steam-porthole", zero=84.0, note=None),
    dict(id="ps1-crunchy", zero=142.0, note=None),
    dict(id="myst-arcanum", zero=94.0, note="two-marks"),
    dict(id="fallout-vault", zero=354.0, note=None),  # 354 == -6 mod 360
    dict(id="fa-pod", zero=4.0, note=None, regression=True),
    dict(id="n64-cutscene", zero=0.0, note=None, regression=True),
]

UPSCALE = 4  # sprites are ~330-515px; upscale for legibility per verify-rule close-up crops

def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

def cap_centroid_radius(arr):
    alpha = arr[:, :, 3] > 40
    ys, xs = np.where(alpha)
    cy, cx = ys.mean(), xs.mean()
    R = float(np.percentile(np.hypot(xs - cx, ys - cy), 97))
    return cx, cy, R

def angle_to_xy(cx, cy, R, deg, frac=1.0):
    theta = math.radians(deg)
    x = cx + R * frac * math.sin(theta)
    y = cy - R * frac * math.cos(theta)
    return x, y

def draw_pointer(draw, cx, cy, R, deg, color, width, dash=False, r_lo_frac=0.0):
    x0, y0 = angle_to_xy(cx, cy, R, deg, r_lo_frac)
    x1, y1 = angle_to_xy(cx, cy, R, deg, 1.02)
    if dash:
        n = 14
        for i in range(0, n, 2):
            a = i / n; b = min(1.0, (i + 1) / n)
            ax = x0 + (x1 - x0) * a; ay = y0 + (y1 - y0) * a
            bx = x0 + (x1 - x0) * b; by = y0 + (y1 - y0) * b
            draw.line([(ax, ay), (bx, by)], fill=color, width=width)
    else:
        draw.line([(x0, y0), (x1, y1)], fill=color, width=width)
    # arrowhead
    ah = 14
    theta = math.radians(deg)
    perp = theta + math.pi / 2
    ax1 = x1 - ah * math.sin(theta) + ah * 0.5 * math.sin(perp)
    ay1 = y1 + ah * math.cos(theta) - ah * 0.5 * math.cos(perp)
    ax2 = x1 - ah * math.sin(theta) - ah * 0.5 * math.sin(perp)
    ay2 = y1 + ah * math.cos(theta) + ah * 0.5 * math.cos(perp)
    draw.polygon([(x1, y1), (ax1, ay1), (ax2, ay2)], fill=color)

def legend_row(draw, x, y, color, text, f):
    sw = 34
    draw.line([(x, y + 12), (x + sw, y + 12)], fill=color, width=6)
    draw.text((x + sw + 10, y), text, fill=(235, 235, 240, 255), font=f)

def process(skin):
    sid = skin["id"]
    src = os.path.join(GEN12, f"assets-{sid}_biref", "vol.png")
    im = Image.open(src).convert("RGBA")
    arr = np.asarray(im).astype(float)
    cx, cy, R = cap_centroid_radius(arr)

    im2 = im.resize((im.width * UPSCALE, im.height * UPSCALE), Image.LANCZOS)
    cx2, cy2, R2 = cx * UPSCALE, cy * UPSCALE, R * UPSCALE
    canvas = Image.new("RGBA", im2.size, (18, 18, 22, 255))
    canvas.alpha_composite(im2)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # center + measurement ring (green, thin) — shows the r_lo..r_hi ring the detector scanned
    draw.ellipse([cx2-R2*0.28, cy2-R2*0.28, cx2+R2*0.28, cy2+R2*0.28], outline=(0, 220, 140, 150), width=2)
    draw.ellipse([cx2-R2*0.94, cy2-R2*0.94, cx2+R2*0.94, cy2+R2*0.94], outline=(0, 220, 140, 150), width=2)
    draw.ellipse([cx2-5, cy2-5, cx2+5, cy2+5], fill=(255, 255, 255, 255))

    zero = skin["zero"]
    draw_pointer(draw, cx2, cy2, R2, zero, (255, 60, 60, 255), 6)
    if skin.get("note") == "two-marks":
        draw_pointer(draw, cx2, cy2, R2, 0.0, (60, 170, 255, 255), 4, dash=True)

    # header caption band + legend
    band_h = 56
    legend_h = 80 if skin.get("note") == "two-marks" else 48
    cap = Image.new("RGBA", (canvas.width, band_h), (12, 12, 16, 235))
    cd = ImageDraw.Draw(cap)
    cd.text((14, 10), f"{sid} — raw cut sprite (assets-{sid}_biref/vol.png), material-agnostic radial-anomaly detector",
             fill=(220, 220, 225, 255), font=font(18))

    leg = Image.new("RGBA", (canvas.width, legend_h), (12, 12, 16, 235))
    ld = ImageDraw.Draw(leg)
    f18 = font(18)
    legend_row(ld, 14, 10, (255, 60, 60, 255), f"DETECTED knob_zero_deg = {zero:.0f}°" + (" — chosen: wedge slit" if skin.get("note") == "two-marks" else " — pointer/notch anomaly"), f18)
    if skin.get("note") == "two-marks":
        legend_row(ld, 14, 44, (60, 170, 255, 255), "alt candidate (not chosen): V-notch, ~0° — see myst-arcanum ambiguity note below", f18)

    out = Image.new("RGBA", (canvas.width, canvas.height + band_h + legend_h), (0, 0, 0, 0))
    out.paste(canvas, (0, 0))
    out.paste(cap, (0, canvas.height), cap)
    out.paste(leg, (0, canvas.height + band_h), leg)

    dst = os.path.join(OUT, f"{sid}-raw-annotated.png")
    out.convert("RGB").save(dst, quality=95)
    print("wrote", dst, out.size)

if __name__ == "__main__":
    for s in SKINS:
        process(s)
