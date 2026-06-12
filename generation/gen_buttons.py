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

def split_buttons(im):
    """Alpha connected components, x-sorted — robust to uneven spacing."""
    a = np.asarray(im)[..., 3] > 24
    lbl, n = ndimage.label(ndimage.binary_closing(a, iterations=3))
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lbl == i)
        if xs.size < 2000: continue
        comps.append((xs.min(), xs.max(), ys.min(), ys.max(), xs.size))
    comps.sort(key=lambda c: -c[4])
    comps = sorted(comps[:5], key=lambda c: c[0])
    if len(comps) != 5:
        # organic styles bridge neighbours into one blob — fall back to five
        # equal columns over the sheet's alpha bbox, trimming each by alpha
        bb = im.getchannel("A").getbbox()
        if not bb: return None
        bx0, by0, bx1, by1 = bb
        cw = (bx1 - bx0) / 5
        out = []
        for i in range(5):
            cell = im.crop((int(bx0 + i*cw), by0, int(bx0 + (i+1)*cw), by1))
            ca = np.asarray(cell)[..., 3] > 24
            cl, cn = ndimage.label(ca)
            if cn == 0: return None
            keep = 1 + int(np.argmax(ndimage.sum(ca, cl, range(1, cn + 1))))
            arr = np.asarray(cell).copy(); arr[cl != keep, 3] = 0   # drop neighbour slivers
            cell = Image.fromarray(arr)
            cb = cell.getchannel("A").getbbox()
            crop = cell.crop(cb)
            side = max(crop.width, crop.height) + 12
            sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            sq.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
            out.append(sq.resize((512, 512), Image.LANCZOS))
        return out
    out = []
    for x0, x1, y0, y1, _ in comps:
        crop = im.crop((x0, y0, x1 + 1, y1 + 1))
        side = max(crop.width, crop.height) + 12
        sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        sq.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
        out.append(sq.resize((512, 512), Image.LANCZOS))
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
