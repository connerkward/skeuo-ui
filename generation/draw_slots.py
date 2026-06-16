#!/usr/bin/env python3
"""Show the LITERAL output of the slot-drawing algorithm.

The runtime positions every control with pct() in Composite.tsx:
    left: x*100%   top: y*100%   width: w*100%   height: h*100%
i.e. a plain rectangle at the region's normalized rect. This script draws THAT
exact rectangle (no arc/ellipse interpretation) over the real frame.png, so you
see precisely where each slot lands on the painted art. Every box here is one
`div` the app renders.

Usage: python3 draw_slots.py [<id> ...]      (default: all live skins)
"""
import json, os, sys, glob, math
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "public", "skins")
OUT = "/Users/conner/Desktop/cc-skeuo"
os.makedirs(OUT, exist_ok=True)

# bright colours for the interactive controls (what the user cares about),
# dim grey for the screen/visualizer/decoration regions.
CTRL = {"button": (90, 255, 130), "toggle": (255, 120, 60), "knob": (90, 180, 255),
        "slider-h": (255, 70, 70), "slider-v": (255, 210, 60),
        "slider-arc": (255, 70, 70), "slider-path": (255, 70, 70),
        "segmented": (200, 120, 255), "xy": (120, 220, 220)}
DIM = (110, 110, 120)


def font(sz):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        try: return ImageFont.truetype(p, sz)
        except: pass
    return ImageFont.load_default()


def overlay(skin_id):
    d = os.path.join(SK, skin_id)
    tpl = json.load(open(os.path.join(d, "template.json")))
    fr = Image.open(os.path.join(d, "frame.png")).convert("RGBA")
    W, H = fr.size
    bg = Image.new("RGBA", (W, H), (20, 20, 22, 255)); bg.alpha_composite(fr)
    im = bg.convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(ov)
    lw = max(2, W // 200)
    f = font(max(14, W // 50))
    # draw dim regions first, controls on top
    regs = sorted(tpl["regions"], key=lambda r: r["kind"] in CTRL)
    # collapse the EQ band cluster to ONE label so the 5 sliders don't pile up
    eq = [r for r in regs if (r.get("bind") == "eqBand")]
    eq_first = eq[0]["id"] if eq else None
    for r in regs:
        rc = r["rect"]
        x0, y0 = rc["x"] * W, rc["y"] * H
        x1, y1 = x0 + rc["w"] * W, y0 + rc["h"] * H
        ctrl = r["kind"] in CTRL
        c = CTRL.get(r["kind"], DIM)
        w = lw if ctrl else max(1, lw // 2)
        g.rectangle([x0, y0, x1, y1], fill=(c + (45,)) if ctrl else None,
                    outline=c + (255,), width=w)
        if not ctrl:
            continue
        if r.get("bind") == "eqBand" and r["id"] != eq_first:
            continue  # only label the cluster once
        lab = "eqBand×%d" % len(eq) if r.get("bind") == "eqBand" else (r.get("bind") or r.get("id") or r["kind"])
        tb = g.textbbox((0, 0), lab, font=f)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        ly = max(0, y0 - th - 6)
        g.rectangle([x0, ly, x0 + tw + 8, ly + th + 6], fill=(0, 0, 0, 220))
        g.text((x0 + 4, ly + 1), lab, fill=c + (255,), font=f)
    im = Image.alpha_composite(im, ov).convert("RGB")
    im.save(os.path.join("/tmp", f"slots-{skin_id}.png"))
    im.save(os.path.join(OUT, f"slots-{skin_id}.png"))   # full-res, openable
    return os.path.join("/tmp", f"slots-{skin_id}.png")


def sheet(ids):
    cell = 360; per = 6; pad = 8; lblh = 20
    rows = math.ceil(len(ids) / per)
    ch = int(cell * 1.5) + lblh
    W = per * (cell + pad) + pad; Ht = rows * (ch + pad) + pad
    s = Image.new("RGB", (W, Ht), (12, 12, 14)); dd = ImageDraw.Draw(s)
    f = font(15)
    for i, sid in enumerate(ids):
        rr, cc = divmod(i, per); x = pad + cc * (cell + pad); y = pad + rr * (ch + pad)
        try:
            im = Image.open(f"/tmp/slots-{sid}.png"); sc = cell / im.width
            im = im.resize((cell, int(im.height * sc)))
            s.paste(im, (x, y + lblh)); dd.text((x + 2, y + 2), sid, fill=(235, 235, 240), font=f)
        except Exception as e:
            dd.text((x + 2, y + lblh), f"{sid}: {e}", fill=(255, 120, 120), font=f)
    out = os.path.join(OUT, "2026-06-16-slot-algorithm-output.png")
    s.save(out); print("SHEET", out, s.size)
    return out


if __name__ == "__main__":
    ids = sys.argv[1:] or sorted(
        os.path.basename(os.path.dirname(p)) for p in glob.glob(SK + "/*/template.json")
        if os.path.exists(os.path.join(os.path.dirname(p), "frame.png"))
        and os.path.basename(os.path.dirname(p)) not in ("winamp", "toilet"))
    for sid in ids:
        try: overlay(sid)
        except Exception as e: print(f"[{sid}] {e}")
    sheet(ids)
