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
# transport button size hierarchy (× base diameter) — PLAY dominates, stop is
# smallest. Breaks the uniform-small-grid look the user flagged.
BSIZE = {"play": 1.5, "pause": 1.0, "prev": 0.9, "next": 0.9, "stop": 0.82}

SIL_PROMPT = (
    "A single flat solid DARK-GRAY SILHOUETTE shape on a pure white background: the outline of {brief}. "
    "Completely flat fill, no interior detail, no shading, no outline strokes — just the filled "
    "silhouette, centered, filling most of the canvas. The PROPORTION and posture must follow the brief — "
    "it may be tall and narrow, squat and wide, asymmetric, leaning, angular/geometric or organic; do NOT "
    "default to a generic centered rounded blob, make the OVERALL shape distinctive. COMPOSITION RULE "
    "(for fit only): somewhere in the shape there is ONE large CONTIGUOUS mass — at least half the area, "
    "tall enough and wide enough to seat stacked screens — and the wild parts (horns, fins, tendrils, "
    "legs, spikes, blades, claws) grow outward from it. Bold, readable, wildly non-rectangular outline."
)

MATERIAL = {
    "biomech": ("H.R. Giger biomechanical nightmare: fused bone and sinew, ribbed chitin tubes wrapping "
                "the body, vertebrae ridges, wet organic sheen, sickly green-amber bioluminescence "
                "glowing from the recesses."),
    "manray":  ("a chubby cartoon BABY creature: smooth glossy CERULEAN-BLUE skin, two oversized round "
                "BRIGHT-RED goggle eyes, a simple RED diaper-and-cape costume across the lower body, soft "
                "round baby proportions, clean friendly cel-shaded cartoon look, a thin red glow from the "
                "control recesses. Match the palette and character of the reference image."),
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
    # divergent body-horror materials — same theme family as biomech, different flesh
    "flesh":   ("wet anatomical body horror: exposed crimson muscle fiber and sinew, glistening "
                "vein networks, stretched translucent skin membranes, pale bone plates and teeth "
                "as hardware accents."),
    "chitin":  ("glossy black insect carapace with an iridescent oil-slick sheen, segmented "
                "armor plates, serrated edges, deep crimson bioluminescence pulsing in the seams."),
    "fungal":  ("pale sickly fungal mass: cordyceps stalks, layered gill ridges, swollen spore "
                "sacs, fibrous mycelium webbing, faint amber glow seeping between growths."),
    "wmp":     ("Windows Media Player 9 / XP Luna capsule hardware: glossy silver-white plastic "
                "shells, translucent aqua-blue gel inlays, polished chrome trim rings, soft blue "
                "gradients, subtle green LED accents."),
    "halo":    ("Halo 2 UNSC military hardware: olive-drab armored metal plating with scuffed "
                "edges, hex bolts, vents, layered angular armor ridges, amber-orange holographic "
                "tick marks and warning chevrons glowing from recesses."),
    # cute tomato — plump glossy ripe-tomato body, leafy stem crown, fresh & friendly
    "tomato":  ("a cute plump ripe TOMATO: glossy waxy tomato-red skin with dewy soft-box "
                "highlights and subtle deeper-red mottling, a fresh green leafy calyx stem crown on "
                "top, friendly rounded chubby form, bright spring-green glossy plastic hardware "
                "accents, clean and adorable."),
    # Mexico soccer (NO humans) — El Tri tricolor + football paneling, gold crest accents
    "mexico":  ("Mexico national football (soccer) theme, ABSOLUTELY NO people or figures: bold "
                "green-white-red tricolor panels, classic black-and-white soccer-ball pentagon "
                "paneling, stitched leather and athletic jersey-mesh fabric textures, a golden "
                "embroidered eagle crest emblem, polished gold trophy-metal hardware accents, "
                "stadium-floodlit sheen."),
}

