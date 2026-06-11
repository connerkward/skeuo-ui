#!/usr/bin/env python3
"""Generate STATEFUL CONTROL SPRITES per skin — the layered workflow's middle
layer. Controls are real AI-rendered sprites with states, composited live by
React (not CSS approximations, not baked into the faceplate):

  switch  → ONE image, the SAME switch twice side-by-side (lever DOWN | lever
            UP). Split at the midline → switch-off.png / switch-on.png. Same
            design, two states: toggling swaps actual art.
  knob    → one sprite, pointer straight up → React rotates it (CSS transform).
  button  → one blank embossed face → glyph/label overlaid live; press is a
            transform of the same sprite.
  thumb   → fader cap sprite, dragged along a channel.

gpt-image-1.5 t2i with background:"transparent" gives clean RGBA sprites.
Saves to public/skins/<id>/sprites/. Usage: python3 gen_sprites.py [skins...]
"""
import io, json, os, sys, time, urllib.request, concurrent.futures
from PIL import Image
import generate as G

ROOT = os.path.dirname(G.HERE)

BASE = (
    "Photoreal skeuomorphic hardware UI part on a fully TRANSPARENT background, front-on orthographic, "
    "even studio light, crisp, centered, fills most of the canvas, no text, no shadow cast outside the part. "
)

MAT = {
    "winamp":     "Late-90s Winamp hardware: brushed gunmetal, dark charcoal plastic, polished chrome bevel, green LED accents.",
    "fallout":    "Fallout Pip-Boy / RobCo industrial: scuffed olive-drab metal, worn paint, rivets, amber-green monochrome accents.",
    "fantasy":    "Baldur's Gate fantasy artifact: carved gray-green stone, ornate gold filigree rim, faceted amber gem, brass.",
    "aqua":       "Mac OS X Aqua: glossy translucent candy-blue gel and white glass over brushed aluminium, bright top highlight.",
    "hifi":       "1970s hi-fi receiver: knurled brushed-aluminium, silver, black pointer markings, warm amber pilot-lamp accents.",
    "papercraft": "Hand-made papercraft: folded kraft cardboard and cut paper, matte, visible creases, red/teal marker accents.",
}

# per-style switch DESIGNS — distinct hardware, not one archetype recolored
SWITCH_DESC = {
    "winamp":     "a small rectangular chrome toggle switch on a brushed plate with a tiny green LED window below the lever",
    "fallout":    "a big industrial KNIFE-SWITCH: bakelite handle on a riveted scuffed metal plate with an amber indicator lamp",
    "fantasy":    "an ornate gold lever with a faceted gem tip, mounted on a small carved stone plaque with gold trim",
    "aqua":       "a glossy aqua-gel ROCKER switch: translucent candy-blue pill in a white glass frame, glows when on",
    "hifi":       "a rectangular silver paddle switch on a brushed-aluminium plate with engraved ON/OFF dots and a small amber lamp",
    "papercraft": "a cut-paper TAB sliding in a cardboard slot, red marker dot indicator, visible fold creases",
}

ASSETS = {
    "switch": (
        "TWO STATES of the SAME switch side by side with a clear gap: LEFT copy in the OFF position "
        "(lever/handle DOWN, indicator unlit), RIGHT copy is the IDENTICAL switch in the ON position "
        "(lever/handle UP, indicator lit). Identical plate size, identical vertical position. The switch: "
        "{sw}. {mat}"
    ),
    "knob": (
        "A single round rotary knob CAP only, perfectly circular, viewed dead-on from the front. NO base "
        "plate, NO panel, NO tick marks, NO mounting ring, NO shadow — JUST the circular knob itself. "
        "Radially symmetric design and shading, lit evenly from directly above (so it can rotate "
        "naturally), with ONE clear high-contrast pointer line from the center to the edge pointing "
        "STRAIGHT UP. {mat}"
    ),
    "button": (
        "A single blank rectangular pressable BUTTON face with beveled edges, slightly rounded corners, no "
        "label, no icon. {mat}"
    ),
    "thumb": (
        "A single small fader SLIDER CAP / thumb (the grabbable part of a mixing-desk fader), horizontal "
        "ridge grip. {mat}"
    ),
}

