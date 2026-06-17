#!/usr/bin/env python3
"""A small 3-panel micro-diagram explaining the ALIGN masking step, built from the
REAL pebble composite as inset screenshots:

  1 · TEMPLATE     control rects (the intended layout) outlined on the painted skin
  2 · VLM MASK     a vision model traces where each control ACTUALLY landed → blobs
  3 · SNAP / WARP  fit the template to the mask: each rect snaps onto its blob

The mask/snap overlays are SCHEMATIC (fal is the real mask source); a small drift is
added so the snap arrows are visible. Output → site/process/pebble-align-steps.png.
"""
import json, os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "public", "skins", "pebble")
OUT = os.path.join(ROOT, "site", "process", "pebble-align-steps.png")
SRC = os.path.join(ROOT, "site", "process", "pebble-composite.png")

CW, CH = 1024, 1536
# crop the composite to the control-dense band so the inset reads at small size
CROP = (0.10, 0.085, 0.90, 0.685)   # x0,y0,x1,y1 in normalized canvas
SCALE = 2                            # render at 2x for crispness
PANEL_W = 300 * SCALE                # panel inset width (px)

CYAN = (90, 210, 255); MAG = (255, 70, 235); GREEN = (90, 255, 150)
INK = (236, 240, 245); SUB = (150, 156, 168); BG = (15, 16, 20)
# control kinds the VLM marks (skip the screen displays)
CTRL = {"button", "knob", "toggle", "slider-h", "slider-v", "slider-arc"}
# deterministic per-control drift (px @ full canvas res) so snap arrows are visible
DRIFT = {"play": (14, -10), "prev": (-12, 8), "next": (11, 9),
         "volume": (-9, -12), "seek": (8, -7)}


def font(s, bold=True):
    p = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"
    try: return ImageFont.truetype(p, s)
    except Exception: return ImageFont.load_default()


tpl = json.load(open(os.path.join(SK, "template.json")))
ctrls = [r for r in tpl["regions"] if r["kind"] in CTRL]


def inset():
    """The cropped pebble composite, scaled to PANEL_W, returns (img, scale_px_per_canvas)."""
    comp = Image.open(SRC).convert("RGB")
    x0, y0, x1, y1 = CROP[0]*CW, CROP[1]*CH, CROP[2]*CW, CROP[3]*CH
    crop = comp.crop((int(x0), int(y0), int(x1), int(y1)))
    s = PANEL_W / crop.width
    img = crop.resize((PANEL_W, int(crop.height*s)), Image.LANCZOS)
    return img, s, (x0, y0)


def to_panel(rc, s, off, dxy=(0, 0)):
    """region rect (normalized canvas) → panel px box, with optional canvas-px drift."""
    x = rc["x"]*CW + dxy[0] - off[0]; y = rc["y"]*CH + dxy[1] - off[1]
    return [x*s, y*s, (x + rc["w"]*CW)*s, (y + rc["h"]*CH)*s]


def is_round(r): return r.get("shape") == "ellipse" or r["kind"] == "knob"


def panel_template(s, off):
    img, _, _ = inset(); d = ImageDraw.Draw(img, "RGBA")
    for r in ctrls:
        b = to_panel(r["rect"], s, off)
        (d.ellipse if is_round(r) else d.rounded_rectangle)(
            b, **({} if is_round(r) else {"radius": 6*SCALE}), outline=CYAN+(255,), width=2*SCALE)
    return img


def panel_mask(s, off):
    img, _, _ = inset()
    img = ImageEnhance.Brightness(img).enhance(0.42)        # dim so the mask pops
    d = ImageDraw.Draw(img, "RGBA")
    for r in ctrls:
        b = to_panel(r["rect"], s, off, DRIFT.get(r.get("bind"), (0, 0)))
        (d.ellipse if is_round(r) else d.rounded_rectangle)(
            b, **({} if is_round(r) else {"radius": 6*SCALE}), fill=MAG+(205,))
    return img