STYLE_PROMPT = (
    "Restyle this blueprint into a photoreal, wildly-shaped skeuomorphic MP3-player device. CRITICAL: "
    "keep the EXACT silhouette, and keep EVERY dark recessed well and screen EXACTLY where it is, same "
    "size and shape — every recessed well stays a DEEP DARK EMPTY socket: a near-black matte cavity "
    "with a crisp raised rim, NOTHING mounted inside, NOT glowing, NOT filled with material; and every "
    "screen — INCLUDING the thin marquee strip — stays switched-off NEAR-BLACK glass, a CLEAN FLAT "
    "RECTANGLE never tinted or overgrown by the body material (no text, no graphics). Make the body rich and detailed BETWEEN the wells. Everything outside the silhouette stays pure white. Front-on "
    "orthographic, even light, high detail. MATERIAL: "
)

def gen_silhouette(brief, out_id, sil_path=None):
    if sil_path:                                     # reuse a known silhouette
        tmp = sil_path
    else:
        # Silhouette is a pure text-to-image ask — feeding a (rectangular) UI
        # reference here would flatten the wild shape, so references belong to
        # the PAINT pass (gen_styled), not here.
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

ENVELOPE_PROMPT = (
    "Keep every dark control socket, round well, ring groove and dark screen EXACTLY where it is, "
    "pixel-identical, unchanged. Around and BEHIND them, paint ONE flat solid dark-gray SILHOUETTE "
    "shape on the pure white background: the outline of {brief}. If a REFERENCE image is provided, "
    "the silhouette MUST closely follow that reference character's distinctive OUTLINE — its head "
    "shape, body proportions, ears/horns, arms, legs, tail and pose — NOT a generic rounded blob. "
    "The silhouette must still fully CONTAIN every socket and screen with margin; grow/inflate the "
    "reference's body where needed so the controls fit inside it. Completely flat dark-gray fill, no "
    "interior detail, no shading, no outline strokes. Everything else stays pure white."
)

def layout_radial():
    """Layout-FIRST radial template (no mask yet — the body is generated
    around it): round dial, buttons orbiting the lower rim, knobs as eyes,
    and the SEEK as a RING riding the dial's upper arc."""
    import math
    regs = []
    def add(id, kind, x, y, w, h, **kw):
        regs.append({"id": id, "kind": kind,
                     "content": kw.pop("content", "sprite"),
                     "layer": kw.pop("layer", "components"),
                     "rect": {"x": x/W, "y": y/H, "w": w/W, "h": h/H}, **kw})
    cx, cy, r = W/2, H*0.287, W*0.21
    d = 64.0
    rg = r - d - 12                      # dial glass radius
    rc = rg + 8 + d/2                    # orbit/ring radius
    add("visualizer", "display", cx-rg, cy-rg, 2*rg, 2*rg,
        content="dynamic", layer="screen", dynamicType="visualizer", shape="ellipse")
    # asymmetric hierarchy: PLAY dominates, stop is smallest — the center stays
    # on the ring (placed by center − bd/2) so varying size keeps it aligned
    for ang, b in zip([150, 120, 90, 60, 30], ["prev", "play", "pause", "stop", "next"]):
        a = math.radians(ang); bd = d * BSIZE[b]
        add(b, "button", cx + rc*math.cos(a) - bd/2, cy + rc*math.sin(a) - bd/2, bd, bd,
            bind=b, label=b, shape="ellipse")
    kd = 72.0
    for ang, (kid, bind, lab) in zip([205, 335], [("knob0", "volume", "VOL"), ("knob1", "balance", "BAL")]):
        a = math.radians(ang)
        add(kid, "knob", cx + rc*math.cos(a) - kd/2, cy + rc*math.sin(a) - kd/2, kd, kd, bind=bind, label=lab)
    side = 2*(rc + 14)                   # seek ring: upper arc of the same radius
    add("seek", "slider-arc", cx-side/2, cy-side/2, side, side,
        bind="seek", label="Seek", arc={"start": 212, "end": 328})
    my = cy + r + 16
    add("marquee", "display", W*0.18, my, W*0.64, 38, content="dynamic", layer="screen", dynamicType="marquee")
    ey, eh = my + 56, 130
    ex0, span = W*0.17, W*0.66
    sww = 42.0
    add("sw0", "toggle", ex0, ey+8, sww, eh-16, bind="shuffle", label="SHUF")
    add("sw1", "toggle", ex0+span-sww, ey+8, sww, eh-16, bind="eqOn", label="EQ")
    sx, exx = ex0 + sww + span*0.05, ex0 + span - sww - span*0.05
    sw_ = (exx-sx)/6
    for i in range(6):
        add(f"eq{i}", "slider-v", sx + i*sw_ + sw_*0.28, ey, sw_*0.44, eh,
            bind="eqBand", group="eq-bands", index=i, label="")
    py = ey + eh + 28
    add("playlist", "display", W*0.19, py, W*0.62, H*0.945 - py, content="dynamic", layer="screen", dynamicType="playlist")
    return regs

