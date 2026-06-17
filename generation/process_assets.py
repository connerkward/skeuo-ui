#!/usr/bin/env python3
"""Generate per-stage illustration images for the process webview, using pebble as
the exemplar: blueprint (wells-only), envelope (gray body + wells), paint (on white),
composite (on dark), and an align overlay (labeled control boxes on the frame)."""
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "public", "skins", "pebble")
OUT = os.path.join(ROOT, "public", "process"); os.makedirs(OUT, exist_ok=True)
W, H = 1024, 1536
WELL = (18, 20, 22); EDGE = (70, 74, 78); GRAY = (176, 178, 182)
COL = {"button": (90, 255, 130), "knob": (90, 180, 255), "slider-h": (255, 90, 110),
       "slider-v": (255, 210, 70), "toggle": (255, 138, 61), "display": (180, 150, 255)}
tpl = json.load(open(os.path.join(SK, "template.json")))
regs = tpl["regions"]
frame = Image.open(os.path.join(SK, "frame.png")).convert("RGBA").resize((W, H))


def font(s):
    try: return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", s)
    except: return ImageFont.load_default()


def draw_wells(d, fill_disp):
    for r in regs:
        rc = r["rect"]; x0, y0 = rc["x"]*W, rc["y"]*H; x1, y1 = x0+rc["w"]*W, y0+rc["h"]*H
        k = r["kind"]; ell = r.get("shape") == "ellipse" or k == "knob"
        if k == "display":
            (d.ellipse if ell else d.rounded_rectangle)([x0, y0, x1, y1], **({} if ell else {"radius": 14}), fill=fill_disp, outline=EDGE, width=5)
        elif ell or k == "button":
            d.ellipse([x0, y0, x1, y1], fill=WELL, outline=EDGE, width=4)
        else:
            d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=WELL, outline=EDGE, width=4)


def save(im, name): im.convert("RGB").save(os.path.join(OUT, f"pebble-{name}.png")); print("  pebble-"+name)


# 1 blueprint: wells on white
bp = Image.new("RGB", (W, H), (244, 244, 246)); draw_wells(ImageDraw.Draw(bp), (12, 13, 15)); save(bp, "blueprint")

# 2 envelope: gray body silhouette (from frame alpha) + wells
alpha = np.asarray(frame.split()[-1]) > 40
env = np.full((H, W, 3), 244, np.uint8); env[alpha] = GRAY
env = Image.fromarray(env); draw_wells(ImageDraw.Draw(env), (12, 13, 15)); save(env, "envelope")

# 3 paint: the painted device on white
pw = Image.new("RGBA", (W, H), (244, 244, 246, 255)); pw.alpha_composite(frame); save(pw, "paint")

# 4 composite: on dark (transparency / final frame)
pd = Image.new("RGBA", (W, H), (20, 21, 24, 255)); pd.alpha_composite(frame); save(pd, "composite")

# 5 align: labeled control boxes on the frame (per label-overlays-rule)
al = pd.copy(); g = ImageDraw.Draw(al, "RGBA"); f = font(26)
for r in regs:
    rc = r["rect"]; x0, y0 = rc["x"]*W, rc["y"]*H; x1, y1 = x0+rc["w"]*W, y0+rc["h"]*H
    c = COL.get(r["kind"], (200, 200, 200)); g.rectangle([x0, y0, x1, y1], outline=c+(255,), width=5)
    lab = r.get("bind") or r.get("dynamicType") or r["kind"]
    tb = g.textbbox((0, 0), lab, font=f); tw = tb[2]-tb[0]
    ly = max(26, y0-30); g.rectangle([x0, ly-4, x0+tw+10, ly+26], fill=(0, 0, 0, 220)); g.text((x0+5, ly), lab, fill=c, font=f)
save(al, "align")
print("done ->", OUT)
