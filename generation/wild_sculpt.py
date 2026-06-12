#!/usr/bin/env python3
"""THE ROOT-CAUSE PIPELINE for wild bodies. No detection, no repair, ever.

Split creativity and geometry at the right joint:
  1. gpt-image-2 freely designs only the SILHOUETTE (flat solid shape on
     white — an easy, reliable ask; this is where the wildness comes from).
  2. WE draw the interior deterministically INSIDE that exact mask: screens
     and wells are fitted to the silhouette band-by-band (widest interior span
     per band), so every coordinate is known and everything fits the shape.
  3. Nano Banana paints the material over the blueprint (layout-preserving).
  4. The SAME mask becomes the alpha — no BiRefNet, no holes, no guessing.
  5. The template is emitted from the drawn coordinates.

Usage: python3 wild_sculpt.py <id> <style> "<silhouette brief>"
"""
import json, os, sys, time, urllib.request
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import generate as G

ROOT = os.path.dirname(G.HERE)
W, H = 1024, 1536
WELL = (20, 22, 24)
EDGE = (74, 78, 82)
BODY = (174, 176, 180)

SIL_PROMPT = (
    "A single flat solid DARK-GRAY SILHOUETTE shape on a pure white background: the outline of {brief}. "
    "Completely flat fill, no interior detail, no shading, no outline strokes — just the filled "
    "silhouette, centered, filling most of the canvas. COMPOSITION RULE: the shape is dominated by ONE "
    "large solid rounded TORSO mass (at least two thirds of the shape's area, wide in the middle AND "
    "lower half); all the wild parts — horns, fins, tendrils, legs, spikes — grow outward from the "
    "torso's edge and stay relatively small. Bold, readable, wildly non-rectangular outline."
)

MATERIAL = {
    "biomech": ("H.R. Giger biomechanical nightmare: fused bone and sinew, ribbed chitin tubes wrapping "
                "the body, vertebrae ridges, wet organic sheen, sickly green-amber bioluminescence "
                "glowing from the recesses."),
    "winamp":  ("polished chrome and brushed gunmetal over dark charcoal plastic, thin green LED accent "
                "lines tracing the curves, tiny screws."),
    "frog":    ("glossy moulded rubber toy-frog skin in vivid green with subtle mottling, bulging "
                "highlights, bright orange plastic hardware accents."),
    "burger":  ("photoreal fast-food materials: toasted sesame-seed bun, drippy melted cheddar, ruffled "
                "lettuce, glossy ketchup beads, kraft-paper accents."),
    "bondi":   ("translucent grape-purple Y2K plastic with visible internals and circuit shadows "
                "glowing through, frosted white trim, soft backlight."),
    "toilet":  ("gleaming white glazed porcelain with soft studio reflections, polished chrome "
                "hardware, faint blue ceramic shadowing."),
}

STYLE_PROMPT = (
    "Restyle this blueprint into a photoreal, wildly-shaped skeuomorphic MP3-player device. CRITICAL: "
    "keep the EXACT silhouette, and keep EVERY dark recessed well and screen EXACTLY where it is, same "
    "size and shape — every recessed well stays a DEEP DARK EMPTY socket: a near-black matte cavity "
    "with a crisp raised rim, NOTHING mounted inside, NOT glowing, NOT filled with material; and empty "
    "switched-off dark glass screens kept as CLEAN FLAT RECTANGLES (no text, no graphics, never "
    "overgrown). Make the body rich and detailed BETWEEN the wells. Everything outside the silhouette stays pure white. Front-on "
    "orthographic, even light, high detail. MATERIAL: "
)