def layout_capsule():
    """WMP9-capsule grammar: dial pod on the LEFT with buttons fully RINGING
    it (no linear row anywhere), a chrome pill marquee sweeping right, a seek
    ring around the whole pod, playlist + EQ in the lower body."""
    import math
    regs = []
    def add(id, kind, x, y, w, h, **kw):
        regs.append({"id": id, "kind": kind,
                     "content": kw.pop("content", "sprite"),
                     "layer": kw.pop("layer", "components"),
                     "rect": {"x": x/W, "y": y/H, "w": w/W, "h": h/H}, **kw})
    cx, cy, r = W*0.30, H*0.235, W*0.205
    d = 56.0
    rg = r - d - 12
    rc = rg + 6 + d/2
    add("visualizer", "display", cx-rg, cy-rg, 2*rg, 2*rg,
        content="dynamic", layer="screen", dynamicType="visualizer", shape="ellipse")
    # buttons FULLY around the dial; the gap at 0 deg is where the pill attaches
    ring = [(40, "next"), (88, "stop"), (136, "pause"), (184, "play"), (232, "prev")]
    for ang, b in ring:
        a = math.radians(ang); bd = d * BSIZE[b]
        add(b, "button", cx + rc*math.cos(a) - bd/2, cy + rc*math.sin(a) - bd/2, bd, bd,
            bind=b, label=b, shape="ellipse")
    for ang, (kid, bind, lab) in zip([280, 322], [("sw0", "shuffle", "SHUF"), ("sw1", "eqOn", "EQ")]):
        a = math.radians(ang)
        add(kid, "toggle", cx + rc*math.cos(a) - d*0.42, cy + rc*math.sin(a) - d*0.55,
            d*0.84, d*1.1, bind=bind, label=lab)
    rOut = rc + d/2 + 16                 # seek ring OUTSIDE the button ring
    side = 2*(rOut + 12)
    add("seek", "slider-arc", cx-side/2, cy-side/2, side, side,
        bind="seek", label="Seek", arc={"start": 60, "end": 300})
    # chrome pill marquee sweeping right from the pod
    px0 = cx + rOut + 26
    add("marquee", "display", px0, cy-36, W*0.95 - px0, 72, content="dynamic", layer="screen", dynamicType="marquee")
    # knobs tucked under the pill
    kd = 76.0
    add("knob0", "knob", px0 + 30, cy + 64, kd, kd, bind="volume", label="VOL")
    add("knob1", "knob", px0 + 30 + kd + 28, cy + 64, kd, kd, bind="balance", label="BAL")
    # EQ row
    ey, eh = H*0.475, 124
    ex0, span = W*0.20, W*0.60
    sw_ = span/6
    for i in range(6):
        add(f"eq{i}", "slider-v", ex0 + i*sw_ + sw_*0.30, ey, sw_*0.40, eh,
            bind="eqBand", group="eq-bands", index=i, label="")
    add("playlist", "display", W*0.185, H*0.575, W*0.63, H*0.355, content="dynamic", layer="screen", dynamicType="playlist")
    return regs

