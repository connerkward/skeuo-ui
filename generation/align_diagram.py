#!/usr/bin/env python3
"""A DEAD-SIMPLE 2-panel align explainer: a tight zoom on the pebble transport
cluster, shown twice —

  1 · VLM MASK   magenta fills = where the vision model says each control is
  2 · SNAP       the template rects locked onto those blobs (green outline + dot)

Real pebble paint underneath both. No connecting clutter; one centered arrow.
Output → site/process/pebble-align-maskvsnap.png.
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "public", "skins", "pebble")
OUT = os.path.join(ROOT, "site", "process", "pebble-align-maskvsnap.png")
SRC = os.path.join(ROOT, "site", "process", "pebble-composite.png")

CW, CH = 1024, 1536
CROP = (0.25, 0.378, 0.75, 0.605)   # tight on seek + play/prev/next + volume
S = 2                                # supersample
PW = 360 * S                         # panel display width

MAG = (214, 40, 184); GRN = (120, 240, 150); INK = (236, 240, 245)
SUB = (150, 156, 168); BG = (15, 16, 20)
CTRL = {"button", "knob", "toggle", "slider-h", "slider-v", "slider-arc"}

tpl = json.load(open(os.path.join(SK, "template.json")))
ctrls = [r for r in tpl["regions"] if r["kind"] in CTRL]


def font(s, bold=True):
    p = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"
    try: return ImageFont.truetype(p, s)
    except Exception: return ImageFont.load_default()


def crop_inset():
    comp = Image.open(SRC).convert("RGB")
    x0, y0, x1, y1 = CROP[0]*CW, CROP[1]*CH, CROP[2]*CW, CROP[3]*CH
    c = comp.crop((int(x0), int(y0), int(x1), int(y1)))
    s = PW / c.width
    return c.resize((PW, int(c.height*s)), Image.LANCZOS), s, (x0, y0)


def box(rc, s, off, grow=0):
    x = (rc["x"]*CW - off[0])*s - grow; y = (rc["y"]*CH - off[1])*s - grow
    return [x, y, x + rc["w"]*CW*s + 2*grow, y + rc["h"]*CH*s + 2*grow]


def is_round(r): return r.get("shape") == "ellipse" or r["kind"] == "knob"


def panel_mask(img, s, off):
    im = img.copy(); d = ImageDraw.Draw(im, "RGBA")
    for r in ctrls:
        b = box(r["rect"], s, off, grow=2*S)
        (d.ellipse if is_round(r) else d.rounded_rectangle)(
            b, **({} if is_round(r) else {"radius": 7*S}), fill=MAG+(235,))
    return im


def panel_snap(img, s, off):
    im = img.copy(); d = ImageDraw.Draw(im, "RGBA")
    for r in ctrls:
        b = box(r["rect"], s, off, grow=2*S)
        (d.ellipse if is_round(r) else d.rounded_rectangle)(
            b, **({} if is_round(r) else {"radius": 7*S}), outline=GRN+(255,), width=3*S)
        cx, cy = (b[0]+b[2])/2, (b[1]+b[3])/2
        d.ellipse([cx-3*S, cy-3*S, cx+3*S, cy+3*S], fill=INK+(255,))
    return im


def build():
    img, s, off = crop_inset()
    pmask, psnap = panel_mask(img, s, off), panel_snap(img, s, off)
    ph = img.height
    pad = 18*S; head = 26*S; cap = 26*S; gap = 40*S
    W = pad + PW + gap + PW + pad
    H = head + ph + cap + pad
    sheet = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(sheet, "RGBA")
    d.text((pad, pad*0.5), "How align finds each control", fill=INK, font=font(15*S))
    top = head
    for i, (img_p, num, title, col) in enumerate(
            [(pmask, 1, "VLM mask", MAG), (psnap, 2, "Snap", GRN)]):
        x = pad + i*(PW+gap)
        sheet.paste(img_p, (int(x), int(top)))
        d.rounded_rectangle([x-1, top-1, x+PW+1, top+ph+1], radius=7*S, outline=(58, 62, 72, 255), width=S)
        cy = top + ph + 6*S
        d.ellipse([x, cy, x+19*S, cy+19*S], fill=col+(255,))
        d.text((x+9.5*S, cy+9.5*S), str(num), fill=(12, 12, 14), font=font(12*S), anchor="mm")
        d.text((x+26*S, cy+1*S), title, fill=INK, font=font(13*S))
        sub = "magenta = where each control landed" if i == 0 else "template rects locked onto the mask"
        d.text((x+26*S, cy+15*S), sub, fill=SUB, font=font(10*S, False))
    # one arrow, vertically centred on the panel images
    ax = pad + PW + gap*0.5; ay = top + ph/2
    d.text((ax, ay), "→", fill=SUB, font=font(28*S), anchor="mm")
    sheet = sheet.resize((W//S, H//S), Image.LANCZOS)
    sheet.save(OUT)
    print("wrote", OUT, sheet.size)


if __name__ == "__main__":
    build()
