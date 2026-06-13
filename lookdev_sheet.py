#!/usr/bin/env python3
"""Compose a lookdev contact sheet that bundles the IG-shaped exports so the
user can review and pick what to post: the two primary 9:16 posts (skins grid +
hardware sprites) shown large, plus the hero skins as a 9:16 strip. Each tile is
captioned with its filename / dims / available formats."""
import os, glob
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.expanduser("~/Desktop/skeuo-skins")
W, H = 2360, 1560
BG = (10, 11, 13)
INK = (210, 213, 219)
DIM = (120, 126, 136)
FAINT = (74, 78, 86)
LINE = (38, 41, 47)
ACCENT = (150, 200, 130)

def font(path, size):
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

MONO = "/System/Library/Fonts/Menlo.ttc"
SANS = "/System/Library/Fonts/HelveticaNeue.ttc"
f_title = font(SANS, 40)
f_h     = font(MONO, 24)
f_lbl   = font(MONO, 19)
f_sub   = font(MONO, 15)

img = Image.new("RGB", (W, H), BG)
# faint dotted grid
dot = Image.new("RGB", (W, H), BG); dd = ImageDraw.Draw(dot)
for y in range(0, H, 46):
    for x in range(0, W, 46):
        dd.point((x, y), fill=(26, 28, 32))
img = Image.blend(img, dot, 1.0)
d = ImageDraw.Draw(img)

def tile(path, x, y, th, label, sub):
    """paste a 9:16 png scaled to height th at (x,y); caption beneath. returns width."""
    im = Image.open(path).convert("RGB")
    tw = int(th * im.width / im.height)
    im = im.resize((tw, th), Image.LANCZOS)
    # hairline frame
    d.rectangle([x-1, y-1, x+tw, y+th], outline=LINE, width=1)
    img.paste(im, (x, y))
    d.text((x, y+th+12), label, font=f_lbl, fill=INK)
    d.text((x, y+th+36), sub, font=f_sub, fill=DIM)
    return tw

# ---- header ----
d.text((48, 40), "skeuo/ui", font=f_title, fill=(238, 240, 244))
d.text((250, 56), "— instagram story exports · lookdev contact sheet", font=f_h, fill=DIM)
d.text((W-360, 60), "1080×1920 · 9:16 · 2026-06-13", font=f_sub, fill=FAINT)
d.line([48, 110, W-48, 110], fill=LINE, width=1)

# ---- primary posts: the two IG-shaped contents ----
d.text((48, 132), "POST A — skins (tap to post) · POST B — hardware sprites", font=f_sub, fill=FAINT)
big_h = 860
x = 48; y = 168
grid = os.path.join(OUT, "grid-1080x1920@2x.png")
spr  = os.path.join(OUT, "sprites-1080x1920@2x.png")
wA = tile(grid, x, y, big_h, "grid-1080x1920.png", "6 best skins · tight contact-sheet grid")
x += wA + 56
wB = tile(spr, x, y, big_h, "sprites-1080x1920.png", "switches · knobs · molded buttons · per skin")
x += wB + 72

# ---- hero strip (each: still + mp4 + gif) ----
d.text((x, 140), "HERO POSTS — animated · still + mp4 (full-fps) + gif (12fps)", font=f_sub, fill=FAINT)
heroes = ["maw", "wmp", "obelisk", "scarab"]
names = {"maw": "Angler Maw", "wmp": "Media Capsule", "obelisk": "Bone Totem", "scarab": "Scarab"}
hh = 408
hx, hy = x, 168
col = 0
for s in heroes:
    p = os.path.join(OUT, f"hero-{s}-1080x1920@2x.png")
    if not os.path.exists(p): continue
    tw = tile(p, hx, hy, hh, f"hero-{s}.png", f"{names.get(s, s)} · mp4 · gif")
    col += 1
    if col % 2 == 0:
        hx = x; hy += hh + 64
    else:
        hx += tw + 40

# ---- footer ----
d.line([48, H-58, W-48, H-58], fill=LINE, width=1)
d.text((48, H-44), "all 9:16 1080×1920 · stills @2x (2160×3840) · mp4 yuv420p crf18 · gif 12fps 720×1280",
       font=f_sub, fill=FAINT)
d.text((W-360, H-44), "skeuo-ui.pages.dev", font=f_sub, fill=FAINT)

out = os.path.join(OUT, "lookdev-contact-sheet.png")
img.save(out)
print("wrote", out, img.size)