def layout_minimal():
    """STRIPPED-DOWN grammar — the user asked for a 'minimized type' that does
    not use every control. A now-playing PUCK: round dial (radial spectrum +
    clock), one horizontal seek, three buttons (a dominant PLAY flanked by small
    prev/next), one VOLUME knob, a marquee. No EQ, no playlist, no toggles, no
    balance — deliberately sparse."""
    regs = []
    def add(id, kind, x, y, w, h, **kw):
        regs.append({"id": id, "kind": kind,
                     "content": kw.pop("content", "sprite"),
                     "layer": kw.pop("layer", "components"),
                     "rect": {"x": x/W, "y": y/H, "w": w/W, "h": h/H}, **kw})
    cx, cy, rg = W/2, H*0.255, W*0.185
    add("visualizer", "display", cx-rg, cy-rg, 2*rg, 2*rg,
        content="dynamic", layer="screen", dynamicType="visualizer", shape="ellipse")
    sy = cy + rg + 30                              # horizontal seek under the dial
    add("seek", "slider-h", W*0.23, sy, W*0.54, 28, bind="seek", label="Seek")
    by = sy + 96                                    # transport row, PLAY dominant
    play_d, small_d, gap = 132.0, 78.0, 44.0
    add("play", "button", cx-play_d/2, by-play_d/2, play_d, play_d, bind="play", label="play", shape="ellipse")
    add("prev", "button", cx-play_d/2-gap-small_d, by-small_d/2, small_d, small_d, bind="prev", label="prev", shape="ellipse")
    add("next", "button", cx+play_d/2+gap, by-small_d/2, small_d, small_d, bind="next", label="next", shape="ellipse")
    ky = by + play_d/2 + 40                         # one volume knob
    kd = 96.0
    add("knob0", "knob", cx-kd/2, ky, kd, kd, bind="volume", label="VOL")
    my = ky + kd + 32                               # marquee at the foot
    add("marquee", "display", W*0.19, my, W*0.62, 50, content="dynamic", layer="screen", dynamicType="marquee")
    return regs

def layout_manray():
    """Man Ray (SpongeBob villain): a wide manta-ray HEAD over a torso chassis.
    A wide rectangular VISUALIZER in the flat head, a novel zigzag 'bolt' SCRUB
    across the chest (rect well; the lightning path is drawn live by the React
    renderer), and a sparse transport — SHUFFLE toggle · dominant PLAY · NEXT."""
    regs = []
    def add(id, kind, x, y, w, h, **kw):
        regs.append({"id": id, "kind": kind,
                     "content": kw.pop("content", "sprite"),
                     "layer": kw.pop("layer", "components"),
                     "rect": {"x": x/W, "y": y/H, "w": w/W, "h": h/H}, **kw})
    cx = W/2
    # leave the UPPER head (top ~18%) free for the character's big eyes — the
    # visualizer sits on the chest below the face, not over the eyes
    vw, vh = W*0.54, H*0.120
    add("visualizer", "display", cx-vw/2, H*0.255, vw, vh,
        content="dynamic", layer="screen", dynamicType="visualizer")
    # marquee strip under the visualizer
    add("marquee", "display", cx-W*0.30, H*0.395, W*0.60, 46,
        content="dynamic", layer="screen", dynamicType="marquee")
    # NOVEL 'bolt' scrub — a rect well; React draws a zigzag path
    sw, sh = W*0.62, H*0.085
    add("seek", "slider-path", cx-sw/2, H*0.46, sw, sh, bind="seek", label="Seek")
    # transport: SHUFFLE toggle · PLAY (dominant) · NEXT
    by = H*0.62
    play_d = W*0.205
    add("play", "button", cx-play_d/2, by, play_d, play_d, bind="play", label="play", shape="ellipse")
    nd = W*0.115
    add("next", "button", cx+play_d/2+W*0.055, by+(play_d-nd)/2, nd, nd, bind="next", label="next", shape="ellipse")
    tw, th = W*0.17, H*0.072
    add("shuffle", "toggle", cx-play_d/2-W*0.055-tw, by+(play_d-th)/2, tw, th, bind="shuffle", label="SHUF")
    return regs

def covers(mask, regs):
    """Every control/screen must sit fully inside the enveloping body."""
    import math
    core = ndimage.binary_erosion(mask, iterations=6)
    for r in regs:
        rc = r["rect"]
        if r["kind"] == "slider-arc":    # ring: sample points along the arc
            ccx, ccy = (rc["x"]+rc["w"]/2)*W, (rc["y"]+rc["h"]/2)*H
            rr = rc["w"]*W/2 * 0.88
            a0, a1 = r["arc"]["start"], r["arc"]["end"]
            for t in range(21):
                a = math.radians(a0 + (a1-a0)*t/20)
                x, y = int(ccx + rr*math.cos(a)), int(ccy + rr*math.sin(a))
                if not core[max(0, min(H-1, y)), max(0, min(W-1, x))]: return False
            continue
        x0, y0 = int(rc["x"]*W), int(rc["y"]*H)
        x1, y1 = int((rc["x"]+rc["w"])*W), int((rc["y"]+rc["h"])*H)
        if not core[max(0, y0):min(H, y1), max(0, x0):min(W, x1)].all(): return False
    return True

