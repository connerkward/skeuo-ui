#!/usr/bin/env python3
"""Review board for the FAVORITES layout variations — six IG-shaped (9:16)
contact-sheet treatments of the same six skins, tiled so the user can pick
which to post."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.expanduser("~/Desktop/skeuo-skins")
W, H = 2260, 1780
BG = (10, 11, 13)
INK = (210, 213, 219); DIM = (120, 126, 136); FAINT = (74, 78, 86); LINE = (38, 41, 47)

def font(p, s):
    try: return ImageFont.truetype(p, s)
    except Exception: return ImageFont.load_default()
MONO = "/System/Library/Fonts/Menlo.ttc"; SANS = "/System/Library/Fonts/HelveticaNeue.ttc"
f_title, f_h, f_lbl, f_sub = font(SANS, 40), font(MONO, 23), font(MONO, 20), font(MONO, 15)

img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
for y in range(0, H, 46):
    for x in range(0, W, 46):
        d.point((x, y), fill=(26, 28, 32))

# header
d.text((48, 40), "skeuo/ui", font=f_title, fill=(238, 240, 244))
d.text((250, 56), "— favorites · layout variations", font=f_h, fill=DIM)
d.text((W-470, 60), "frog · bondi · burger · pebble · halo · biomech", font=f_sub, fill=FAINT)
d.line([48, 110, W-48, 110], fill=LINE, width=1)

TILES = [
    ("fav-grid-1080x1920@2x.png",        "grid · 2-col",        "color-balanced, no two greens adjacent"),
    ("fav-grid-3col-1080x1920@2x.png",   "grid · 3-col",        "tighter cluster, all 6 fully in frame"),
    ("fav-fan-1080x1920@2x.png",         "fan",                 "overlapping arc, drop shadows"),
    ("fav-center-halo-1080x1920@2x.png", "center · Spartan",    "one hero, rest bleed off the edges"),
    ("fav-center-frog-1080x1920@2x.png", "center · Froggo",     "?center= picks the hero"),
    ("fav-scatter-1080x1920@2x.png",     "scatter",             "playful pile, varied size + rotation"),
]
cols, th = 3, 720
gx, gy = 56, 168
cellw = (W - 96 - gx * (cols - 1)) // cols
for i, (fn, label, sub) in enumerate(TILES):
    p = os.path.join(OUT, fn)
    if not os.path.exists(p): continue
    im = Image.open(p).convert("RGB")
    tw = int(th * im.width / im.height)
    im = im.resize((tw, th), Image.LANCZOS)
    c, r = i % cols, i // cols
    x = 48 + c * (cellw + gx) + (cellw - tw) // 2
    y = gy + r * (th + 96)
    d.rectangle([x-1, y-1, x+tw, y+th], outline=LINE, width=1)
    img.paste(im, (x, y))
    d.text((x, y+th+12), label, font=f_lbl, fill=INK)
    d.text((x, y+th+38), sub, font=f_sub, fill=DIM)

d.line([48, H-56, W-48, H-56], fill=LINE, width=1)
d.text((48, H-42), "all 1080×1920 @2x · post directly, or tune via ?ts=&mg=&gap=&cols=&dev=&skins=&center=",
       font=f_sub, fill=FAINT)
d.text((W-360, H-42), "skeuo-ui.pages.dev", font=f_sub, fill=FAINT)

out = os.path.join(OUT, "lookdev-favorites.png")
img.save(out); print("wrote", out, img.size)
