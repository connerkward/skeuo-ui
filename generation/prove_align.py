#!/usr/bin/env python3
"""Alignment PROOF: overlay each template region's rendered shape onto the skin's
actual frame.png, so you can SEE every control box sitting on its painted well.
This is independent of the app — it reads the same normalized rects the runtime
uses and draws them over the real art.

Usage: python3 prove_align.py [<id> ...]   (default: all live skins)
"""
import json, os, sys, glob, math
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "public", "skins")

# colour per role so mismatches are obvious
COL = {
    "play": (80, 255, 120), "pause": (80, 255, 120), "next": (80, 255, 120),
    "prev": (80, 255, 120), "stop": (80, 255, 120), "shuffle": (80, 255, 120),
    "seek": (255, 80, 80), "volume": (90, 170, 255), "balance": (90, 170, 255),
    "eqBand": (255, 200, 60), "eqOn": (255, 200, 60), "mute": (90, 170, 255),
}
DISP = (180, 120, 255)   # screens / visualizer / marquee / time
DEFLT = (200, 200, 200)


def color(r):
    b = r.get("bind")
    if b in COL: return COL[b]
    if r["kind"] in ("display", "marquee") or r.get("dynamicType"): return DISP
    return DEFLT


def overlay(skin_id):
    d = os.path.join(SK, skin_id)
    tpl = json.load(open(os.path.join(d, "template.json")))
    fr = Image.open(os.path.join(d, "frame.png")).convert("RGBA")
    W, H = fr.size
    bg = Image.new("RGBA", (W, H), (24, 24, 26, 255)); bg.alpha_composite(fr)
    im = bg.convert("RGB")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(ov)
    lw = max(2, W // 220)
    for r in tpl["regions"]:
        rc = r["rect"]; x0, y0 = rc["x"]*W, rc["y"]*H; x1, y1 = x0+rc["w"]*W, y0+rc["h"]*H
        c = color(r); ca = c + (255,)
        k = r["kind"]
        if k == "slider-arc" and r.get("arc"):
            a = r["arc"]; i = 0.06*(x1-x0)
            g.arc([x0+i, y0+i, x1-i, y1-i], a["start"], a["end"], fill=ca, width=lw*2)
            g.rectangle([x0, y0, x1, y1], outline=c+(90,), width=lw)
        elif k == "slider-path" and r.get("path"):
            pl = [(x0+p["x"]*(x1-x0), y0+p["y"]*(y1-y0)) for p in r["path"]]
            g.line(pl, fill=ca, width=lw*2, joint="curve")
        elif k in ("slider-h",) or (k == "slider" and rc["w"] >= rc["h"]):
            ym = (y0+y1)/2
            g.line([(x0, ym), (x1, ym)], fill=ca, width=lw*2)          # track
            g.ellipse([x0-lw*2, ym-lw*3, x0+lw*4, ym+lw*3], outline=ca, width=lw)  # thumb at start
            g.rectangle([x0, y0, x1, y1], outline=c+(110,), width=lw)
        elif k == "knob" or (k == "button" and r.get("shape") == "ellipse"):
            g.ellipse([x0, y0, x1, y1], outline=ca, width=lw)
        else:
            rad = 10 if k in ("display", "marquee") else 6
            g.rounded_rectangle([x0, y0, x1, y1], radius=rad, outline=ca, width=lw)
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    out = os.path.join("/tmp", f"align-{skin_id}.png"); im.save(out)
    return out


def sheet(ids):
    cell = 230; per = 6; pad = 6; lblh = 16
    import math as m
    rows = m.ceil(len(ids)/per)
    cw = cell; ch = int(cell*1.5) + lblh
    W = per*(cw+pad)+pad; H = rows*(ch+pad)+pad
    s = Image.new("RGB", (W, H), (12, 12, 14)); dd = ImageDraw.Draw(s)
    try: f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 14)
    except: f = ImageFont.load_default()
    for i, sid in enumerate(ids):
        rr, cc = divmod(i, per); x = pad+cc*(cw+pad); y = pad+rr*(ch+pad)
        try:
            im = Image.open(f"/tmp/align-{sid}.png"); sc = cell/im.width
            im = im.resize((cell, int(im.height*sc)))
            s.paste(im, (x, y+lblh)); dd.text((x+2, y+1), sid, fill=(235,235,240), font=f)
        except Exception as e:
            dd.text((x+2, y+lblh), f"{sid}: {e}", fill=(255,120,120), font=f)
    out = "/Users/conner/Desktop/cc-skeuo/2026-06-15-alignment-proof.png"
    s.save(out); print("SHEET", out, s.size)


if __name__ == "__main__":
    ids = sys.argv[1:] or sorted(
        os.path.basename(os.path.dirname(p)) for p in glob.glob(SK+"/*/template.json")
        if os.path.exists(os.path.join(os.path.dirname(p), "frame.png")))
    for sid in ids:
        try: overlay(sid)
        except Exception as e: print(f"[{sid}] {e}")
    sheet(ids)
