#!/usr/bin/env python3
"""DETERMINISTIC wild bodies — alignment by construction, nothing guessed.

We DRAW the wild silhouette and every mounting well procedurally at exact
coordinates (PIL), hand that blueprint to Nano Banana to paint the MATERIAL
(it preserves layout), cut the white background (BiRefNet), and emit the
template from the very coordinates we drew. So:
  - every well gets exactly its control, sized to the well
  - knob wells are circles the knob sprite fills and pivots in
  - switch wells match the switch sprite aspect (tall)
  - slider grooves are the real, full travel
No CV, no LLM grounding, no mismatch possible.

Usage: python3 wild_proc.py [pod|wasp]
"""
import json, math, os, sys, time, urllib.request, concurrent.futures
from PIL import Image, ImageDraw
import generate as G

ROOT = os.path.dirname(G.HERE)
W, H = 1024, 1536

BODY_FILL = (172, 174, 178)
WELL = (22, 24, 26)
WELL_EDGE = (78, 80, 84)

VARIANTS = {
    "pod": {
        "style": "winamp", "name": "Y2K Pod ✦",
        "mat": ("late-90s Winamp-skin hardware: polished chrome and brushed gunmetal with dark plastic "
                "inserts, green LED accent strips along the fins, tiny screws."),
        "horns": True, "antenna": False,
    },
    "wasp": {
        "style": "fallout", "name": "Rust Wasp ✦",
        "mat": ("scuffed olive-drab riveted metal, retro-industrial RobCo style: worn paint, rivets along "
                "the edges, amber-green accents, a small stencilled roundel on the lower hull."),
        "horns": False, "antenna": True,
    },
}

# ---------- the shared internal layout (exact, reused for the template) ----------
def layout():
    regs = []
    def add(id, kind, x, y, w, h, **kw):
        regs.append({"id": id, "kind": kind, "content": kw.pop("content", "sprite"),
                     "layer": kw.pop("layer", "components"),
                     "rect": {"x": x / W, "y": y / H, "w": w / W, "h": h / H}, **kw})
    # screens
    add("visualizer", "display", 262, 250, 500, 170, content="dynamic", layer="screen", dynamicType="visualizer")
    add("playlist",   "display", 232, 900, 560, 300, content="dynamic", layer="screen", dynamicType="playlist")
    add("marquee",    "display", 262, 444, 500, 40,  content="dynamic", layer="screen", dynamicType="marquee")
    # transport row (5)
    bx, by, bw, bh, gap = 252, 530, 88, 72, 14
    for i, b in enumerate(["prev", "play", "pause", "stop", "next"]):
        add(b, "button", bx + i * (bw + gap), by, bw, bh, bind=b, label=b)
    # knobs (2, round wells)
    add("knob0", "knob", 282, 640, 110, 110, bind="volume", label="VOL")
    add("knob1", "knob", 632, 640, 110, 110, bind="balance", label="BAL")
    # EQ slots (6) between the knobs
    sx, sy, sw, sh, sgap = 422, 632, 22, 126, 12
    for i in range(6):
        add(f"eq{i}", "slider-v", sx + i * (sw + sgap), sy, sw, sh,
            bind="eqBand", group="eq-bands", index=i, label="")
    # seek groove
    add("seek", "slider-h", 252, 800, 520, 26, bind="seek", label="Seek")
    # switches (2, tall wells matching the switch sprite aspect)
    add("sw0", "toggle", 822, 530, 64, 96, bind="shuffle", label="SHUF")
    add("sw1", "toggle", 822, 650, 64, 96, bind="eqOn", label="EQ")
    return regs

# ---------- procedural silhouette ----------
def blob_path(cx, cy, rx, ry, wobble, n=24, seed=7):
    import random
    rnd = random.Random(seed)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1 + wobble * (rnd.random() - 0.5)
        pts.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r))
    return pts

