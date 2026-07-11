#!/usr/bin/env python3
"""score_poscorr -- deterministic, $0 scoring of a poscorr generation against its ground truth.

Four metrics per gen, all independent of any model call (per verify-outputs-rule §2: the
check must not share the model/assumption it's testing):
  1. per-cell IoU (stack) -- output band k's painted silhouette vs the EXPECTED shape for the
                             region canonically assigned to band k (reading order), both
                             rendered in the SAME fixed geometry -- the literal, most demanding
                             test of "did position alone put the right SHAPE in the right CELL,
                             at the right size/position". PRIMARY metric.
  1b. per-cell IoU (mirror) -- same shape, but at the region's OWN panel position mirrored 1:1
                             into the right column instead of its reading-order band -- tests
                             the ALTERNATE convention the model may default to when it ignores
                             the requested stack (observed: position/color arms both did).
  2. cells_filled         -- of the N bands, how many contain ANY painted blob at all (occupancy
                             completeness). Two shape-identity classifiers were tried and
                             dropped: an area+aspect nearest-neighbour (broke because the model
                             doesn't preserve source SIZE -- inflation varies by shape, not just
                             by generation) and an argmax-IoU-against-all-candidates classifier
                             (broke because several of the 8 abstract shapes are genuinely
                             silhouette-similar at the sizes the model actually renders, so
                             "which shape is this" is itself ambiguous even to a human eye at
                             a glance -- see the write-up). Rather than keep polishing a noisy
                             secondary classifier, cells_filled stays a blunt, unambiguous
                             completeness check; the primary IoU metric already captures
                             position+shape+size fidelity jointly and is the load-bearing number.
  3. contamination        -- color arm: any painted colour that isn't neutral white/grey
                             (should be pure white silhouettes per the prompt); numbered/color
                             arms: residual digit-tag / swatch-chip pixels left in the corner
                             of a band where the drafting mark used to sit (a coarse, cheap
                             proxy for "did the reference mark leak into the final output").

Usage: python3 score_poscorr.py    (no args -- walks assets-<arm>-<seed>/ dirs on disk)
Writes poscorr/scores.json
"""
import os, sys, json, glob
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from template import (N, COL_W, H, BAND_H, REGION_ORDER, expected_band_mask,
                       expected_mirror_mask)

FG_THRESH = 40      # brightness threshold for "painted" foreground vs black background
SAT_THRESH = 30      # max-min channel gap above which a pixel counts as "coloured" (not grey)
TAG_CORNER = 70       # px (in TEMPLATE coords) checked for residual digit/swatch leakage


def band_bbox_and_mask(band_img_L):
    """band_img_L: grayscale np array of one band crop. Returns (fg_mask, area, bbox_aspect,
    bbox) of the LARGEST connected foreground component only -- not the bbox of ALL painted
    pixels, which gets polluted by small residual digit-tag/swatch-chip pixels the
    numbered/color prompts asked to remove but that sometimes survive in a band's corner (see
    tag_leak). Picking the largest component is a cheap, deterministic way to isolate 'the
    shape' from 'leftover drafting-mark speckle' without OCR. Returns None if nothing painted."""
    fg = band_img_L > FG_THRESH
    if fg.sum() < 30:
        return None
    lbl, n = ndimage.label(fg)
    if n == 0:
        return None
    sizes = ndimage.sum(fg, lbl, index=range(1, n + 1))
    biggest = 1 + int(np.argmax(sizes))
    comp = lbl == biggest
    ys, xs = np.where(comp)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    return comp, int(comp.sum()), bw / bh, (x0, y0, x1, y1)


DARK_COL_THRESH = 110  # a column/row belongs to the black mask panel if its mean is below this


