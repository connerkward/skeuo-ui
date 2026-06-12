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
    "frog": {
        "style": "frog", "dest": "frog", "app": "ears", "seed": 11,
        "mat": ("a glossy lime-green rubber cartoon frog-creature toy: smooth candy-shine lobes, darker "
                "green accents, orange dot details, friendly and absurd."),
    },
    "burger": {
        "style": "burger", "dest": "burger", "app": "none", "seed": 31, "rx": 470, "ry": 620,
        "mat": ("a juicy CHEESEBURGER device: toasted sesame-seed bun body, melted cheese dripping between "
                "layers, lettuce frill and tomato edge — appetizing cartoon food-photography style."),
    },
    "bondi": {
        "style": "bondi", "dest": "bondi", "app": "handle", "seed": 17,
        "mat": ("translucent Bondi-blue Y2K plastic (iMac G3 style): see-through gel revealing faint "
                "internal circuit-board silhouettes, silver trim, white specular highlights."),
    },
    "toilet": {
        "style": "toilet", "dest": "toilet", "app": "tank", "seed": 41, "rx": 410, "ry": 580,
        "mat": ("gleaming white porcelain bathroom ceramic with polished chrome flush hardware — yes, a "
                "toilet-shaped music player, played completely straight."),
    },
    "biomech": {
        "style": "biomech", "dest": "biomech", "app": "tendrils", "seed": 13,
        "mat": ("an H.R. Giger biomechanical nightmare: fused bone and sinew, ribbed chitin tubes wrapping "
                "the body, vertebrae ridges, wet organic sheen, sickly green-amber bioluminescence in the "
                "recesses."),
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
    rx = variant.get("rx", 430); ry = variant.get("ry", 660)
    d.polygon(blob_path(W/2, H/2 + 30, rx, ry, 0.16, seed=seed), fill=BODY_FILL, outline=(120, 122, 126))
    app = variant.get("app", "horns" if variant.get("horns") else ("antenna" if variant.get("antenna") else "none"))
    if app == "ears":
        d.ellipse([60, 60, 340, 340], fill=BODY_FILL)                      # ear pods
        d.ellipse([684, 60, 964, 340], fill=BODY_FILL)
        d.ellipse([240, 1380, 440, 1510], fill=BODY_FILL)                  # feet
        d.ellipse([584, 1380, 784, 1510], fill=BODY_FILL)
    elif app == "handle":
        d.rounded_rectangle([322, 30, 702, 250], radius=110, fill=BODY_FILL)   # carry handle arch
        d.rounded_rectangle([402, 90, 622, 190], radius=50, fill=(255, 255, 255))  # handle cutout
    elif app == "tank":
        d.rounded_rectangle([222, 30, 802, 240], radius=30, fill=BODY_FILL)    # cistern tank
        d.rounded_rectangle([262, 6, 462, 70], radius=18, fill=BODY_FILL)      # flush button block
        d.ellipse([282, 1340, 742, 1530], fill=BODY_FILL)                      # base
    elif app == "tendrils":
        for (x0, y0, x1, y1, x2, y2) in [
            (90, 300, -6, 80, 230, 420), (934, 300, 1030, 80, 794, 420),
            (70, 900, -6, 1120, 200, 1010), (954, 900, 1030, 1120, 824, 1010),
            (330, 1330, 240, 1530, 470, 1380), (694, 1330, 784, 1530, 554, 1380)]:
            d.polygon([(x0, y0), (x1, y1), (x2, y2)], fill=BODY_FILL)          # tendril spikes
    if app == "horns" and variant.get("horns", True):
        d.polygon([(230, 480), (60, 60), (430, 280)], fill=BODY_FILL)     # left horn
        d.polygon([(794, 480), (964, 60), (594, 280)], fill=BODY_FILL)    # right horn
        d.polygon([(330, 1300), (260, 1520), (440, 1340)], fill=BODY_FILL)  # feet
        d.polygon([(694, 1300), (764, 1520), (584, 1340)], fill=BODY_FILL)
    if app == "antenna":
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
    "is, same size and shape — empty recessed sockets (controls mount separately) and empty switched-off, "
    "dark glass screens kept as CLEAN FLAT RECTANGLES, never overgrown (no text, no graphics). Make the BODY rich and detailed between the wells: "
    "sculpted curves, panel seams, vents, lights. Everything outside the silhouette stays pure flat "
    "white. Front-on orthographic, even light, high detail. MATERIAL: "
)

def gen(key):
    v = VARIANTS[key]
    seed = v.get("seed", {"pod": 7, "wasp": 23}.get(key, 5))
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
    dest = os.path.join(ROOT, "public", "skins", v.get("dest", f"y2k-{key}"))
    os.makedirs(dest, exist_ok=True)
    urllib.request.urlretrieve(cut, os.path.join(dest, "frame.png"))
    json.dump({"id": v.get("dest", f"y2k-{key}"), "name": "wild-proc", "canvas": {"w": W, "h": H},
               "regions": layout()}, open(os.path.join(dest, "template.json"), "w"), indent=2)
    print(f"[{key}] saved", flush=True)

if __name__ == "__main__":
    keys = sys.argv[1:] or list(VARIANTS.keys())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(gen, keys))
    print("ALL DONE", flush=True)
