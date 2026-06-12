#!/usr/bin/env python3
"""Molded transport-button sprites: the icon is part of the hardware, not a
font overlay — a play button must READ as a play button in the skin's own
material. One sheet of five round buttons per style, split by alpha into the
five faces, each centered square. Saves sprites/btn-{prev,play,pause,stop,next}.png.

Usage: python3 gen_buttons.py [styles...]
"""
import io, os, sys, time, urllib.request
import numpy as np
from PIL import Image
from scipy import ndimage
import generate as G
from gen_sprites import MAT

ROOT = os.path.dirname(G.HERE)
ORDER = ["prev", "play", "pause", "stop", "next"]

SHEET = (
    "Photoreal skeuomorphic hardware: FIVE separate identical ROUND push-buttons in ONE horizontal row, "
    "evenly spaced with clear gaps, all the same diameter, on a fully TRANSPARENT background, front-on "
    "orthographic, even studio light, no shadow cast outside the buttons. Each button face carries ONE "
    "deeply MOLDED, embossed media-transport icon as part of the physical material (no printed text): "
    "1st SKIP-BACK (left-pointing triangle against a vertical bar), 2nd PLAY (right-pointing triangle), "
    "3rd PAUSE (two vertical bars), 4th STOP (solid square), 5th SKIP-FORWARD (right-pointing triangle "
    "against a vertical bar). The icons must be bold, large and unmistakable. STYLE: {mat}"
)

def gen_sheet(style):
    job = G.post("https://queue.fal.run/fal-ai/gpt-image-1.5", {
        "prompt": SHEET.format(mat=MAT[style]), "image_size": "1536x1024",
        "quality": "high", "background": "transparent", "output_format": "png",
    })
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): return None
        if time.time() - t0 > 420: return None
        time.sleep(3)
    url = G.get(job["response_url"])["images"][0]["url"]
    data = urllib.request.urlopen(url, timeout=120).read()
    return Image.open(io.BytesIO(data)).convert("RGBA")

def _square(crop):
    side = max(crop.width, crop.height) + 12
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    return sq.resize((512, 512), Image.LANCZOS)

def split_buttons(im):
    """Split a row of five buttons by the COLUMN-ALPHA PROFILE: find a valley
    (gap between buttons) near each ideal 1/5..4/5 boundary and cut there.
    Robust to organic styles whose buttons BRIDGE — the gap is a local minimum,
    not necessarily zero — and to uneven spacing, where blind equal-fifths would
    slice a button in half. Always yields five faces (or None if sheet is empty)."""
    bb = im.getchannel("A").getbbox()
    if not bb: return None
    bx0, by0, bx1, by1 = bb
    sub = im.crop((bx0, by0, bx1, by1))
    a = np.asarray(sub)[..., 3] > 24
    n = a.shape[1]
    if n < 50: return None
    col = a.sum(0).astype(float)
    k = max(3, n // 120)
    col = np.convolve(col, np.ones(k) / k, mode="same")   # smooth out texture noise
    splits = []
    for i in range(1, 5):                                  # valley near each boundary
        c = int(n * i / 5); w = max(4, int(n * 0.08))
        lo, hi = max(1, c - w), min(n - 1, c + w)
        splits.append(lo + int(np.argmin(col[lo:hi])))
    bounds = [0] + splits + [n]
    out = []
    for i in range(5):
        seg = sub.crop((bounds[i], 0, bounds[i + 1], a.shape[0]))
        sa = np.asarray(seg)[..., 3] > 24
        cl, cn = ndimage.label(sa)
        if cn:                                             # keep this button, drop neighbour slivers
            keep = 1 + int(np.argmax(ndimage.sum(sa, cl, range(1, cn + 1))))
            arr = np.asarray(seg).copy(); arr[cl != keep, 3] = 0
            seg = Image.fromarray(arr)
        cb = seg.getchannel("A").getbbox()
        if not cb: return None
        out.append(_square(seg.crop(cb)))
    return out

def do_style(style):
    for attempt in range(2):
        sheet = gen_sheet(style)
        if sheet is None: continue
        faces = split_buttons(sheet)
        if faces: break
        print(f"[{style}] sheet split != 5 buttons — retry", flush=True)
    else:
        print(f"[{style}] FAILED", flush=True); return
    dest = os.path.join(ROOT, "public", "skins", style, "sprites")
    os.makedirs(dest, exist_ok=True)
    for name, face in zip(ORDER, faces):
        face.save(os.path.join(dest, f"btn-{name}.png"))
    print(f"[{style}] saved 5 molded buttons", flush=True)

if __name__ == "__main__":
    import concurrent.futures
    styles = sys.argv[1:] or ["winamp", "frog", "burger", "bondi", "toilet", "biomech"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(do_style, styles))
