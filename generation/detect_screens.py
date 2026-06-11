#!/usr/bin/env python3
"""Detect the SCREEN regions in a generated frame by finding large, flat
(low-texture) rectangular areas — screens are uniform panels on a textured
metallic body, dark OR light. This is reliable where LLM box-grounding is not.

Writes <dir>/template.json (display regions only, with live content assigned by
size/position) and <dir>/_screens_overlay.png for verification.

Usage: python3 detect_screens.py public/skins/<id>
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

def detect(path):
    im = Image.open(path).convert("RGBA")
    W, H = im.size
    arr = np.asarray(im).astype(np.float32)
    alpha = arr[..., 3] > 40
    gray = arr[..., :3].mean(2)

    # local texture = local std over a window; screens are FLAT (low std)
    k = max(5, (min(W, H) // 120) | 1)
    mean = ndimage.uniform_filter(gray, k)
    sq = ndimage.uniform_filter(gray * gray, k)
    var = np.clip(sq - mean * mean, 0, None)
    std = np.sqrt(var)

    flat = (std < 7.0) & alpha
    # require the flat area to be notably darker OR lighter than mid (screens
    # are inset glass / paper, not raw mid-grey panel); keeps panels out
    flat &= (gray < 70) | (gray > 200)
    flat = ndimage.binary_opening(flat, iterations=max(1, k // 3))
    flat = ndimage.binary_closing(flat, iterations=max(2, k // 2))

    lbl, n = ndimage.label(flat)
    boxes = []
    minarea = 0.012 * W * H
    for i in range(1, n + 1):
        ys, xs = np.where(lbl == i)
        if xs.size < minarea:
            continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        fill = xs.size / (bw * bh)
        ar = bw / bh
        if fill < 0.62 or ar < 0.25 or ar > 8:
            continue
        boxes.append((x0, y0, bw, bh, xs.size))
    # largest first
    boxes.sort(key=lambda b: -b[4])
    return W, H, boxes

# assign live content by rank (largest = playlist) then position
def assign(boxes):
    out = []
    if not boxes:
        return out
    # playlist = largest
    order = list(boxes)
    pl = order.pop(0)
    out.append((pl, "playlist"))
    # remaining: topmost wide → visualizer, next → marquee, next → time
    rest = sorted(order, key=lambda b: b[1])  # by y (top first)
    roles = ["visualizer", "marquee", "time", "meta"]
    for b, role in zip(rest, roles):
        out.append((b, role))
    return out

def build(dirpath):
    frame = os.path.join(dirpath, "frame.png")
    W, H, boxes = detect(frame)
    assigned = assign(boxes)
    regions = []
    for (x0, y0, bw, bh, _), role in assigned:
        regions.append({
            "id": role, "kind": "display", "content": "dynamic", "layer": "screen",
            "dynamicType": role,
            "rect": {"x": x0 / W, "y": y0 / H, "w": bw / W, "h": bh / H},
        })
    tpl = {"id": os.path.basename(dirpath), "name": "screen-detected",
           "canvas": {"w": W, "h": H}, "regions": regions}
    json.dump(tpl, open(os.path.join(dirpath, "template.json"), "w"), indent=2)

    # overlay for verification
    im = Image.open(frame).convert("RGBA"); bg = Image.new("RGBA", (W, H), (18, 18, 22, 255))
    bg.alpha_composite(im); d = ImageDraw.Draw(bg, "RGBA")
    for (x0, y0, bw, bh, _), role in assigned:
        d.rectangle([x0, y0, x0 + bw, y0 + bh], outline=(0, 255, 180, 255), width=6)
        d.text((x0 + 6, y0 + 6), role, fill=(255, 255, 0))
    bg.convert("RGB").save(os.path.join(dirpath, "_screens_overlay.png"))
    print(os.path.basename(dirpath), "screens:", [(r["dynamicType"]) for r in regions])

if __name__ == "__main__":
    for d in sys.argv[1:]:
        build(d)