def draw_blueprint(variant, seed):
    img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    # body: big wobbly blob covering the layout area
    d.polygon(blob_path(W/2, H/2 + 30, 430, 660, 0.16, seed=seed), fill=BODY_FILL, outline=(120, 122, 126))
    # appendages
    if variant["horns"]:
        d.polygon([(230, 480), (60, 60), (430, 280)], fill=BODY_FILL)     # left horn
        d.polygon([(794, 480), (964, 60), (594, 280)], fill=BODY_FILL)    # right horn
        d.polygon([(330, 1300), (260, 1520), (440, 1340)], fill=BODY_FILL)  # feet
        d.polygon([(694, 1300), (764, 1520), (584, 1340)], fill=BODY_FILL)
    if variant["antenna"]:
        d.rectangle([740, 80, 790, 420], fill=BODY_FILL)                  # antenna stalk
        d.ellipse([700, 20, 830, 140], fill=BODY_FILL)                    # antenna bulb
        d.ellipse([70, 560, 260, 940], fill=BODY_FILL)                    # side pod
        d.polygon([(400, 1300), (350, 1520), (480, 1330)], fill=BODY_FILL)
        d.polygon([(624, 1300), (674, 1520), (544, 1330)], fill=BODY_FILL)
    # wells at EXACT layout coords
    for r in layout():
        rc = r["rect"]; x0, y0 = rc["x"]*W, rc["y"]*H; x1, y1 = x0+rc["w"]*W, y0+rc["h"]*H
        if r["kind"] == "knob":
            d.ellipse([x0, y0, x1, y1], fill=WELL, outline=WELL_EDGE, width=4)
        elif r["kind"] == "display":
            d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=(12, 13, 15), outline=WELL_EDGE, width=5)
        else:
            d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=WELL, outline=WELL_EDGE, width=4)
    return img

PROMPT = (
    "Restyle this blueprint into a photoreal, wildly-shaped Y2K skeuomorphic MP3-player device. "
    "CRITICAL: keep the EXACT silhouette and keep EVERY dark recessed well and screen EXACTLY where it "
    "is, same size and shape — empty recessed sockets (controls mount separately) and empty switched-off "
    "dark glass screens (no text, no graphics). Make the BODY rich and detailed between the wells: "
    "sculpted curves, panel seams, vents, lights. Everything outside the silhouette stays pure flat "
    "white. Front-on orthographic, even light, high detail. MATERIAL: "
)

def gen(key):
    v = VARIANTS[key]
    seed = {"pod": 7, "wasp": 23}[key]
    bp = draw_blueprint(v, seed)
    bp_path = os.path.join(G.HERE, f"wildproc-{key}.png")
    bp.save(bp_path)
    cu = G.upload(bp_path)
    job = G.submit(cu, PROMPT + v["mat"])
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit(f"{key} FAIL")
        if time.time() - t0 > 500: raise SystemExit("timeout")
        time.sleep(4)
    url = G.get(job["response_url"])["images"][0]["url"]
    print(f"[{key}] styled {time.time()-t0:.0f}s", flush=True)
    # cutout
    job = G.post("https://queue.fal.run/fal-ai/birefnet/v2", {
        "image_url": url, "model": "General Use (Heavy)",
        "operating_resolution": "2048x2048", "refine_foreground": True, "output_format": "png"})
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("cutout FAIL")
        if time.time() - t0 > 300: raise SystemExit("cutout timeout")
        time.sleep(3)
    cut = G.get(job["response_url"])["image"]["url"]
    dest = os.path.join(ROOT, "public", "skins", f"y2k-{key}")
    os.makedirs(dest, exist_ok=True)
    urllib.request.urlretrieve(cut, os.path.join(dest, "frame.png"))
    json.dump({"id": f"y2k-{key}", "name": "wild-proc", "canvas": {"w": W, "h": H},
               "regions": layout()}, open(os.path.join(dest, "template.json"), "w"), indent=2)
    print(f"[{key}] saved", flush=True)

if __name__ == "__main__":
    keys = sys.argv[1:] or list(VARIANTS.keys())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(gen, keys))
    print("ALL DONE", flush=True)
