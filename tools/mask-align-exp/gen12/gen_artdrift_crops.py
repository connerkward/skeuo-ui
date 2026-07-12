#!/usr/bin/env python3
"""gen_artdrift_crops — small helper for artdrift.html. $0, no new generations: reads
artdrift_data.json (written by analyze_artdrift.py) and the mainline roster's own
paint.png, and bakes ONE labeled-overlay crop per templated skin: TEMPLATE album_art /
visualizer boxes (dashed) vs DETECTED device boxes (solid), captioned with the drift
magnitude, per label-overlays-rule (every drawn shape must carry a legible id + value).

Usage: python3 gen_artdrift_crops.py   (writes artdrift_crops/<skin>.jpg)
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "artdrift_crops")
os.makedirs(OUT, exist_ok=True)

FONT_PATHS = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]
def font(sz):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()

COL_TEMPLATE = (255, 210, 0, 255)     # yellow dashed = template/authored slot
COL_DETECTED_AA = (0, 220, 255, 255)  # cyan solid = detected album_art
COL_DETECTED_VZ = (255, 60, 140, 255) # magenta solid = detected visualizer

def dashed_rect(d, box, color, width=6, dash=18, gap=12):
    x0, y0, x1, y1 = box
    # top+bottom
    for (ya) in (y0, y1):
        x = x0
        while x < x1:
            d.line([(x, ya), (min(x + dash, x1), ya)], fill=color, width=width)
            x += dash + gap
    for (xa) in (x0, x1):
        y = y0
        while y < y1:
            d.line([(xa, y), (xa, min(y + dash, y1))], fill=color, width=width)
            y += dash + gap

def label(d, xy, text, fg=(0, 0, 0, 255), bg=(255, 255, 255, 235), sz=34, anchor="la"):
    f = font(sz)
    bbox = d.textbbox(xy, text, font=f, anchor=anchor)
    pad = 6
    d.rectangle([bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad], fill=bg)
    d.text(xy, text, font=f, fill=fg, anchor=anchor)


def main():
    data = json.load(open(os.path.join(HERE, "artdrift_data.json")))
    mainline = [g for g in data["gens"] if g["group"] == "mainline"]
    made = []
    for g in mainline:
        sid = g["id"]
        d_path = os.path.join(HERE, g["dir"], "paint.png")
        if not os.path.exists(d_path):
            print(f"  skip {sid}: no paint.png")
            continue
        im = Image.open(d_path).convert("RGB")
        W, H = im.size
        canvas = Image.new("RGBA", (W, H))
        canvas.paste(im, (0, 0))
        draw = ImageDraw.Draw(canvas, "RGBA")

        tmpl = g["template"]
        ctrls = g["controls"]

        def px_box(cx_frac, cy_frac, w_frac, h_frac):
            return (int((cx_frac - w_frac / 2) * W), int((cy_frac - h_frac / 2) * H),
                    int((cx_frac + w_frac / 2) * W), int((cy_frac + h_frac / 2) * H))

        # authored template sizes (genskin.py ART_W/H, VIZ_W/H on COL_W x DEV_H, DEVF-scaled)
        DEVF = 1440 / 1920
        ART_W_F, ART_H_F = 560 / 1200 * DEVF, 300 / 1440 * DEVF
        VIZ_W_F, VIZ_H_F = 640 / 1200 * DEVF, 156 / 1440 * DEVF
        # hcapsule uses ART_H*1.15
        aa_h_f = ART_H_F * (1.15 if g["archetype"] == "hcapsule" else 1.0)

        if "album_art" in tmpl:
            box = px_box(tmpl["album_art"][0], tmpl["album_art"][1], ART_W_F, aa_h_f)
            dashed_rect(draw, box, COL_TEMPLATE)
            label(draw, (box[0], max(0, box[1] - 46)), "TEMPLATE album_art", fg=(90, 70, 0, 255),
                  bg=(255, 230, 120, 235), sz=30)
        if "visualizer" in tmpl:
            box = px_box(tmpl["visualizer"][0], tmpl["visualizer"][1], VIZ_W_F, VIZ_H_F)
            dashed_rect(draw, box, COL_TEMPLATE)
            label(draw, (box[0], box[3] + 6), "TEMPLATE visualizer", fg=(90, 70, 0, 255),
                  bg=(255, 230, 120, 235), sz=30)

        if "album_art" in ctrls:
            c = ctrls["album_art"]
            box = px_box(c["det_center_frac"][0], c["det_center_frac"][1], ART_W_F, aa_h_f)
            draw.rectangle(box, outline=COL_DETECTED_AA, width=8)
            label(draw, (box[0], box[3] + 6), f"DETECTED album_art  drift {c['mag_px']:.0f}px",
                  fg=(0, 60, 70, 255), bg=(150, 245, 255, 235), sz=30)
        if "visualizer" in ctrls:
            c = ctrls["visualizer"]
            box = px_box(c["det_center_frac"][0], c["det_center_frac"][1], VIZ_W_F, VIZ_H_F)
            draw.rectangle(box, outline=COL_DETECTED_VZ, width=8)
            label(draw, (box[2], box[1] - 46) if box[2] < W - 260 else (box[0], box[1] - 46),
                  f"DETECTED visualizer  drift {c['mag_px']:.0f}px",
                  fg=(90, 0, 40, 255), bg=(255, 190, 220, 235), sz=30, anchor="ra" if box[2] < W - 260 else "la")

        gate = "FAIL" if not g["gate_pass"] and g.get("drift_worst") else ("PASS" if g["gate_pass"] else "FAIL")
        label(draw, (24, 24), f"{sid}  ({g['archetype']})  gate={gate}  mean_drift={g.get('drift_mean_px')}px",
              fg=(255, 255, 255, 255), bg=(20, 20, 20, 210), sz=40)

        # crop to top ~80% (where the art/viz composition lives) + small margin
        crop = canvas.crop((0, 0, W, int(H * 0.80)))
        crop = crop.convert("RGB")
        crop.save(os.path.join(OUT, f"{sid}.jpg"), quality=90)
        made.append(sid)
        print(f"  wrote artdrift_crops/{sid}.jpg")

    print(f"\n{len(made)} crops written to {OUT}")


if __name__ == "__main__":
    main()
