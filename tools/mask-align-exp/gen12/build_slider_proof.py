#!/usr/bin/env python3
"""Build the seek-slider overshoot-fix proof page (labeled crops + slider-fix-proof.html) from
the raw full-page screenshots in slider-proof-media/_raw/ and slider-proof-media/measurements.json.
One-off script for the 2026-07-12 seek-travel-overshoot fix proof. $0, local, no network calls."""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(HERE, "slider-proof-media")
RAW = os.path.join(MEDIA, "_raw")
DF = 0.75
SKINS = ["claymation", "diablo-gothic", "fallout-vault", "n64-cutscene", "ps1-crunchy"]

meas = json.load(open(os.path.join(MEDIA, "measurements.json")))

def font(size):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Menlo.ttc"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

F_CAP = font(15)
F_SMALL = font(12)

def device_px(entry):
    """Return (x0,y0,x1,y1) of the device/groove rect in raw-screenshot px.
    y is always a fraction of paint-height (needs /DF); x is a direct fraction of phone width
    (no crop horizontally) -- see build_player.py's DF handling."""
    pr = entry["phoneRect"]
    dx, dy, dw, dh = entry["device"]
    x0 = pr["x"] + dx * pr["width"]
    x1 = pr["x"] + (dx + dw) * pr["width"]
    y0 = pr["y"] + (dy / DF) * pr["height"]
    y1 = pr["y"] + ((dy + dh) / DF) * pr["height"]
    return x0, y0, x1, y1

def overshoot(entry, extreme):
    vert = entry["vert"]
    x0, y0, x1, y1 = device_px(entry)
    tr = entry["minThumbRect"] if extreme == "min" else entry["maxThumbRect"]
    if vert:
        lo, hi = y0, y1
        thumb_lo, thumb_hi = tr["y"], tr["y"] + tr["height"]
    else:
        lo, hi = x0, x1
        thumb_lo, thumb_hi = tr["x"], tr["x"] + tr["width"]
    if extreme == "min":
        signed = lo - thumb_lo   # + = thumb pokes out past the LOW (left/top) end
    else:
        signed = thumb_hi - hi   # + = thumb pokes out past the HIGH (right/bottom) end
    return signed

def draw_caption(im, text, color):
    """Dark backing pill + text, top-left, per label-overlays-rule."""
    d = ImageDraw.Draw(im)
    bbox = d.textbbox((0, 0), text, font=F_CAP)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 6
    d.rectangle([4, 4, 4 + tw + pad * 2, 4 + th + pad * 2], fill=(10, 10, 14, 230))
    d.text((4 + pad, 4 + pad - bbox[1]), text, fill=color, font=F_CAP)
    return im

def crop_padded(im, entry, extreme):
    """Generous crop around the SPECIFIC end-cap under test at this extreme (not the whole
    groove span -- on a long-throw slider the far end dwarfs the thumb and the overshoot
    becomes invisible). Same boundary-focus as crop_zoom, just wider padding, no upscale."""
    vert = entry["vert"]
    x0, y0, x1, y1 = device_px(entry)
    tr = entry["minThumbRect"] if extreme == "min" else entry["maxThumbRect"]
    tx0, ty0, tx1, ty1 = tr["x"], tr["y"], tr["x"] + tr["width"], tr["y"] + tr["height"]
    if vert:
        cross0, cross1 = min(x0, tx0), max(x1, tx1)
        cross_pad = max(30, (cross1 - cross0) * 0.6)
        cross0 -= cross_pad; cross1 += cross_pad
        boundary = y0 if extreme == "min" else y1
        along_half = max(70, (ty1 - ty0) * 1.3)
        along0, along1 = boundary - along_half, boundary + along_half
        box = (cross0, along0, cross1, along1)
    else:
        cross0, cross1 = min(y0, ty0), max(y1, ty1)
        cross_pad = max(30, (cross1 - cross0) * 0.6)
        cross0 -= cross_pad; cross1 += cross_pad
        boundary = x0 if extreme == "min" else x1
        along_half = max(70, (tx1 - tx0) * 1.3)
        along0, along1 = boundary - along_half, boundary + along_half
        box = (along0, cross0, along1, cross1)
    bx0, by0, bx1, by1 = box
    bx0, by0 = max(0, bx0), max(0, by0)
    bx1, by1 = min(im.width, bx1), min(im.height, by1)
    return im.crop((int(bx0), int(by0), int(bx1), int(by1)))

