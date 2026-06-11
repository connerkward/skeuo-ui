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

ASSETS = {
    "switch": (
        "TWO STATES of the SAME chunky retro flip switch (toggle lever in a recessed slot plate), side by "
        "side with a clear gap: LEFT copy lever flipped DOWN = OFF (indicator unlit), RIGHT copy IDENTICAL "
        "switch lever flipped UP = ON (indicator lit). Identical size, identical position height. {mat}"
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
        im = gen(skin, asset, BASE + ASSETS[asset].format(mat=mat))
        if im is None: return
        if asset == "switch":
            mid = im.width // 2
            trim(im.crop((0, 0, mid, im.height))).save(os.path.join(out, "switch-off.png"))
            trim(im.crop((mid, 0, im.width, im.height))).save(os.path.join(out, "switch-on.png"))
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