def gen_silhouette(brief, out_id, sil_path=None):
    if sil_path:                                     # reuse a known silhouette
        tmp = sil_path
    else:
        job = G.post("https://queue.fal.run/openai/gpt-image-2", {
            "prompt": SIL_PROMPT.format(brief=brief),
            "image_size": {"width": W, "height": H}, "quality": "medium", "output_format": "png"})
        t0 = time.time()
        while True:
            s = G.get(job["status_url"]).get("status")
            if s == "COMPLETED": break
            if s in ("FAILED", "ERROR"): raise SystemExit("silhouette FAIL")
            if time.time() - t0 > 420: raise SystemExit("timeout")
            time.sleep(3)
        url = G.get(job["response_url"])["images"][0]["url"]
        # per-id temp file — concurrent runs must not race on a shared name
        tmp = os.path.join(G.HERE, f"_sil-{out_id}.png"); urllib.request.urlretrieve(url, tmp)
    im = Image.open(tmp).convert("L").resize((W, H))
    mask = np.asarray(im) < 200                      # dark shape on white
    mask = ndimage.binary_fill_holes(mask)
    lbl, n = ndimage.label(mask)                     # keep largest component
    if n > 1:
        sizes = ndimage.sum(mask, lbl, range(1, n + 1))
        mask = lbl == (1 + int(np.argmax(sizes)))
    print(f"silhouette ok ({mask.mean()*100:.0f}% of canvas)", flush=True)
    return mask

def max_rect(B):
    """Largest axis-aligned rectangle of True cells in 2D bool array B.
    Returns (x, y, w, h) in B's coordinates. Histogram-stack, O(rows*cols)."""
    rows, cols = B.shape
    h = np.zeros(cols, dtype=int)
    best = (0, 0, 0, 0); barea = 0
    for y in range(rows):
        h = (h + 1) * B[y]
        stack = []
        x = 0
        while x <= cols:
            cur = h[x] if x < cols else 0
            if not stack or cur >= h[stack[-1]]:
                stack.append(x); x += 1
            else:
                ti = stack.pop()
                height = h[ti]
                left = (stack[-1] + 1) if stack else 0
                width = x - left
                if width * height > barea:
                    barea = width * height
                    best = (left, y - height + 1, width, height)
    return best

def layout_in_mask(mask):
    """Fit the control layout inside the silhouette, band by band."""
    core = ndimage.binary_erosion(mask, iterations=14)   # keep off the rim
    # Lay out within the TORSO span — rows where the body is actually wide.
    # Fixed fractions of total height land the top bands on horns/heads and
    # the bottom ones on legs; the torso is where the UI lives.
    rs = core.sum(1)
    rows = np.nonzero(rs >= 0.5 * rs.max())[0]
    top, bot = rows.min(), rows.max()
    Hc = bot - top
    regs = []
    def add(id, kind, x, y, w, h, **kw):
        regs.append({"id": id, "kind": kind,
                     "content": kw.pop("content", "sprite"),
                     "layer": kw.pop("layer", "components"),
                     "rect": {"x": x/W, "y": y/H, "w": w/W, "h": h/H}, **kw})
    def band(f0, f1, max_h=None):
        """Largest inscribed rectangle within the fractional window [f0,f1]."""
        yA, yB = int(top + Hc*f0), int(top + Hc*f1)
        x, y, w, h = max_rect(core[yA:yB])
        y += yA
        if max_h and h > max_h:          # center a capped-height strip in it
            y += (h - max_h) // 2; h = max_h
        return x, y, x + w, y + h
    # visualizer
    x0, y0, x1, y1 = band(0.02, 0.24)
    add("visualizer", "display", x0+8, y0, (x1-x0)-16, y1-y0, content="dynamic", layer="screen", dynamicType="visualizer")
    # marquee strip
    x0, y0, x1, y1 = band(0.24, 0.31, max_h=40)
    add("marquee", "display", x0+8, y0, (x1-x0)-16, y1-y0, content="dynamic", layer="screen", dynamicType="marquee")
    # transport row: 5 buttons + 2 switch wells
    x0, y0, x1, y1 = band(0.31, 0.43, max_h=82)
    span = x1-x0-16; bx = x0+8
    bw = span/8.2
    for i, b in enumerate(["prev", "play", "pause", "stop", "next"]):
        add(b, "button", bx + i*bw*1.12, y0, bw, y1-y0, bind=b, label=b)
    swx = bx + 5*bw*1.12 + bw*0.35
    for i, (bind, lab) in enumerate([("shuffle", "SHUF"), ("eqOn", "EQ")]):
        add(f"sw{i}", "toggle", swx + i*bw*1.05, y0-6, bw*0.92, (y1-y0)+12, bind=bind, label=lab)
    # knobs + EQ slots
    x0, y0, x1, y1 = band(0.42, 0.58, max_h=150)
    span = x1-x0-16; bx = x0+8
    kd = min(y1-y0, span*0.16)
    add("knob0", "knob", bx, y0+( (y1-y0)-kd)/2, kd, kd, bind="volume", label="VOL")
    add("knob1", "knob", x0+8+span-kd, y0+((y1-y0)-kd)/2, kd, kd, bind="balance", label="BAL")
    sx = bx + kd + span*0.045
    ex = x0+8+span-kd - span*0.045
    sw_ = (ex-sx)/6
    for i in range(6):
        add(f"eq{i}", "slider-v", sx + i*sw_ + sw_*0.28, y0, sw_*0.44, y1-y0,
            bind="eqBand", group="eq-bands", index=i, label="")
    # seek groove
    x0, y0, x1, y1 = band(0.58, 0.64, max_h=34)
    add("seek", "slider-h", x0+10, y0, (x1-x0)-20, y1-y0, bind="seek", label="Seek")
    # playlist
    x0, y0, x1, y1 = band(0.64, 0.99)
    add("playlist", "display", x0+8, y0, (x1-x0)-16, y1-y0, content="dynamic", layer="screen", dynamicType="playlist")
    return regs