def region_mask(regs):
    """Boolean mask of every drawn region (the layout is part of the body
    BY CONSTRUCTION — teeth/jaws painted over a screen must not cut holes)."""
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    for r in regs:
        rc = r["rect"]; x0, y0 = rc["x"]*W, rc["y"]*H; x1, y1 = x0+rc["w"]*W, y0+rc["h"]*H
        if r["kind"] == "slider-arc":
            i = 0.06*(x1-x0)
            d.arc([x0+i, y0+i, x1-i, y1-i], r["arc"]["start"], r["arc"]["end"], fill=255, width=26)
        else:
            d.rectangle([x0, y0, x1, y1], fill=255)
    return ndimage.binary_dilation(np.asarray(img) > 0, iterations=10)

def gen_envelope(wells_img, brief, out_id, ref_urls=None):
    tmp = os.path.join(G.HERE, f"_wells-{out_id}.png"); wells_img.save(tmp)
    cu = G.upload(tmp)
    # ref_urls (the reference character) steer the SHAPE of the grown silhouette so
    # it follows the reference's outline instead of a generic blob
    job = G.submit(cu, ENVELOPE_PROMPT.format(brief=brief), ref_urls or [])
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): return None
        if time.time() - t0 > 420: return None
        time.sleep(3)
    url = G.get(job["response_url"])["images"][0]["url"]
    out = os.path.join(G.HERE, f"_env-{out_id}.png"); urllib.request.urlretrieve(url, out)
    im = Image.open(out).convert("L").resize((W, H))
    mask = ndimage.binary_fill_holes(np.asarray(im) < 200)
    lbl, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, lbl, range(1, n + 1))
        mask = lbl == (1 + int(np.argmax(sizes)))
    print(f"[{out_id}] envelope ok ({mask.mean()*100:.0f}% of canvas)", flush=True)
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

