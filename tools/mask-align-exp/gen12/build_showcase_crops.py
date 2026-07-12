#!/usr/bin/env python3
"""build_showcase_crops.py — STANDALONE, read-only extraction for stateful-buttons-showcase.html.

Does NOT touch build_player.py / extract12.py / erase12.py or any assets-*/ file. Reads
paint.png + regions.json (device rects, already-baked truth from the real pipeline) from
existing skin folders and writes padded crops + copies of real cut two-state sprites into
./stateful-showcase-assets/crops/. Every crop here is REAL painted/cut pixels from a real
skin generation — no synthetic content, no invented geometry.

Safe to re-run any time; only ever writes into stateful-showcase-assets/, never into
assets-*/.
"""
import os, json
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "stateful-showcase-assets", "crops")
os.makedirs(OUT, exist_ok=True)

PAD = 0.38  # generous context padding around the device rect, each side


def crop_device(theme, control, out_name, pad=PAD):
    """Crop `control`'s device rect straight out of assets-<theme>/paint.png at native res."""
    adir = os.path.join(HERE, f"assets-{theme}")
    paint = Image.open(os.path.join(adir, "paint.png")).convert("RGB")
    regs = json.load(open(os.path.join(adir, "regions.json")))
    r = regs["regions"].get(control)
    if not r or not r.get("device"):
        print(f"  SKIP {theme}/{control} — no device rect")
        return None
    x, y, w, h = r["device"]
    W, H = paint.size
    px, py = w * pad, h * pad
    box = (
        max(0, x - px) * W, max(0, y - py) * H,
        min(1, x + w + px) * W, min(1, y + h + py) * H,
    )
    c = paint.crop(tuple(int(v) for v in box))
    dest = os.path.join(OUT, out_name)
    c.save(dest)
    print(f"  {theme}/{control} -> {out_name}  {c.size}")
    return dest


def copy_sprite(theme, sprite, out_name):
    """Copy a real cut (transparent) sprite straight from assets-<theme>_biref/."""
    src = os.path.join(HERE, f"assets-{theme}_biref", f"{sprite}.png")
    if not os.path.exists(src):
        print(f"  SKIP {theme}/{sprite} — no biref cut")
        return None
    im = Image.open(src).convert("RGBA")
    dest = os.path.join(OUT, out_name)
    im.save(dest)
    print(f"  {theme}/{sprite} -> {out_name}  {im.size}")
    return dest


print("Device-rect crops from real paint.png (padded, native res):")
JOBS = [
    ("wmp-quicksilver", "playpause", "wmp-playpause.png"),
    ("fallout-pipboy", "queue", "pipboy-queue.png"),
    ("fallout-pipboy", "repeat", "pipboy-repeat.png"),
    ("diablo-gothic", "playpause", "diablo-playpause.png"),
    ("wc-goldshield", "repeat", "goldshield-repeat.png"),
    ("wc-goldshield", "queue", "goldshield-queue.png"),
    ("steam-porthole", "repeat", "steam-repeat.png"),
    ("biomech-giger", "repeat", "biomech-repeat.png"),
    ("claymation", "playpause", "claymation-playpause.png"),
    ("myst-arcanum", "shuffle", "myst-shuffle.png"),
    ("fa-sky", "playpause", "fasky-playpause.png"),
    ("fa-sky", "repeat", "fasky-repeat.png"),
    ("claymation-toggletrack1", "shuffle", "claytt1-shuffle.png"),
    ("fa-pod-toggletrack2", "shuffle", "fapodtt2-shuffle.png"),
]
for theme, control, out in JOBS:
    crop_device(theme, control, out)

print("\nReal cut two-state / lever sprites (transparent, from *_biref/):")
SPRITES = [
    ("fallout-pipboy", "shuffle_off", "pipboy-shuffle_off.png"),
    ("fallout-pipboy", "shuffle_on", "pipboy-shuffle_on.png"),
    ("wmp-quicksilver", "shuffle_off", "wmp-shuffle_off.png"),
    ("wmp-quicksilver", "shuffle_on", "wmp-shuffle_on.png"),
    ("claymation-toggletrack1", "shuffle_lever", "claytt1-lever.png"),
    ("fa-pod-toggletrack2", "shuffle_lever", "fapodtt2-lever.png"),
]
for theme, sprite, out in SPRITES:
    copy_sprite(theme, sprite, out)

print("\nDone ->", OUT)