def panel_snap(s, off):
    img, _, _ = inset(); d = ImageDraw.Draw(img, "RGBA")
    for r in ctrls:
        dxy = DRIFT.get(r.get("bind"), (0, 0))
        blob = to_panel(r["rect"], s, off, dxy)           # where the mask is
        rect = to_panel(r["rect"], s, off)                # template (pre-snap)
        # faint magenta blob (the target)
        (d.ellipse if is_round(r) else d.rounded_rectangle)(
            blob, **({} if is_round(r) else {"radius": 6*SCALE}), fill=MAG+(70,))
        # green rect snapped ONTO the blob
        (d.ellipse if is_round(r) else d.rounded_rectangle)(
            blob, **({} if is_round(r) else {"radius": 6*SCALE}), outline=GREEN+(255,), width=2*SCALE)
        # arrow from template centre → blob centre
        c0 = ((rect[0]+rect[2])/2, (rect[1]+rect[3])/2)
        c1 = ((blob[0]+blob[2])/2, (blob[1]+blob[3])/2)
        if abs(c1[0]-c0[0]) + abs(c1[1]-c0[1]) > 5*SCALE:
            d.line([c0, c1], fill=INK+(230,), width=max(1, SCALE))
            d.ellipse([c1[0]-2*SCALE, c1[1]-2*SCALE, c1[0]+2*SCALE, c1[1]+2*SCALE], fill=INK+(255,))
    return img


def chip(d, x, y, num, title, col):
    f1, f2 = font(15*SCALE), font(13*SCALE, False)
    d.ellipse([x, y, x+22*SCALE, y+22*SCALE], fill=col+(255,))
    d.text((x+11*SCALE, y+11*SCALE), str(num), fill=(12, 12, 14), font=f1, anchor="mm")
    d.text((x+30*SCALE, y+3*SCALE), title, fill=INK, font=f1)
    return f2


def build():
    _, s, off = inset()
    panels = [("TEMPLATE", "intended layout", CYAN, panel_template(s, off)),
              ("VLM MASK", "where controls landed", MAG, panel_mask(s, off)),
              ("SNAP / WARP", "fit template to mask", GREEN, panel_snap(s, off))]
    ph = panels[0][3].height
    pad = 22*SCALE; head = 30*SCALE; cap = 30*SCALE; arrow = 34*SCALE
    W = pad + sum(PANEL_W + arrow for _ in panels) - arrow + pad
    H = head + ph + cap + pad + head
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet, "RGBA")
    d.text((pad, pad*0.6), "Align — make the template match where the paint actually put the controls",
           fill=INK, font=font(16*SCALE))
    x = pad; top = head + pad*0.4
    fcap = font(13*SCALE, False)
    for i, (title, sub, col, img) in enumerate(panels):
        sheet.paste(img, (int(x), int(top)))
        d.rounded_rectangle([x-1, top-1, x+PANEL_W+1, top+ph+1], radius=6*SCALE, outline=(58, 62, 72, 255), width=SCALE)
        cy = top + ph + 7*SCALE
        chip(d, x, cy, i+1, title, col)
        d.text((x+30*SCALE, cy+24*SCALE), sub, fill=SUB, font=fcap)
        if i < len(panels)-1:
            ax = x + PANEL_W + arrow*0.18; ay = top + ph/2
            d.text((ax, ay), "→", fill=SUB, font=font(30*SCALE), anchor="lm")
        x += PANEL_W + arrow
    d.text((pad, H-head*0.9), "Drew the controls first? Drift is tiny — this is optional. "
           "Freeform prompt-only? The VLM mask is how the template is built. "
           "(mask/snap overlays schematic)", fill=SUB, font=font(12*SCALE, False))
    sheet = sheet.resize((W//SCALE, H//SCALE), Image.LANCZOS)
    sheet.save(OUT)
    print("wrote", OUT, sheet.size)


if __name__ == "__main__":
    build()