def draw_blueprint(mask, regs):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    body = np.asarray(img).copy()
    body[mask] = BODY
    img = Image.fromarray(body)
    d = ImageDraw.Draw(img)
    for r in regs:
        rc = r["rect"]; x0, y0 = rc["x"]*W, rc["y"]*H; x1, y1 = x0+rc["w"]*W, y0+rc["h"]*H
        if r["kind"] == "knob":
            d.ellipse([x0, y0, x1, y1], fill=WELL, outline=EDGE, width=4)
        elif r["kind"] == "display":
            d.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=(12, 13, 15), outline=EDGE, width=5)
        else:
            d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=WELL, outline=EDGE, width=4)
    return img

def usable(regs):
    """Hard gate: the layout must have real screens, or the silhouette is rejected."""
    d = {r["id"]: r["rect"] for r in regs if r["kind"] == "display"}
    return (d["playlist"]["w"] >= 0.30 and d["playlist"]["h"] >= 0.12 and
            d["visualizer"]["w"] >= 0.24 and d["visualizer"]["h"] >= 0.06)

def main(out_id, style, brief, sil_path=None):
    for attempt in range(3):
        mask = gen_silhouette(brief, out_id, sil_path); sil_path = None
        regs = layout_in_mask(mask)
        if usable(regs):
            break
        print(f"[{out_id}] silhouette unusable (screens too small) — retry {attempt+1}", flush=True)
    else:
        raise SystemExit("no usable silhouette in 3 attempts")
    bp = draw_blueprint(mask, regs)
    bp_path = os.path.join(G.HERE, f"_sculpt-{out_id}.png"); bp.save(bp_path)
    cu = G.upload(bp_path)
    job = G.submit(cu, STYLE_PROMPT + MATERIAL.get(style, MATERIAL["winamp"]))
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("style FAIL")
        if time.time() - t0 > 500: raise SystemExit("timeout")
        time.sleep(4)
    url = G.get(job["response_url"])["images"][0]["url"]
    print(f"[{out_id}] styled {time.time()-t0:.0f}s", flush=True)
    tmp = os.path.join(G.HERE, f"_sculpt-{out_id}-out.png"); urllib.request.urlretrieve(url, tmp)
    styled = Image.open(tmp).convert("RGBA").resize((W, H))
    # OUR mask is the alpha — soft edge via 1px blur of the mask
    a = Image.fromarray((mask*255).astype(np.uint8)).convert("L")
    styled.putalpha(a)
    dest = os.path.join(ROOT, "public", "skins", out_id); os.makedirs(dest, exist_ok=True)
    styled.save(os.path.join(dest, "frame.png"))
    json.dump({"id": out_id, "name": "wild-sculpt", "canvas": {"w": W, "h": H}, "regions": regs},
              open(os.path.join(dest, "template.json"), "w"), indent=2)
    print(f"[{out_id}] saved (alignment by construction)", flush=True)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