def crop_zoom(im, entry, extreme):
    """Tight crop of just the relevant end-cap (the boundary under test at this extreme),
    upscaled for visibility."""
    vert = entry["vert"]
    x0, y0, x1, y1 = device_px(entry)
    tr = entry["minThumbRect"] if extreme == "min" else entry["maxThumbRect"]
    tx0, ty0, tx1, ty1 = tr["x"], tr["y"], tr["x"] + tr["width"], tr["y"] + tr["height"]
    if vert:
        cross0, cross1 = min(x0, tx0), max(x1, tx1)
        cross_pad = (cross1 - cross0) * 0.35
        cross0 -= cross_pad; cross1 += cross_pad
        boundary = y0 if extreme == "min" else y1
        along_half = max(30, (ty1 - ty0) * 0.55)
        along0, along1 = boundary - along_half, boundary + along_half
        box = (cross0, along0, cross1, along1)
    else:
        cross0, cross1 = min(y0, ty0), max(y1, ty1)
        cross_pad = (cross1 - cross0) * 0.35
        cross0 -= cross_pad; cross1 += cross_pad
        boundary = x0 if extreme == "min" else x1
        along_half = max(30, (tx1 - tx0) * 0.55)
        along0, along1 = boundary - along_half, boundary + along_half
        box = (along0, cross0, along1, cross1)
    bx0, by0, bx1, by1 = box
    bx0, by0 = max(0, bx0), max(0, by0)
    bx1, by1 = min(im.width, bx1), min(im.height, by1)
    crop = im.crop((int(bx0), int(by0), int(bx1), int(by1)))
    scale = 4
    return crop.resize((max(1, crop.width * scale), max(1, crop.height * scale)), Image.LANCZOS)

results = {}
for skin in SKINS:
    results[skin] = {}
    for phase in ["before", "after"]:
        entry = meas[phase][skin]
        results[skin][phase] = {}
        for extreme in ["min", "max"]:
            raw_path = os.path.join(RAW, f"{skin}-{phase}-{extreme}-full.png")
            im = Image.open(raw_path).convert("RGB")
            osv = overshoot(entry, extreme)
            results[skin][phase][extreme] = osv
            color = (255, 90, 90) if phase == "before" else (110, 230, 140)
            label = f"{skin} · {phase.upper()} · {extreme.upper()} · overshoot: {osv:+.2f}px"

            padded = crop_padded(im, entry, extreme)
            padded = padded.copy()
            draw_caption(padded, label, color)
            padded.save(os.path.join(MEDIA, f"{skin}-{phase}-{extreme}.png"))

            zoom = crop_zoom(im, entry, extreme)
            zoom = zoom.copy()
            draw_caption(zoom, f"{label} · END-CAP ZOOM 4x", color)
            zoom.save(os.path.join(MEDIA, f"{skin}-{phase}-{extreme}-zoom.png"))
    print(f"[proof] {skin}: "
          f"before min={results[skin]['before']['min']:+.2f}px max={results[skin]['before']['max']:+.2f}px  "
          f"after min={results[skin]['after']['min']:+.2f}px max={results[skin]['after']['max']:+.2f}px")

json.dump(results, open(os.path.join(MEDIA, "overshoot-results.json"), "w"), indent=2)
print("[proof] wrote", os.path.join(MEDIA, "overshoot-results.json"))