def find_black_panel_bbox(mask_L):
    """The model does NOT reliably render the black mask column edge-to-edge in its own crop
    half (it adds its own card margin/background around the black rectangle) -- naively
    assuming the black region spans the full half-crop silently counts that margin as
    'painted foreground' and wrecks every IoU. The bright (~246) outer backdrop and the pure
    black (~0-30) panel are far enough apart that a simple global bbox of 'dark enough' pixels
    (< DARK_COL_THRESH) is robust and needs no contiguity assumption -- a stray bright seam
    pixel (a divider-line antialiasing artifact) just isn't counted, it doesn't break a
    row/col-mean run the way a contiguity check would. Returns bbox in mask_L's own pixel
    coordinates: (x0, y0, x1, y1)."""
    ys, xs = np.where(mask_L < DARK_COL_THRESH)
    if len(ys) == 0:
        return 0, 0, mask_L.shape[1], mask_L.shape[0]
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def score_one(arm, seed):
    tag = f"{arm}-{seed}"
    d = os.path.join(HERE, f"assets-{tag}")
    maskp = os.path.join(d, "mask.png")
    if not os.path.exists(maskp):
        return None
    res = json.load(open(os.path.join(d, "results.json")))
    dims = res.get("dims")
    if not dims:
        return None
    mask = Image.open(maskp).convert("RGB")
    mask_rgb_full = np.asarray(mask).astype(int)
    mask_L_full = np.asarray(mask.convert("L"))
    # the model does not reliably fill its own crop half edge-to-edge with the black mask
    # panel -- detect the REAL black-panel bbox rather than assume it spans the whole crop
    px0, py0, px1, py1 = find_black_panel_bbox(mask_L_full)
    mask_L = mask_L_full[py0:py1, px0:px1]
    mask_rgb = mask_rgb_full[py0:py1, px0:px1]
    W, Ht = mask_L.shape[1], mask_L.shape[0]  # detected black-panel size only
    sx, sy = W / COL_W, Ht / H  # scale from template coords -> detected-panel output coords
    # full-column normalized copy for the secondary "mirror position" metric (not band-restricted)
    full_norm = np.asarray(Image.fromarray(mask_L).resize((COL_W, H))) > FG_THRESH

    per_cell, contamination = {}, {}
    ious, mirror_ious, filled = [], [], []
    for k in range(N):
        expected_name = REGION_ORDER[k]
        y0t, y1t = int(k * BAND_H * sy), int((k + 1) * BAND_H * sy)
        band_L = mask_L[y0t:y1t, :]
        band_rgb = mask_rgb[y0t:y1t, :]

        # largest-connected-component isolates 'the shape' from small residual digit-tag /
        # swatch-chip speckle in the band corner (see band_bbox_and_mask docstring) -- computed
        # once and reused for both the IoU shape mask and the assignment classifier below.
        info = band_bbox_and_mask(band_L)
        comp_native = info[0] if info else np.zeros_like(band_L, dtype=bool)

        # 1. IoU vs the ground-truth silhouette, both resized to a common (COL_W,BAND_H) frame
        out_fg = np.asarray(Image.fromarray((comp_native * 255).astype(np.uint8))
                             .resize((COL_W, BAND_H))) > 127
        gt_fg = expected_band_mask(expected_name)
        inter, union = int((out_fg & gt_fg).sum()), int((out_fg | gt_fg).sum())
        iou = inter / union if union else 0.0
        per_cell[expected_name] = {"cell": k, "iou": round(iou, 4)}
        ious.append(iou)

        # 1b. secondary metric: IoU vs the ALTERNATE "mirror panel position" convention,
        # measured over the FULL column (not band-restricted) since a mirrored shape may not
        # fall inside its reading-order band at all.
        gt_mirror = expected_mirror_mask(expected_name)
        m_inter, m_union = int((full_norm & gt_mirror).sum()), int((full_norm | gt_mirror).sum())
        m_iou = m_inter / m_union if m_union else 0.0
        per_cell[expected_name]["mirror_iou"] = round(m_iou, 4)
        mirror_ious.append(m_iou)

        # 2. cell occupancy completeness (see module docstring for why this replaced two
        # tried-and-dropped shape-identity classifiers)
        is_filled = info is not None
        per_cell[expected_name]["filled"] = is_filled
        filled.append(is_filled)

        # 3a. colour contamination: any non-neutral (saturated) painted pixel in this band
        painted = band_L > FG_THRESH
        if painted.sum():
            sat = band_rgb.max(2) - band_rgb.min(2)
            colour_frac = float((painted & (sat > SAT_THRESH)).sum()) / float(painted.sum())
        else:
            colour_frac = 0.0
        # 3b. residual tag/swatch leakage: check where numbered/color arms placed their
        # drafting mark -- template.py centers both the digit tag and the colour swatch chip
        # at (x=~0..140, y=BAND CENTER), not the band's top-left corner -- match that exactly,
        # in band_L's own LOCAL coordinates (band_L is already the per-band crop).
        band_local_h = band_L.shape[0]
        cy0 = max(0, int(band_local_h / 2 - TAG_CORNER * sy))
        cy1 = min(band_local_h, int(band_local_h / 2 + TAG_CORNER * sy))
        cx0, cx1 = 0, int(TAG_CORNER * 2 * sx)
        corner = band_L[cy0:cy1, cx0:cx1]
        tag_leak = bool(corner.size and (corner > FG_THRESH).mean() > 0.08)
        contamination[expected_name] = {"colour_frac": round(colour_frac, 4), "tag_leak": tag_leak}

    n_iou_pass = sum(1 for v in ious if v >= 0.5)
    n_mirror_pass = sum(1 for v in mirror_ious if v >= 0.5)
    mean_iou, mean_mirror = float(np.mean(ious)), float(np.mean(mirror_ious))
    return {
        "arm": arm, "seed": seed, "dims": dims,
        "per_cell": per_cell, "contamination": contamination,
        "mean_iou": round(mean_iou, 4),
        "iou_pass_at_0.5": n_iou_pass, "iou_pass_total": N,
        "mean_mirror_iou": round(mean_mirror, 4),
        "mirror_pass_at_0.5": n_mirror_pass,
        "detected_topology": "stack" if mean_iou >= mean_mirror else "mirror",
        "cells_filled": sum(filled), "cells_total": N,
        "mean_colour_contam": round(float(np.mean([c["colour_frac"] for c in contamination.values()])), 4),
        "tag_leak_n": sum(1 for c in contamination.values() if c["tag_leak"]),
    }


def main():
    scores = {}
    for d in sorted(glob.glob(os.path.join(HERE, "assets-*"))):
        base = os.path.basename(d)
        parts = base.replace("assets-", "").rsplit("-", 1)
        if len(parts) != 2:
            continue
        arm, seed = parts[0], int(parts[1])
        s = score_one(arm, seed)
        if s is None:
            print(f"[{base}] no output yet -- skip")
            continue
        tag = f"{arm}-{seed}"
        scores[tag] = s
        print(f"[{tag}] mean_iou(stack)={s['mean_iou']:.3f} ({s['iou_pass_at_0.5']}/{N}) "
              f"mean_iou(mirror)={s['mean_mirror_iou']:.3f} ({s['mirror_pass_at_0.5']}/{N}) "
              f"topology={s['detected_topology']} cells_filled={s['cells_filled']}/{N} "
              f"colour_contam={s['mean_colour_contam']:.4f} tag_leak={s['tag_leak_n']}/{N}")
    json.dump(scores, open(os.path.join(HERE, "scores.json"), "w"), indent=1)
    print(f"-> scores.json ({len(scores)} gens)")


if __name__ == "__main__":
    main()
