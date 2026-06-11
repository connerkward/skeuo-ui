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

    for reg in tpl["regions"]:
        x0, y0, x1, y1 = px(reg["rect"])
        kind, content = reg["kind"], reg["content"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        h = y1 - y0

        if kind == "display":
            # recessed dark screen — kept EMPTY (live content renders at runtime)
            rrect(d, [x0, y0, x1, y1], 8, fill=(20, 22, 24),
                  outline=(70, 72, 76), width=3)
        elif kind in ("button", "toggle"):
            # raised rounded control with top highlight + bottom shadow
            rad = int(min(h * 0.32, 14))
            rrect(d, [x0, y0, x1, y1], rad, fill=(206, 208, 212),
                  outline=(108, 110, 114), width=3)
            rrect(d, [x0 + 3, y0 + 3, x1 - 3, y0 + (y1 - y0) * 0.45], rad,
                  fill=(226, 228, 232))
            lab = reg.get("label", "")
            d.text((cx, cy), lab[:8], fill=(60, 62, 66),
                   font=font(max(10, int(h * 0.34))), anchor="mm")
        elif kind == "slider-h":
            # recessed channel ONLY — the knob is a live React element at runtime
            rrect(d, [x0, cy - 5, x1, cy + 5], 5, fill=(40, 42, 46),
                  outline=(86, 88, 92), width=2)
        elif kind == "slider-v":
            rrect(d, [cx - 5, y0, cx + 5, y1], 5, fill=(40, 42, 46),
                  outline=(86, 88, 92), width=2)

    out = os.path.join(HERE, "control.png")
    img.save(out)
    print("wrote", out, img.size)

if __name__ == "__main__":
    render()
