#!/usr/bin/env python3
"""prep_ab — build the shared crop backdrops for the switch-slot-compare experiment.

Uses assets-fallout-pipboy-tt-baseline (mainline TOGGLE_TRACK_ENABLED regen: baked PILL
housing + a separately-cut fun-shaped lever, exactly the "housing/lever shape mismatch"
this comparison is about) as the substrate for variants A and B:
  1. Locate the baked lever/boss inside the shuffle device window (erase12.detect_bbox).
  2. Erase it classically ($0, cv2.INPAINT_TELEA) -> a flat, housing-free patch.
  3. Crop a generous context window around the shuffle device -> shared "clean" backdrop.
Also crops the equivalent context window from assets-fallout-pipboy-shapematch (variant C,
already has a baked shaped housing, no erasure needed) at matching relative padding, for a
fair side-by-side.

Outputs into this dir: clean-backdrop.png (A's base, pre-CSS-housing), c-backdrop.png
(variant C crop), plus prints the crop's pixel box + device bbox-in-crop for the HTML to
position elements.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
from erase12 import detect_bbox, erase_classical  # noqa: E402

BASELINE = os.path.join(GEN12, "assets-fallout-pipboy-tt-baseline")
SHAPEMATCH = os.path.join(GEN12, "assets-fallout-pipboy-shapematch")


def crop_ctx(paint_img, dev_bbox, padx_frac=0.25, pady_frac=3.0):
    W, H = paint_img.size
    x, y, w, h = dev_bbox
    padx, pady = w * padx_frac, h * pady_frac
    cx0 = max(0, int((x - padx) * W))
    cy0 = max(0, int((y - pady) * H))
    cx1 = min(W, int((x + w + padx) * W))
    cy1 = min(H, int((y + h + pady) * H))
    crop = paint_img.crop((cx0, cy0, cx1, cy1))
    # device bbox expressed as fraction OF THE CROP, for the HTML to position on top
    dev_in_crop = [(x * W - cx0) / (cx1 - cx0), (y * H - cy0) / (cy1 - cy0),
                   w * W / (cx1 - cx0), h * H / (cy1 - cy0)]
    return crop, (cx0, cy0, cx1, cy1), dev_in_crop


def main():
    regs_b = json.load(open(os.path.join(BASELINE, "regions.json")))["regions"]["shuffle"]
    paint_b = Image.open(os.path.join(BASELINE, "paint.png")).convert("RGB")
    dev_b = regs_b["device"]
    W, H = paint_b.size

    # 1. erase the ENTIRE pill track (rim + recess + boss), not just the detected sub-part —
    # variants A and B both need a genuinely flat, housing-free patch to build their own housing
    # on top of; erasing only the small detected "baked part" bbox left a visible classical-
    # inpaint smudge at the boundary (Telea handles a small hole far better than a long thin
    # groove). Full-track erase, then a light floor_darken pass to flatten residual shading.
    x, y, w, h = dev_b
    W, H = paint_b.size
    full_bbox = (int(x * W), int(y * H), int((x + w) * W), int((y + h) * H))
    print(f"[detect] full device track bbox: {full_bbox}")
    clean_img, erase_crop_box = erase_classical(paint_b, full_bbox, pad_frac=0.35)
    print(f"[erase] classical inpaint over {erase_crop_box}")
    # second smaller pass focused on the sub-part detect_bbox found, to mop up any residual
    # rim/boss edge the first wide pass didn't fully smooth (cheap, still $0)
    arr2 = np.asarray(clean_img)
    bad2 = detect_bbox(arr2, dev_b, vertical=False)
    if bad2 is not None:
        clean_img, _ = erase_classical(clean_img, bad2, pad_frac=0.7)
        print(f"[erase] second mop-up pass over residual {bad2}")
    clean_img.save(os.path.join(HERE, "baseline-erased-full.png"))

    # 2. shared context crop for A/B from the erased baseline
    crop_a, box_a, dev_in_crop_a = crop_ctx(clean_img, dev_b)
    crop_a.save(os.path.join(HERE, "clean-backdrop.png"))
    print(f"[crop A/B] box={box_a} size={crop_a.size} dev_in_crop={dev_in_crop_a}")

    # 3. same context crop from the ORIGINAL (pre-erase) baseline, for the "before" reference
    crop_before, _, _ = crop_ctx(paint_b, dev_b)
    crop_before.save(os.path.join(HERE, "baseline-before.png"))

    # 4. matching context crop for variant C from the shapematch regen
    regs_c = json.load(open(os.path.join(SHAPEMATCH, "regions.json")))["regions"]["shuffle"]
    paint_c = Image.open(os.path.join(SHAPEMATCH, "paint.png")).convert("RGB")
    dev_c = regs_c["device"]
    crop_c, box_c, dev_in_crop_c = crop_ctx(paint_c, dev_c)
    crop_c.save(os.path.join(HERE, "c-backdrop.png"))
    print(f"[crop C] box={box_c} size={crop_c.size} dev_in_crop={dev_in_crop_c}")

    meta = {
        "baseline_device": dev_b, "baseline_detents": regs_b.get("detents"),
        "baseline_track": regs_b.get("track"),
        "crop_ab_box": box_a, "crop_ab_size": list(crop_a.size), "dev_in_crop_ab": dev_in_crop_a,
        "shapematch_device": dev_c, "shapematch_detents": regs_c.get("detents"),
        "shapematch_track": regs_c.get("track"),
        "crop_c_box": box_c, "crop_c_size": list(crop_c.size), "dev_in_crop_c": dev_in_crop_c,
    }
    json.dump(meta, open(os.path.join(HERE, "prep_meta.json"), "w"), indent=1)
    print("[ok] wrote prep_meta.json + backdrops")


if __name__ == "__main__":
    main()
