#!/usr/bin/env python3
"""Render a neutral skeuomorphic-blueprint CONTROL image from the template.

The image model (fal gpt-image-1.5/edit) receives this as the structural
reference: it shows exactly where every button / slider / screen sits, with
light 3D hinting so the model styles it as physical controls (not engraving)
while preserving the layout. Output is sized to the model's 1024x1536 canvas
so there is no reprojection — normalized coords map identically at runtime.
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(__file__)
TPL = json.load(open(os.path.join(HERE, "template.json")))

OUT_W, OUT_H = 1024, 1536  # model output size

tpl = TPL
def px(r):
    return (r["x"] * OUT_W, r["y"] * OUT_H,
            (r["x"] + r["w"]) * OUT_W, (r["y"] + r["h"]) * OUT_H)

def font(sz):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()

def rrect(d, box, r, **kw):
    d.rounded_rectangle(box, radius=r, **kw)

def render():
    img = Image.new("RGB", (OUT_W, OUT_H), (176, 178, 182))  # neutral panel gray
    d = ImageDraw.Draw(img)
    # outer bezel hint
    d.rounded_rectangle([6, 6, OUT_W - 6, OUT_H - 6], radius=26,
                        outline=(120, 122, 126), width=10)

    PANEL = (176, 178, 182)
    for reg in tpl["regions"]:
        x0, y0, x1, y1 = px(reg["rect"])
        kind, content = reg["kind"], reg["content"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = x1 - x0, y1 - y0

        if kind == "flourish":
            # decorative inset — slightly proud panel with a thin frame + motif,
            # signalling the model to ORNAMENT here (not place a control)
            rrect(d, [x0, y0, x1, y1], 6, fill=(168, 170, 174),
                  outline=(140, 142, 146), width=2)
            r = min(w, h) * 0.18
            d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
                      outline=(150, 152, 156), width=2)
        elif kind == "display":
            rrect(d, [x0, y0, x1, y1], 8, fill=(20, 22, 24), outline=(70, 72, 76), width=3)
        elif kind in ("button", "toggle"):
            rad = int(min(h * 0.32, 14))
            rrect(d, [x0, y0, x1, y1], rad, fill=(206, 208, 212), outline=(108, 110, 114), width=3)
            rrect(d, [x0 + 3, y0 + 3, x1 - 3, y0 + h * 0.45], rad, fill=(226, 228, 232))
            d.text((cx, cy), reg.get("label", "")[:8], fill=(60, 62, 66),
                   font=font(max(10, int(h * 0.34))), anchor="mm")
        elif kind == "segmented":
            rad = int(min(h * 0.3, 12))
            rrect(d, [x0, y0, x1, y1], rad, fill=(200, 202, 206), outline=(108, 110, 114), width=3)
            opts = reg.get("options", []) or [""]
            n = len(opts)
            for i, o in enumerate(opts):
                sx = x0 + w * i / n
                if i: d.line([(sx, y0 + 3), (sx, y1 - 3)], fill=(120, 122, 126), width=2)
                d.text((sx + w / n / 2, cy), str(o)[:5], fill=(70, 72, 76),
                       font=font(max(9, int(h * 0.34))), anchor="mm")
        elif kind == "knob":
            # raised circular knob body (no indicator — that's a live element)
            cr = min(w, h) * 0.40
            d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(120, 124, 130),
                      outline=(80, 82, 86), width=3)
            d.ellipse([cx - cr * 0.55, cy - cr * 0.55, cx + cr * 0.55, cy + cr * 0.55],
                      fill=(150, 154, 160))
        elif kind == "xy":
            # recessed square pad with crosshair
            rrect(d, [x0, y0, x1, y1], 6, fill=(26, 28, 30), outline=(78, 80, 84), width=3)
            d.line([(x0 + 4, cy), (x1 - 4, cy)], fill=(60, 62, 66), width=1)
            d.line([(cx, y0 + 4), (cx, y1 - 4)], fill=(60, 62, 66), width=1)
        elif kind == "slider-h":
            rrect(d, [x0, cy - 5, x1, cy + 5], 5, fill=(40, 42, 46), outline=(86, 88, 92), width=2)
        elif kind == "slider-v":
            rrect(d, [cx - 5, y0, cx + 5, y1], 5, fill=(40, 42, 46), outline=(86, 88, 92), width=2)

    out = os.path.join(HERE, "control.png")
    img.save(out)
    print("wrote", out, img.size)

if __name__ == "__main__":
    render()
