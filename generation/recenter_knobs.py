#!/usr/bin/env python3
"""Re-center every knob sprite on its ALPHA CENTROID (the disc center) so CSS
rotation — which pivots on the image center — pivots exactly on the disc.
Prints the residual offset per knob (must be ~0). Idempotent."""
import os, sys
import numpy as np
from PIL import Image, ImageDraw

def recenter(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)[..., 3].astype(np.float32)
    a[a < 60] = 0                              # drop halo/shadow
    ys, xs = np.nonzero(a)
    wsum = a[ys, xs]
    cx = float((xs * wsum).sum() / wsum.sum())
    cy = float((ys * wsum).sum() / wsum.sum())
    # radius: 99.5th percentile distance (robust to stray pixels)
    d = np.hypot(xs - cx, ys - cy)
    r = float(np.percentile(d, 99.5)) + 2
    side = int(2 * r)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(im, (int(side / 2 - cx), int(side / 2 - cy)), im)
    # circle mask centered on the canvas (= disc center now)
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, side - 1, side - 1], fill=255)
    alpha = out.getchannel("A")
    out.putalpha(Image.composite(alpha, Image.new("L", (side, side), 0), mask))
    out.save(path)
    # verify: recompute centroid offset from canvas center
    a2 = np.asarray(out)[..., 3].astype(np.float32); a2[a2 < 60] = 0
    ys2, xs2 = np.nonzero(a2); w2 = a2[ys2, xs2]
    ox = (xs2 * w2).sum() / w2.sum() - side / 2
    oy = (ys2 * w2).sum() / w2.sum() - side / 2
    print(f"{path}: residual centroid offset ({ox:+.2f}, {oy:+.2f}) px of {side}px")

if __name__ == "__main__":
    skins = sys.argv[1:] or ["winamp", "fallout", "fantasy", "aqua", "hifi", "papercraft"]
    for s in skins:
        p = f"public/skins/{s}/sprites/knob.png"
        if os.path.exists(p): recenter(p)