def layout_in_mask(mask, variant="classic"):
    """Fit a control layout inside the silhouette, band by band.

    Variants (all alignment-by-construction, all gated by usable()):
      classic — the stacked rectangle layout
      hero    — one BIG round play button center-stage, round prev/stop/pause/
                next flanking it, switches at the band's outer edges
      flank   — knobs sit beside the visualizer like eyes; the five transport
                buttons are round and ride a downward arc
    """
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
        """Largest inscribed rectangle within the fractional window [f0,f1].
        Degenerate windows return a sentinel rect that fails usable()."""
        yA = max(int(top + Hc*f0), 0)
        yB = min(int(top + Hc*f1), core.shape[0])
        if yB - yA < 6:
            return 0, yA, 40, yA + 8
        x, y, w, h = max_rect(core[yA:yB])
        if w < 40 or h < 8:
            return 0, yA, 40, yA + 8
        y += yA
        if max_h and h > max_h:          # center a capped-height strip in it
            y += (h - max_h) // 2; h = max_h
        return x, y, x + w, y + h

    def screens_and_seek(vis_box, marq_f, seek_f, pl_f):
        x0, y0, x1, y1 = vis_box
        add("visualizer", "display", x0+8, y0, (x1-x0)-16, y1-y0, content="dynamic", layer="screen", dynamicType="visualizer")
        x0, y0, x1, y1 = band(*marq_f, max_h=40)
        add("marquee", "display", x0+8, y0, (x1-x0)-16, y1-y0, content="dynamic", layer="screen", dynamicType="marquee")
        x0, y0, x1, y1 = band(*seek_f, max_h=34)
        add("seek", "slider-h", x0+10, y0, (x1-x0)-20, y1-y0, bind="seek", label="Seek")
        x0, y0, x1, y1 = band(*pl_f)
        add("playlist", "display", x0+8, y0, (x1-x0)-16, y1-y0, content="dynamic", layer="screen", dynamicType="playlist")

    def knobs_eq(f0, f1, knobs=True, sw_edges=False):
        x0, y0, x1, y1 = band(f0, f1, max_h=150)
        span = x1-x0-16; bx = x0+8; bH = y1-y0
        used_l, used_r = bx, x0+8+span
        if knobs:
            kd = min(bH, span*0.16)
            add("knob0", "knob", bx, y0+(bH-kd)/2, kd, kd, bind="volume", label="VOL")
            add("knob1", "knob", x0+8+span-kd, y0+(bH-kd)/2, kd, kd, bind="balance", label="BAL")
            used_l, used_r = bx+kd, x0+8+span-kd
        if sw_edges:
            sww = min(bH*0.55, span*0.085)
            add("sw0", "toggle", used_l + span*0.012, y0+bH*0.06, sww, bH*0.88, bind="shuffle", label="SHUF")
            add("sw1", "toggle", used_r - span*0.012 - sww, y0+bH*0.06, sww, bH*0.88, bind="eqOn", label="EQ")
            used_l += sww + span*0.03; used_r -= sww + span*0.03
        sx = used_l + span*0.045
        ex = used_r - span*0.045
        sw_ = (ex-sx)/6
        for i in range(6):
            add(f"eq{i}", "slider-v", sx + i*sw_ + sw_*0.28, y0, sw_*0.44, bH,
                bind="eqBand", group="eq-bands", index=i, label="")

    if variant == "orbit":
        # the reference-skin move: a round dial screen with controls ORBITING
        # it. Largest inscribed circle in the upper torso = the dial.
        # distance transform of the WHOLE core, padded so the canvas edge
        # counts as outside (a slice would let the dial poke past the body)
        dt = ndimage.distance_transform_edt(np.pad(core, 1))[1:-1, 1:-1]
        win = dt[top:top + int(Hc*0.55)]
        # TOPMOST circle big enough for the dial — the global max sits mid-
        # torso and starves the marquee/EQ/playlist below it
        target = min(W*0.21, float(win.max())) * 0.96
        cys, cxs = np.nonzero(win >= target)
        row = cys.min()
        cx = float(np.median(cxs[cys == row]))
        cy = float(top + row)
        r = float(dt[top + row, int(cx)])
        r = min(r, W*0.22, (top + Hc*0.52) - cy)   # keep the lower half free
        d = max(34, min(r*0.30, 72))          # orbiting button diameter
        rg = r - d - 12                        # dial glass radius
        rc = rg + 8 + d/2                      # orbit radius for button centers
        add("visualizer", "display", cx-rg, cy-rg, 2*rg, 2*rg,
            content="dynamic", layer="screen", dynamicType="visualizer", shape="ellipse")
        import math
        for ang, b in zip([150, 120, 90, 60, 30], ["prev", "play", "pause", "stop", "next"]):
            a = math.radians(ang); bd = d * BSIZE[b]
            bx = cx + rc*math.cos(a) - bd/2
            by = cy + rc*math.sin(a) - bd/2     # y-down: bottom semicircle
            add(b, "button", bx, by, bd, bd, bind=b, label=b, shape="ellipse")
        kd = min(d*1.15, max(30.0, (r - rc)*1.9))
        for ang, (kid, bind, lab) in zip([205, 335], [("knob0", "volume", "VOL"), ("knob1", "balance", "BAL")]):
            a = math.radians(ang)
            add(kid, "knob", cx + rc*math.cos(a) - kd/2, cy + rc*math.sin(a) - kd/2,
                kd, kd, bind=bind, label=lab)
        fdb = (cy + r - top)/Hc                # fraction where the dial ends
        x0, y0, x1, y1 = band(fdb + 0.005, fdb + 0.075, max_h=38)
        add("marquee", "display", x0+8, y0, (x1-x0)-16, y1-y0, content="dynamic", layer="screen", dynamicType="marquee")
        knobs_eq(fdb + 0.075, fdb + 0.205, knobs=False, sw_edges=True)
        x0, y0, x1, y1 = band(fdb + 0.205, fdb + 0.26, max_h=30)
        add("seek", "slider-h", x0+10, y0, (x1-x0)-20, y1-y0, bind="seek", label="Seek")
        x0, y0, x1, y1 = band(fdb + 0.26, 0.99)
        add("playlist", "display", x0+8, y0, (x1-x0)-16, y1-y0, content="dynamic", layer="screen", dynamicType="playlist")
    elif variant == "hero":
        # [sw] [prev][stop] ((PLAY)) [pause][next] [sw] — one center-stage button
        screens_and_seek(band(0.02, 0.22), (0.22, 0.28), (0.60, 0.66), (0.66, 0.99))
        x0, y0, x1, y1 = band(0.28, 0.46)
        span = x1-x0; bH = y1-y0; cx = (x0+x1)/2; cy = (y0+y1)/2
        D = min(bH, span*0.20)
        d = D*0.60; gap = d*0.22
        add("play", "button", cx-D/2, cy-D/2, D, D, bind="play", label="play", shape="ellipse")
        for i, b in enumerate(["stop", "prev"]):
            add(b, "button", cx-D/2 - (i+1)*(d+gap), cy-d/2, d, d, bind=b, label=b, shape="ellipse")
        for i, b in enumerate(["pause", "next"]):
            add(b, "button", cx+D/2 + gap + i*(d+gap), cy-d/2, d, d, bind=b, label=b, shape="ellipse")
        sww = min(bH*0.62, span*0.085)
        add("sw0", "toggle", x0+8, cy-bH*0.40, sww, bH*0.80, bind="shuffle", label="SHUF")
        add("sw1", "toggle", x1-8-sww, cy-bH*0.40, sww, bH*0.80, bind="eqOn", label="EQ")
        knobs_eq(0.46, 0.60)
    elif variant == "flank":
        # knobs flank the visualizer like eyes; round transport rides an arc
        x0, y0, x1, y1 = band(0.02, 0.26)
        bH = y1-y0; kd = min(bH*0.62, (x1-x0)*0.16)
        # the visualizer between the knobs must still clear the usable() gate
        kd = max(40, min(kd, ((x1-x0) - 0.26*W - 36) / 2))
        yc = (y0+y1)/2
        add("knob0", "knob", x0+6, yc-kd/2, kd, kd, bind="volume", label="VOL")
        add("knob1", "knob", x1-6-kd, yc-kd/2, kd, kd, bind="balance", label="BAL")
        screens_and_seek((x0+kd+18, y0, x1-kd-18, y1), (0.26, 0.32), (0.60, 0.66), (0.66, 0.99))
        x0, y0, x1, y1 = band(0.32, 0.50)
        span = x1-x0; bH = y1-y0
        d = min(bH*0.62, span/6.6)
        amp = (bH - d) * 0.9
        for i, b in enumerate(["prev", "play", "pause", "stop", "next"]):
            t = i/4
            bx = x0 + span*0.06 + t*(span - span*0.12 - d)
            by = (y1 - d) - amp*(1 - (2*t-1)**2)   # arc dips ends, lifts middle
            add(b, "button", bx, by, d, d, bind=b, label=b, shape="ellipse")
        knobs_eq(0.50, 0.62, knobs=False, sw_edges=True)
    else:
        screens_and_seek(band(0.02, 0.24), (0.24, 0.31), (0.58, 0.64), (0.64, 0.99))
        x0, y0, x1, y1 = band(0.31, 0.43, max_h=82)
        span = x1-x0-16; bx = x0+8
        bw = span/8.2
        for i, b in enumerate(["prev", "play", "pause", "stop", "next"]):
            add(b, "button", bx + i*bw*1.12, y0, bw, y1-y0, bind=b, label=b)
        swx = bx + 5*bw*1.12 + bw*0.35
        for i, (bind, lab) in enumerate([("shuffle", "SHUF"), ("eqOn", "EQ")]):
            add(f"sw{i}", "toggle", swx + i*bw*1.05, y0-6, bw*0.92, (y1-y0)+12, bind=bind, label=lab)
        knobs_eq(0.42, 0.58)
    return regs

