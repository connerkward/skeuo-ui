#!/usr/bin/env python3
"""template — pure-control (non-skin, abstract) test template for the position-mask-correlation
experiment (2026-07-11). Motivation: docs/experiments/2026-07-10-twoimg-conditioning.md's NEUTRAL
arm found guide-colour bleed persists via the TEXT PROMPT even with a colourless reference image,
because the mask spec must NAME each colour. This asks the prior question: can the model
correlate an output mask cell to its template region by POSITION ALONE, with no colour and no
number in the prompt at all -- as reliably as today's colour-keyed convention?

Geometry is IDENTICAL across all three arms (position/numbered/color) -- same panel, same 8
regions at the same pixel positions, same right-hand mask column split into N equal-height
stacked bands in a FIXED vertical order. Only the CORRELATION SIGNAL varies:
  a. position -- no marks at all; correspondence is pure reading-order convention.
  b. numbered -- small digit tags (1..N) on both region and its assigned band.
  c. color    -- region filled a solid guide colour; its band carries a matching colour swatch
                 chip (today's actual production mechanism, ported to this synthetic harness).

Shapes are abstract (circle/oval/rounded-rect/diamond/pill) on a plain grey panel -- explicitly
NOT a music-player control footprint, so this stays a pure-control (non-skin) experiment.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

COL_W, H = 1200, 1920           # per-column size; total canvas 2*COL_W x H = 2400x1920 = 5:4
N = 8                            # region / cell count (within the 6-10 brief)
BAND_H = H // N                  # 240px per stacked mask cell

BG_OUTER = (245, 245, 247)       # left-column flat backdrop
PANEL = (206, 206, 212)          # "plain panel" body
REGION_NEUTRAL = (92, 92, 100)   # position/numbered arms: neutral grey fill, no colour signal
MASK_BG = (0, 0, 0)              # right column background
DIVIDER = (70, 70, 76)

# 8 maximally-separated guide colours (color arm only) -- reused pattern from
# twoimg/genskin_twoimg.py's NAMEMAP keys, trimmed to 8 with clear names for the prompt.
GUIDE_COLORS = {
    "r1": ((0, 90, 255), "AZURE BLUE"),
    "r2": ((255, 40, 0), "PURE RED"),
    "r3": ((0, 200, 90), "SPRING GREEN"),
    "r4": ((255, 200, 0), "GOLD YELLOW"),
    "r5": ((170, 0, 220), "VIOLET PURPLE"),
    "r6": ((0, 210, 210), "CYAN"),
    "r7": ((255, 110, 190), "ROSE PINK"),
    "r8": ((140, 90, 40), "UMBER BROWN"),
}

# 8 distinct abstract shapes: (kind, w, h, radius). kind in circle|oval|rrect|diamond.
# Sizes chosen so max extent (190px, r8 pill) fits inside a 240px band with margin, and pixel
# AREAS are well separated for deterministic shape-matching in scoring (no OCR/cv2 needed).
SHAPES = {
    "r1": ("circle", 110, 110, None),   # small circle,  area ~9500
    "r2": ("oval",   180, 90,  None),   # wide oval,     area ~12700
    "r3": ("rrect",  150, 100, 20),     # small rrect,   area ~14100
    "r4": ("rrect",  340, 55,  27),     # groove/pill,   area ~17600
    "r5": ("circle", 170, 170, None),   # large circle,  area ~22700
    "r6": ("diamond",120, 120, None),   # diamond,       area ~7200
    "r7": ("rrect",  70,  190, 35),     # vertical pill, area ~12200
    "r8": ("rrect",  200, 130, 30),     # large rrect,   area ~24900
}

# 4 rows x 2 cols grid, rows well separated so reading order (top-to-bottom, then left-to-right)
# is unambiguous even after jitter. Reading order == r1..r8 as listed (grid slot order).
_ROW_Y = [260, 740, 1220, 1700]
_COL_X = [0.28 * COL_W, 0.72 * COL_W]
_JITTER = {  # fixed hand-picked jitter (deterministic, no RNG dependency) within +/-30px
    "r1": (-18, 12), "r2": (22, -8), "r3": (-10, 20), "r4": (15, -15),
    "r5": (-25, 5), "r6": (10, 18), "r7": (-8, -22), "r8": (20, 10),
}
REGION_ORDER = [f"r{i+1}" for i in range(N)]  # canonical reading order, ground truth


def region_centers():
    """cx,cy (panel-local px, origin at panel's own column) for each region, grid + jitter."""
    centers = {}
    for i, name in enumerate(REGION_ORDER):
        row, col = divmod(i, 2)
        jx, jy = _JITTER[name]
        centers[name] = (_COL_X[col] + jx, _ROW_Y[row] + jy)
    return centers


def _font(size=40):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def draw_shape(d, kind, w, h, radius, cx, cy, fill):
    if kind == "circle":
        r = w / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    elif kind == "oval":
        d.ellipse([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], fill=fill)
    elif kind == "rrect":
        d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=radius, fill=fill)
    elif kind == "diamond":
        pts = [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)]
        d.polygon(pts, fill=fill)
    else:
        raise ValueError(kind)


