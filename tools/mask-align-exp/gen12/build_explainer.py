#!/usr/bin/env python3
"""build_explainer — generate REAL annotated substep images for the dashboard's interactive
pipeline walkthrough, from an exemplar skin's actual artifacts (default: steam-porthole), plus
the diablo mis-cut case study (why nearest-centroid betrayed us and mask-cell overlap fixes it).
Outputs gen12/explainer/*.png + explainer/steps.json. Usage: python3 build_explainer.py [skin-id]
"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SID = sys.argv[1] if len(sys.argv) > 1 else "steam-porthole"
A = os.path.join(HERE, f"assets-{SID}")
B = A + "_biref"
OUT = os.path.join(HERE, "explainer"); os.makedirs(OUT, exist_ok=True)
REG = json.load(open(os.path.join(A, "regions.json")))
regs = REG["regions"]

paint = Image.open(os.path.join(A, "paint.png")).convert("RGB"); W, H = paint.size


def font(sz):
    try: return ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", sz)
    except Exception: return ImageFont.load_default()


def label(d, xy, txt, sz=34, fg=(255, 255, 255), bg=(0, 0, 0, 190)):
    f = font(sz); x, y = xy
    tb = d.textbbox((x, y), txt, font=f)
    d.rectangle([tb[0] - 8, tb[1] - 5, tb[2] + 8, tb[3] + 5], fill=bg[:3])
    d.text((x, y), txt, font=f, fill=fg)


def save(im, name, maxw=1400):
    if im.width > maxw: im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    im.save(os.path.join(OUT, name))
    return name


steps = []

# 1 blueprint / scaffold
bp = os.path.join(A, "blueprint.png")
if os.path.exists(bp):
    steps.append({"img": save(Image.open(bp).convert("RGB"), "01-blueprint.png"), "t": "1 · Blueprint / scaffold",
        "d": "What WE draw and send (free, PIL): LEFT a placeholder body with one coloured OUTLINE per control (the colour is the control's identity), RIGHT pure black where the model must paint the colour-by-numbers mask. Templateless mode sends just the flat backdrop + strip divider."})

# 2 joint
jt = os.path.join(A, "joint-4k.png")
if os.path.exists(jt):
    steps.append({"img": save(Image.open(jt).convert("RGB"), "02-joint.png", 1600), "t": "2 · One generation, two panels",
        "d": "ONE image-edit call (fal-ai/gemini-3-pro-image-preview/edit, ~$0.15) returns both panels in a single 4K canvas: the painted skin on the left, the flat-colour region mask on the right — pixel-aligned because they were generated together. We split it down the middle."})

# 3 detection overlay — mask cells drawn + labeled on the paint (device area)
ov = paint.copy(); d = ImageDraw.Draw(ov)
COL = {"playpause": (255, 80, 80), "prev": (255, 160, 60), "next": (255, 220, 60), "repeat": (120, 255, 120),
       "queue": (80, 220, 255), "vol": (180, 130, 255), "seek": (255, 120, 200), "shuffle": (120, 255, 220),
       "album_art": (255, 255, 160), "visualizer": (160, 200, 255)}
for k, r in regs.items():
    if not r or not r.get("device"): continue
    b = r["device"]; c = COL.get(k, (255, 255, 255))
    x0, y0 = b[0] * W, b[1] * H; x1, y1 = (b[0] + b[2]) * W, (b[1] + b[3]) * H
    d.rectangle([x0, y0, x1, y1], outline=c, width=6)
    label(d, (x0 + 6, max(4, y0 - 44)), k, 30, c)
steps.append({"img": save(ov, "03-detection.png"), "t": "3 · Detection — read the mask like a map",
    "d": "Every pixel of the RIGHT panel is compared to the known guide colours (nearest-colour within a distance gate); the largest connected blob of each colour = that control's location. Boxes here are drawn from regions.json onto the real paint — identity comes from COLOUR, never from guessing shapes."})

# 4 matte + island cuts strip
mp = os.path.join(B, "global-matte.png")
if os.path.exists(mp):
    gm = Image.open(mp).convert("RGBA").resize((W, H))
    board = Image.new("RGB", (W, H), (24, 26, 32)); board.paste(gm, (0, 0), gm)
    dd = ImageDraw.Draw(board)
    label(dd, (30, 24), "BiRefNet alpha matte — device island + loose-part islands + socket HOLES", 40, (140, 255, 180))
    steps.append({"img": save(board, "04-matte.png"), "t": "4 · Matting — BiRefNet cuts everything at once",
        "d": "One BiRefNet v2 pass (~$0.005) over the paint returns an alpha matte: device body and each loose strip part become separate opaque ISLANDS; empty sockets punch HOLES through the device island (we use those holes' centroids as knob seats in step 6)."})

# 5 THE MIS-CUT CASE STUDY (diablo): centroid vs mask-cell-overlap assignment
DA = os.path.join(HERE, "assets-diablo-gothic")
if os.path.exists(os.path.join(DA, "paint.png")):
    dp = Image.open(os.path.join(DA, "paint.png")).convert("RGB")
    dm = Image.open(os.path.join(DA, "mask.png")).convert("RGB").resize(dp.size)
    dreg = json.load(open(os.path.join(DA, "regions.json")))["regions"]
    y0 = int(dp.height * 0.72)
    pstrip = dp.crop((0, y0, dp.width, dp.height))
    mstrip = dm.crop((0, y0, dp.width, dp.height))
    canvas = Image.new("RGB", (dp.width, pstrip.height * 2 + 30), (14, 15, 18))
    canvas.paste(pstrip, (0, 0)); canvas.paste(mstrip, (0, pstrip.height + 30))
    dd = ImageDraw.Draw(canvas)
    label(dd, (24, 16), "PAINT strip (what was actually painted)", 40, (255, 255, 255))
    label(dd, (24, pstrip.height + 44), "MASK strip (where the model SAID the parts are)", 40, (255, 190, 80))
    # draw the shuffle mask cells on BOTH strips to show the misalignment
    for i, cell in enumerate((dreg.get("shuffle") or {}).get("strip") or []):
        if not cell: continue
        x0c, y0c = cell[0] * dp.width, cell[1] * dp.height - y0
        x1c, y1c = (cell[0] + cell[2]) * dp.width, (cell[1] + cell[3]) * dp.height - y0
        for oy, tag in [(0, "mask cell on PAINT"), (pstrip.height + 30, "mask cell")]:
            dd.rectangle([x0c, y0c + oy, x1c, y1c + oy], outline=(255, 60, 60), width=8)
        label(dd, (x0c + 4, max(4, y0c - 48)), f"shuffle cell {i} — WRONG shape/pos", 30, (255, 90, 90))
    steps.append({"img": save(canvas, "05-miscut.png", 1600), "t": "5 · The mis-cut bug — why we stopped trusting a bad mask blindly",
        "d": "Diablo case study. TOP: the painted strip really has knob · thumb · two landscape switches. BOTTOM: the model's MASK put the shuffle cells at the wrong size/position (red boxes — compare where they land on the paint). The old code then matched BiRefNet islands to parts by NEAREST CENTROID, so a wrong-shaped island got labelled 'switch' — the phantom part you saw. The fix: a part is assigned ONLY to the island that OVERLAPS its colour-coded mask cell (identity from colour, geometry from BiRefNet), and a mask this broken now FAILS the gate and re-rolls instead of shipping."})

# 6 alignment: seat + travel + state-align drawn on the exemplar paint
al = paint.copy(); d = ImageDraw.Draw(al)
kn = next((k for k, ro in (REG.get("roles") or {}).items() if ro == "knob"), "vol")
r = regs.get(kn) or {}
if r.get("seat"):
    cx, cy, rr = r["seat"][0] * W, r["seat"][1] * H, r["seat"][2] * W
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(120, 255, 120), width=8)
    d.line([cx - 22, cy, cx + 22, cy], fill=(120, 255, 120), width=6); d.line([cx, cy - 22, cx, cy + 22], fill=(120, 255, 120), width=6)
    label(d, (cx - rr, cy + rr + 12), "seat: fit radius + matte-hole centroid", 30, (120, 255, 120))
sl = next((k for k, ro in (REG.get("roles") or {}).items() if ro == "slider"), "seek")
r = regs.get(sl) or {}
if r.get("travel") and r.get("device"):
    tv = r["travel"]; gb = r["device"]; ty = (gb[1] + gb[3] / 2) * H
    d.line([tv[0] * W, ty, tv[1] * W, ty], fill=(255, 220, 80), width=10)
    for tx in (tv[0] * W, tv[1] * W): d.line([tx, ty - 30, tx, ty + 30], fill=(255, 220, 80), width=10)
    label(d, (tv[0] * W, ty + 40), "travel: walked to the slot's true ends (recess + rims)", 30, (255, 220, 80))
tg = next((k for k, ro in (REG.get("roles") or {}).items() if ro == "toggle"), "shuffle")
r = regs.get(tg) or {}
if r.get("device"):
    b = r["device"]; sa = r.get("stateAlign") or {}
    d.rectangle([b[0] * W, b[1] * H, (b[0] + b[2]) * W, (b[1] + b[3]) * H], outline=(120, 220, 255), width=8)
    label(d, (b[0] * W, (b[1] + b[3]) * H + 12), f"switch: ON registered onto OFF by max-IoU (IoU={sa.get('iou','—')})", 30, (120, 220, 255))
steps.append({"img": save(al, "06-alignment.png"), "t": "6 · Alignment — computed placement, drawn on the real paint",
    "d": "Green: knob seat (gradient circle-fit radius, centre snapped to the matte hole's centroid). Yellow: seek travel span (pixel-walk to the slot's visual ends, clamped to the groove). Blue: toggle slot; its two states are silhouette-registered so the housing never jumps. These are the ACTUAL numbers from regions.json rendered back onto the paint — studio overlay, not part of the artifact."})

# 7 cut parts board
parts = ["vol", "seek", f"{tg}_off", f"{tg}_on"]
imgs = [(p, Image.open(os.path.join(B, p + ".png"))) for p in parts if os.path.exists(os.path.join(B, p + ".png"))]
if imgs:
    hmax = max(im.height for _, im in imgs) + 90
    board = Image.new("RGB", (sum(im.width for _, im in imgs) + 60 * (len(imgs) + 1), hmax + 40), (20, 22, 28))
    dd = ImageDraw.Draw(board); x = 60
    for p, im in imgs:
        board.paste(im, (x, 50), im if im.mode == "RGBA" else None)
        label(dd, (x, 50 + im.height + 10), p, 34, (200, 230, 255)); x += im.width + 60
    steps.append({"img": save(board, "07-parts.png"), "t": "7 · The cut parts — ready to seat",
        "d": "The final loose sprites, cut by BiRefNet and IDENTIFIED by mask-cell overlap (fix from step 5). The player seats these live: knob rotates under drag (pinned screen-blend specular), thumb slides the travel span, switch swaps its registered states."})

# 8 material-aware silhouette press (composed from the real before/after verification pairs)
import glob as _g
prs = sorted(_g.glob(os.path.expanduser("~/Desktop/cc-skeuo/2026-07-09-press-*-up-vs-down.png")))
if prs:
    boards = [Image.open(p).convert("RGB") for p in prs[:3]]
    w = max(b.width for b in boards)
    boards = [b.resize((w, int(b.height * w / b.width)), Image.LANCZOS) for b in boards]
    gap = 26
    canvas = Image.new("RGB", (w, sum(b.height for b in boards) + gap * (len(boards) + 1) + 40), (14, 15, 18))
    dd = ImageDraw.Draw(canvas); y = gap
    names = ["light glass (fa-sky)", "dark stone (diablo)", "brass (steam)"]
    for i, b in enumerate(boards):
        canvas.paste(b, (0, y)); label(dd, (18, y + 10), f"unpressed | pressed — {names[i] if i < len(names) else ''}", 30, (200, 230, 255))
        y += b.height + gap
    steps.append({"img": save(canvas, "08-press.png", 1500), "t": "8 · Material-aware silhouette press",
        "d": "How a button 'presses' without a fake black blob: the press overlay is the button's OWN paint pixels, "
             "clipped to its EXACT silhouette from the colour mask (no bounding-box ellipse), shifted down ~3% "
             "(physical travel — the icon moves too), darkened proportionally to the material's brightness "
             "(12% on light glass up to ~28% on dark stone, with a slight contrast lift), then shaded the way real "
             "light flips on a pressed part: a shape-following inner shadow at the TOP edge and a faint catch-light "
             "at the BOTTOM edge (the visible cue on dark materials where extra darkness would vanish). "
             "Every layer derives from the button's own pixels, so glass stays glassy and stone stays stone."})

json.dump({"skin": SID, "steps": steps}, open(os.path.join(OUT, "steps.json"), "w"), indent=1)
print(f"[explainer] {len(steps)} steps -> explainer/ (exemplar {SID})")