def _draw_regions(d, regs):
    for r in regs:
        rc = r["rect"]; x0, y0 = rc["x"]*W, rc["y"]*H; x1, y1 = x0+rc["w"]*W, y0+rc["h"]*H
        if r["kind"] == "slider-arc":
            i = 0.06*(x1-x0)             # ring radius matches the live control (0.88 of half-box)
            a = r["arc"]
            d.arc([x0+i, y0+i, x1-i, y1-i], a["start"], a["end"], fill=WELL, width=18)
        elif r["kind"] == "knob" or (r["kind"] == "button" and r.get("shape") == "ellipse"):
            d.ellipse([x0, y0, x1, y1], fill=WELL, outline=EDGE, width=4)
        elif r["kind"] == "display":
            if r.get("shape") == "ellipse":
                d.ellipse([x0, y0, x1, y1], fill=(12, 13, 15), outline=EDGE, width=6)
            else:
                d.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=(12, 13, 15), outline=EDGE, width=5)
        else:
            d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=WELL, outline=EDGE, width=4)

def draw_blueprint(mask, regs):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    body = np.asarray(img).copy()
    body[mask] = BODY
    img = Image.fromarray(body)
    _draw_regions(ImageDraw.Draw(img), regs)
    return img

def draw_wells_only(regs):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    _draw_regions(ImageDraw.Draw(img), regs)
    return img

