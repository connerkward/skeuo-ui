#!/usr/bin/env python3
"""PROOF (one skin, one control): generate a clean self-contained control sprite —
a toggle switch SET INTO a recessed material-matched bezel — and composite it onto
egypt's frame where the old switch floated, to show it reads as mounted + fits."""
import io, os, time, urllib.request
import numpy as np
from PIL import Image
import generate as G

ROOT = os.path.dirname(G.HERE)
MAT_GOLD = ("shiny polished GOLD pharaoh metal: bright reflective gold/brass with warm specular "
            "highlights, lapis-blue and turquoise inlay accents, soft rounded bevels, museum-piece gilding.")

PROMPT = (
    "Photoreal skeuomorphic hardware UI part on a fully TRANSPARENT background, front-on orthographic, "
    "even studio light, crisp, centered, fills most of the canvas, no text, NO cast shadow outside the part. "
    "A small TOGGLE SWITCH set INTO a RECESSED rectangular mounting bezel: the bezel is a raised beveled "
    "rim around a dark inset slot, and a rounded toggle lever sits in the slot (lever resting). It must read "
    "as a real switch MOUNTED and INSET into a panel — a clean self-contained hardware part, not an object "
    "lying on a surface. Material: " + MAT_GOLD
)


def gen():
    job = G.post("https://queue.fal.run/fal-ai/gpt-image-1.5", {
        "prompt": PROMPT, "image_size": "1024x1024", "quality": "high",
        "background": "transparent", "output_format": "png"})
    su, ru = job["status_url"], job["response_url"]; t0 = time.time()
    while True:
        s = G.get(su).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("FAIL")
        if time.time() - t0 > 300: raise SystemExit("timeout")
        time.sleep(3)
    url = G.get(ru)["images"][0]["url"]
    im = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=120).read())).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    return im.crop(bbox)


def main():
    sw = gen()
    sw.save("/tmp/proof-switch-sprite.png")
    frame = Image.open(f"{ROOT}/public/skins/egypt/frame.png").convert("RGBA")
    W, H = frame.size
    before = frame.copy()
    after = frame.copy()
    # OLD floating positions (from template) vs a sensible mounted home (flank the
    # gold gem/EQ row, on flat gilding)
    homes = [(0.085, 0.40), (0.74, 0.40)]      # left & right flanks, normalized top-left
    sw_w = int(0.14 * W)
    sw_r = sw.resize((sw_w, int(sw_w * sw.height / sw.width)))
    for fx, fy in homes:
        after.alpha_composite(sw_r, (int(fx * W), int(fy * H)))
    # side-by-side
    sheet = Image.new("RGB", (W*2 + 30, H), (22, 22, 24))
    sheet.paste(Image.alpha_composite(Image.new("RGBA",(W,H),(22,22,24,255)), before).convert("RGB"), (10, 0))
    sheet.paste(Image.alpha_composite(Image.new("RGBA",(W,H),(22,22,24,255)), after).convert("RGB"), (W+20, 0))
    out = "/Users/conner/Desktop/cc-skeuo/2026-06-15-switch-proof.png"
    sheet.save(out); print("saved", out)


if __name__ == "__main__":
    main()