def gen(skin, asset, prompt):
    job = G.post("https://queue.fal.run/fal-ai/gpt-image-1.5", {
        "prompt": prompt, "image_size": "1024x1024", "quality": "medium",
        "background": "transparent", "output_format": "png",
    })
    su, ru = job["status_url"], job["response_url"]
    t0 = time.time()
    while True:
        s = G.get(su).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): print(f"[{skin}/{asset}] FAIL", flush=True); return None
        if time.time() - t0 > 420: print(f"[{skin}/{asset}] timeout", flush=True); return None
        time.sleep(3)
    url = G.get(ru)["images"][0]["url"]
    data = urllib.request.urlopen(url, timeout=120).read()
    return Image.open(io.BytesIO(data)).convert("RGBA")

def trim(im, pad=6):
    bbox = im.getchannel("A").getbbox()
    if not bbox: return im
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(im.width, x1 + pad); y1 = min(im.height, y1 + pad)
    return im.crop((x0, y0, x1, y1))

ONLY_ASSETS = [a for a in os.environ.get("ASSETS", "").split(",") if a]

def do_skin(skin):
    out = os.path.join(ROOT, "public", "skins", skin, "sprites")
    os.makedirs(out, exist_ok=True)
    mat = MAT[skin]
    def one(asset):
        if ONLY_ASSETS and asset not in ONLY_ASSETS: return
        im = gen(skin, asset, BASE + ASSETS[asset].format(mat=mat, sw=SWITCH_DESC.get(skin, "a flip switch")))
        if im is None: return
        if asset == "switch":
            # split the pair, then ALIGN the two states on the plate (anchor =
            # alpha centroid of the bottom 40%, identical between states) and
            # paste onto one shared canvas size → the plate is pixel-fixed when
            # toggling; only the lever moves.
            import numpy as np
            mid = im.width // 2
            halves = [im.crop((0, 0, mid, im.height)), im.crop((mid, 0, im.width, im.height))]
            anchors, bboxes = [], []
            for h in halves:
                a = np.asarray(h)[..., 3].astype(np.float32); a[a < 60] = 0
                ys, xs = np.nonzero(a)
                y0b = ys.min() + int((ys.max() - ys.min()) * 0.6)
                sel = ys >= y0b; w = a[ys[sel], xs[sel]]
                anchors.append((float((xs[sel] * w).sum() / w.sum()), float((ys[sel] * w).sum() / w.sum())))
                bboxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
            bw = max(b[2] - b[0] for b in bboxes) + 24
            bh = max(b[3] - b[1] for b in bboxes) + 24
            # common anchor target: same relative spot in both outputs
            ax = bw // 2
            ay = int(bh * 0.78)
            names = ["switch-off.png", "switch-on.png"]
            for h, (cx, cy), name in zip(halves, anchors, names):
                cv = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
                cv.paste(h, (int(ax - cx), int(ay - cy)), h)
                cv.save(os.path.join(out, name))
        elif asset == "knob":
            # enforce a circular sprite: center square crop + circle alpha mask,
            # so NOTHING square/panel-like can rotate with the cap
            im = trim(im, pad=0)
            side = min(im.size)
            cx, cy = im.width // 2, im.height // 2
            im = im.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2))
            from PIL import ImageDraw as _ID
            mask = Image.new("L", im.size, 0)
            _ID.Draw(mask).ellipse([0, 0, im.width - 1, im.height - 1], fill=255)
            a = im.getchannel("A").point(lambda v: v)  # copy
            im.putalpha(Image.composite(a, Image.new("L", im.size, 0), mask))
            im.save(os.path.join(out, "knob.png"))
        else:
            trim(im).save(os.path.join(out, f"{asset}.png"))
        print(f"[{skin}] {asset} ok", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(one, ASSETS.keys()))

def main():
    skins = sys.argv[1:] or list(MAT.keys())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(do_skin, skins))
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