def usable(regs):
    """Hard gate: the layout must have real screens, or the silhouette is rejected."""
    if any(r["rect"]["w"] <= 0 or r["rect"]["h"] <= 0 for r in regs):
        return False
    d = {r["id"]: r["rect"] for r in regs if r["kind"] == "display"}
    # thresholds kept low enough that tall/narrow and squat/wide bodies still
    # pass (shape diversity) while screens stay readable
    return (d["playlist"]["w"] >= 0.25 and d["playlist"]["h"] >= 0.11 and
            d["visualizer"]["w"] >= 0.20 and d["visualizer"]["h"] >= 0.055 and
            d["marquee"]["w"] >= 0.15)

def main(out_id, style, brief, sil_path=None, variant="classic", refs=None):
    # upload refs up front — they steer BOTH the grown silhouette shape (envelope)
    # and the paint palette/material, so the body follows the reference character
    ref_urls = [G.upload(p) for p in (refs or []) if os.path.exists(p)]
    if variant in ("radial", "capsule", "minimal", "manray"):
        # LAYOUT FIRST: the arc-native template exists before any body does;
        # the image model grows the creature AROUND the drawn controls
        regs = (layout_radial() if variant == "radial" else
                layout_capsule() if variant == "capsule" else
                layout_minimal() if variant == "minimal" else layout_manray())
        wells = draw_wells_only(regs)
        rmask = region_mask(regs)
        for attempt in range(3):
            mask = gen_envelope(wells, brief, out_id, ref_urls)
            if mask is not None:
                mask = ndimage.binary_fill_holes(mask | rmask)
            if mask is not None and covers(mask, regs):
                break
            print(f"[{out_id}] envelope does not contain the layout — retry {attempt+1}", flush=True)
        else:
            raise SystemExit("no enveloping body in 3 attempts")
    else:
        for attempt in range(3):
            mask = gen_silhouette(brief, out_id, sil_path); sil_path = None
            regs = layout_in_mask(mask, variant)
            if usable(regs):
                break
            print(f"[{out_id}] silhouette unusable (screens too small) — retry {attempt+1}", flush=True)
        else:
            raise SystemExit("no usable silhouette in 3 attempts")
    bp = draw_blueprint(mask, regs)
    bp_path = os.path.join(G.HERE, f"_sculpt-{out_id}.png"); bp.save(bp_path)
    cu = G.upload(bp_path)
    # ref_urls (computed above) also steer the paint pass (material/color/detail)
    # while the blueprint stays the layout authority — passed as extra image_urls
    prompt = STYLE_PROMPT + MATERIAL.get(style, MATERIAL["winamp"])
    if ref_urls:
        prompt += (" Borrow the palette, materials and surface-detail vocabulary "
                   "of the REFERENCE image(s) provided, but DO NOT copy their layout "
                   "or shape — the silhouette and wells come only from the blueprint.")
    job = G.submit(cu, prompt, ref_urls)
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
    # argv: <id> <style> "<brief>" [sil_path|-] [variant] [ref1,ref2,...]
    sil = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    variant = sys.argv[5] if len(sys.argv) > 5 else "classic"
    refs = sys.argv[6].split(",") if len(sys.argv) > 6 and sys.argv[6] != "-" else None
    main(sys.argv[1], sys.argv[2], sys.argv[3], sil, variant, refs)
