#!/usr/bin/env python3
"""
Measure gpt-image-2/edit's spatial drift by overlaying canonical hotspot rects
on each styled-idle output. If gpt-image preserves layout, rects align with
the styled components. Where they don't, drift is visible.
"""
from PIL import Image, ImageDraw
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REFS = REPO / "assets" / "refs"
OUT = Path.home() / "Desktop" / "skeuo-drift"
OUT.mkdir(parents=True, exist_ok=True)

# Same hotspots used in extraction (image-relative).
HOTSPOTS = [
    ("prev",    "button",   0.073, 0.290, 0.075, 0.075),
    ("play",    "button",   0.155, 0.286, 0.080, 0.082),
    ("pause",   "button",   0.245, 0.290, 0.065, 0.075),
    ("stop",    "button",   0.318, 0.290, 0.065, 0.075),
    ("next",    "button",   0.389, 0.290, 0.075, 0.075),
    ("eject",   "button",   0.476, 0.290, 0.050, 0.070),
    ("shuffle", "switch",   0.555, 0.290, 0.140, 0.072),
    ("eq-on",   "switch",   0.087, 0.432, 0.045, 0.045),
    ("eq-auto", "switch",   0.137, 0.432, 0.060, 0.045),
    ("presets", "button",   0.857, 0.432, 0.070, 0.045),
    ("preamp",  "slider-v", 0.095, 0.483, 0.045, 0.158),
    ("eq-1k",   "slider-v", 0.468, 0.483, 0.045, 0.158),
    ("gain",    "slider-v", 0.905, 0.483, 0.045, 0.158),
    ("pl-add",  "button",   0.083, 0.913, 0.045, 0.050),
    ("pl-play", "button",   0.555, 0.913, 0.050, 0.052),
    ("pl-list", "button",   0.905, 0.910, 0.070, 0.060),
]

STYLES = ["canonical-zero", "pipboy", "winamp", "ipod", "nautical", "cyberpunk"]
CN2_DIR = Path("/Users/conner/dev/lookdev-compare/img-v2")
CN3_DIR = Path("/Users/conner/dev/lookdev-compare/img-v3")
KIND_COLOR = {"button": (255, 60, 60, 230), "switch": (255, 180, 0, 230), "slider-v": (60, 200, 255, 230)}

def annotate(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    W, H = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for (hid, kind, x, y, w, h) in HOTSPOTS:
        box = (int(x * W), int(y * H), int((x + w) * W), int((y + h) * H))
        c = KIND_COLOR[kind]
        draw.rectangle(box, outline=c, width=4)
        draw.text((box[0] + 4, box[1] + 2), hid, fill=c)
    return Image.alpha_composite(img, overlay)

for style in STYLES:
    src = REFS / f"{style}.png" if style == "canonical-zero" else REFS / f"{style}-idle.png"
    if not src.exists():
        print(f"!! missing {src}")
        continue
    out = annotate(src)
    out_path = OUT / f"drift-{style}.png"
    out.save(out_path)
    print(f"-> {out_path}")

# Also annotate ControlNet round 2 outputs
for style in ["pipboy", "winamp", "ipod", "nautical", "cyberpunk"]:
    src = CN2_DIR / f"cn2-{style}.png"
    if src.exists():
        out = annotate(src)
        out.save(OUT / f"drift-cn2-{style}.png")

# ControlNet round 3 (stronger control, semantic prompt)
for style in ["pipboy", "winamp", "ipod", "nautical", "cyberpunk"]:
    src = CN3_DIR / f"cn3-{style}.png"
    if src.exists():
        out = annotate(src)
        out_path = OUT / f"drift-cn3-{style}.png"
        out.save(out_path)
        print(f"-> {out_path}")