def _tag(d, x, y, text, font, fg=(235, 235, 235), bg=(30, 30, 34)):
    tw = d.textlength(text, font=font) if hasattr(d, "textlength") else len(text) * 20
    pad = 7
    d.rectangle([x - tw / 2 - pad, y - 18 - pad, x + tw / 2 + pad, y + 18 + pad], fill=bg)
    d.text((x - tw / 2, y - 18), text, fill=fg, font=font)


def build_template(arm):
    """Build the full 2-column canvas for one arm. Returns (PIL.Image, ground_truth dict).
    ground_truth carries everything score_poscorr.py needs: region shapes/centers, canonical
    band assignment, and (for color arm) the guide-colour key per region -- all computed here,
    independent of anything the model does, so scoring never depends on model output."""
    assert arm in ("position", "numbered", "color")
    W = 2 * COL_W
    img = Image.new("RGB", (W, H), BG_OUTER)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([50, 50, COL_W - 50, H - 50], radius=90, fill=PANEL)

    font = _font(40)
    centers = region_centers()
    for i, name in enumerate(REGION_ORDER):
        kind, w, h, radius = SHAPES[name]
        cx, cy = centers[name]
        if arm == "color":
            fill = GUIDE_COLORS[name][0]
        else:
            fill = REGION_NEUTRAL
        draw_shape(d, kind, w, h, radius, cx, cy, fill)
        if arm == "numbered":
            _tag(d, cx, cy, str(i + 1), font)

    # right column: black background, N equal-height bands with thin dividers
    d.rectangle([COL_W, 0, W, H], fill=MASK_BG)
    for k in range(1, N):
        y = k * BAND_H
        d.line([COL_W, y, W, y], fill=DIVIDER, width=2)
    if arm == "numbered":
        for k in range(N):
            by = k * BAND_H + BAND_H // 2
            _tag(d, COL_W + 70, by, str(k + 1), font)
    elif arm == "color":
        # swatch chip = the SAME guide colour as the region assigned to this band (fixed
        # vertical order == REGION_ORDER, band k <-> REGION_ORDER[k]), mirroring production's
        # "region colour == its own mask blob colour" convention.
        for k in range(N):
            name = REGION_ORDER[k]
            by = k * BAND_H + BAND_H // 2
            col = GUIDE_COLORS[name][0]
            d.rectangle([COL_W + 40, by - 24, COL_W + 88, by + 24], fill=col)

    ground_truth = {
        "arm": arm, "N": N, "col_w": COL_W, "H": H, "band_h": BAND_H,
        "region_order": REGION_ORDER,           # reading order == canonical band assignment
        "shapes": {n: list(SHAPES[n]) for n in REGION_ORDER},
        "centers": {n: list(centers[n]) for n in REGION_ORDER},
        "guide_colors": {n: list(GUIDE_COLORS[n][0]) for n in REGION_ORDER},
        "guide_color_names": {n: GUIDE_COLORS[n][1] for n in REGION_ORDER},
        "band_of": {n: k for k, n in enumerate(REGION_ORDER)},
    }
    return img, ground_truth


def expected_band_mask(name):
    """Ground-truth binary mask (band_h x col_w bool array) of the shape expected in region
    `name`'s assigned band, centered in the band -- used as the IoU reference in scoring
    under the REQUESTED convention (fixed vertical stack, reading order)."""
    kind, w, h, radius = SHAPES[name]
    m = Image.new("L", (COL_W, BAND_H), 0)
    d = ImageDraw.Draw(m)
    draw_shape(d, kind, w, h, radius, COL_W / 2, BAND_H / 2, 255)
    return np.asarray(m) > 127


def expected_mirror_mask(name):
    """Ground-truth binary mask (H x col_w bool array) of the shape expected at region `name`'s
    OWN panel position, mirrored 1:1 into the right column -- the ALTERNATE convention the model
    may default to (spatial mirroring) instead of the requested reading-order stack. Used as a
    secondary metric so an arm that ignores the stack convention isn't scored as pure failure if
    it consistently mirrors position instead."""
    kind, w, h, radius = SHAPES[name]
    cx, cy = region_centers()[name]
    m = Image.new("L", (COL_W, H), 0)
    d = ImageDraw.Draw(m)
    draw_shape(d, kind, w, h, radius, cx, cy, 255)
    return np.asarray(m) > 127


if __name__ == "__main__":
    for arm in ("position", "numbered", "color"):
        img, gt = build_template(arm)
        img.save(os.path.join(HERE, f"template-{arm}.png"))
        print(f"[{arm}] template-{arm}.png {img.size} regions={len(gt['region_order'])}")
