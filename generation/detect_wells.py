#!/usr/bin/env python3
"""Pixel-accurate WELL + SCREEN detection for wild bodies — replaces the loose
LLM grounding. Wells are dark recessed shapes on the body; screens are the two
largest dark rects. Classification by geometry:

  aspect >= 2.8           → slider-h (the long groove)
  aspect <= 0.45          → slider-v (EQ slot)
  ~square, low bbox-fill  → knob (circle fills ~0.78 of its bbox)
  ~square/rect, high fill → button; the largest same-row cluster = transport,
                            leftovers = toggles

Writes template.json + _overlay.png per dir. Usage: detect_wells.py <dir>...
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

TRANSPORT = ["prev", "play", "pause", "stop", "next", "eject"]

def detect(path):
    im = Image.open(path).convert("RGBA")
    W, H = im.size
    arr = np.asarray(im).astype(np.float32)
    alpha = arr[..., 3] > 40
    gray = arr[..., :3].mean(2)
    dark = (gray < 105) & alpha
    dark = ndimage.binary_opening(dark, iterations=2)
    lbl, n = ndimage.label(dark)
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.where(lbl == i)
        a = xs.size
        if a < 0.0006 * W * H:           # specks / rivets
            continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        comps.append({"x": int(x0), "y": int(y0), "w": int(bw), "h": int(bh),
                      "area": int(a), "fill": a / (bw * bh)})
    comps.sort(key=lambda c: -c["area"])
    screens = [c for c in comps if c["area"] > 0.02 * W * H][:2]
    wells = [c for c in comps if c not in screens and c["fill"] > 0.45]
    return W, H, screens, wells

def classify(wells):
    out = []
    for c in wells:
        ar = c["w"] / c["h"]
        if ar >= 2.8: kind = "slider-h"
        elif ar <= 0.45: kind = "slider-v"
        elif c["fill"] < 0.86 and 0.6 <= ar <= 1.6: kind = "knob"
        else: kind = "button"
        out.append({**c, "kind": kind})
    return out

def build(dirpath):
    frame = os.path.join(dirpath, "frame.png")
    W, H, screens, wells = detect(frame)
    wells = classify(wells)
    regions = []
    # screens: largest = playlist, other = visualizer (topmost)
    scr = sorted(screens, key=lambda c: -c["area"])
    roles = ["playlist", "visualizer"]
    if len(scr) == 2 and scr[1]["y"] > scr[0]["y"]:
        scr = [scr[0], scr[1]]  # keep largest=playlist regardless of order
    for c, role in zip(scr, roles):
        regions.append({"id": role, "kind": "display", "content": "dynamic", "layer": "screen",
                        "dynamicType": role,
                        "rect": {"x": c["x"]/W, "y": c["y"]/H, "w": c["w"]/W, "h": c["h"]/H}})
    R = lambda c: {"x": c["x"]/W, "y": c["y"]/H, "w": c["w"]/W, "h": c["h"]/H}
    # buttons → row clustering: biggest y-cluster is the transport row
    btns = [c for c in wells if c["kind"] == "button"]
    rows = {}
    for c in btns:
        key = round((c["y"] + c["h"]/2) / (0.03 * H))
        rows.setdefault(key, []).append(c)
    transport = sorted(max(rows.values(), key=len), key=lambda c: c["x"]) if rows else []
    toggles = sorted([c for c in btns if c not in transport], key=lambda c: c["x"])
    for i, c in enumerate(transport[:6]):
        b = TRANSPORT[i]
        regions.append({"id": b, "kind": "button", "content": "sprite", "layer": "components",
                        "bind": b, "label": b, "rect": R(c)})
    for i, c in enumerate(toggles[:3]):
        bind = ["shuffle", "eqOn", "mute"][i]
        regions.append({"id": f"sw{i}", "kind": "toggle", "content": "sprite", "layer": "components",
                        "bind": bind, "label": ["SHUF", "EQ", "MUTE"][i], "rect": R(c)})
    knobs = sorted([c for c in wells if c["kind"] == "knob"], key=lambda c: c["x"])
    for i, c in enumerate(knobs[:2]):
        regions.append({"id": f"knob{i}", "kind": "knob", "content": "sprite", "layer": "components",
                        "bind": ["volume", "balance"][i], "label": ["VOL", "BAL"][i], "rect": R(c)})
    slvs = sorted([c for c in wells if c["kind"] == "slider-v"], key=lambda c: c["x"])
    for i, c in enumerate(slvs):
        regions.append({"id": f"eq{i}", "kind": "slider-v", "content": "sprite", "layer": "components",
                        "bind": "eqBand", "group": "eq-bands", "index": i, "label": "", "rect": R(c)})
    slh = sorted([c for c in wells if c["kind"] == "slider-h"], key=lambda c: -c["w"])
    for c in slh[:1]:
        regions.append({"id": "seek", "kind": "slider-h", "content": "sprite", "layer": "components",
                        "bind": "seek", "label": "Seek", "rect": R(c)})
    tpl = {"id": os.path.basename(dirpath), "name": "wild-y2k", "canvas": {"w": W, "h": H}, "regions": regions}
    json.dump(tpl, open(os.path.join(dirpath, "template.json"), "w"), indent=2)
    # overlay
    im = Image.open(frame).convert("RGBA")
    bg = Image.new("RGBA", (W, H), (18, 18, 22, 255)); bg.alpha_composite(im)
    d = ImageDraw.Draw(bg, "RGBA")
    col = {"button": (59,130,246), "toggle": (34,197,94), "slider-h": (245,158,11),
           "slider-v": (168,85,247), "knob": (236,72,153), "display": (14,165,233)}
    for r in regions:
        rc = r["rect"]; x0, y0 = rc["x"]*W, rc["y"]*H; x1, y1 = x0+rc["w"]*W, y0+rc["h"]*H
        d.rectangle([x0, y0, x1, y1], outline=col[r["kind"]]+(255,), width=5)
    bg.convert("RGB").save(os.path.join(dirpath, "_overlay.png"))
    counts = {}
    for r in regions: counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    print(os.path.basename(dirpath), counts, flush=True)

if __name__ == "__main__":
    for d in sys.argv[1:]:
        build(d)
