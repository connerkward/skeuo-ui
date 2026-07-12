#!/usr/bin/env python3
"""score — deterministic scoring pass (§a of the bake-off spec). Reuses erase12.py's OWN
detect_bbox() (groove-shaped baked-part locator) and seam_delta() (border-band colour delta)
functions directly — same detector the production pipeline gates on, not a reimplementation
(verify-outputs-rule §7: verify in the real runtime).

For each result crop, composites it back into a COPY of the skin's real pre-erase full paint
(erasegallery/mainline/assets-<skin>/before.png) at the exact crop_box location, then runs
detect_bbox() against the skin's regions.json seek-device window. CLEARED = detector no longer
flags a compact anomaly in the groove; FLAGGED = it still does (still reads as a baked part).
seam_delta is measured on the recomposited full-image array using the ORIGINAL bbox_px, so it's
the same border-band metric erase12.py itself computes.

Usage: python3 score.py
"""
import json, os, sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
from erase12 import detect_bbox, seam_delta  # noqa: E402

CROPS_META = json.load(open(os.path.join(HERE, "crops_meta.json")))
RESULTS_DIR = os.path.join(HERE, "results")

MODELS = ["lama", "z-image-turbo", "qwen-inpaint", "flux-pro-fill", "flux-dev-fill", "vertex"]


def boxes_overlap(a, b, pad=20):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ax0, ay0, ax1, ay1 = ax0 - pad, ay0 - pad, ax1 + pad, ay1 + pad
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def score_one(skin, model):
    result_path = os.path.join(RESULTS_DIR, f"{skin}__{model}.png")
    if not os.path.exists(result_path):
        return None
    meta = CROPS_META[skin]
    regions = json.load(open(os.path.join(GEN12, f"assets-{skin}", "regions.json")))
    seek = regions["regions"]["seek"]
    dev_bbox = seek["device"]
    vertical = seek.get("vertical")

    before_full = Image.open(meta["before_path"]).convert("RGB")
    full_arr = np.array(before_full)
    result_crop = Image.open(result_path).convert("RGB")
    cx0, cy0, cx1, cy1 = meta["crop_box"]
    side = cx1 - cx0
    if result_crop.size != (side, side):
        result_crop = result_crop.resize((side, side), Image.LANCZOS)
    full_arr[cy0:cy1, cx0:cx1] = np.array(result_crop)

    det = detect_bbox(full_arr, dev_bbox, vertical=vertical)
    # detect_bbox scans the WHOLE device window (e.g. the full horizontal control strip),
    # not just our repaired region — a raw "det is None" conflates "nothing anomalous
    # anywhere in the groove" with "our specific repair is clean." A rivet, button, or other
    # legit detail elsewhere in that window trips it regardless of repair quality (confirmed
    # live: fallout-vault's flagged anomaly sat at x=1135-1164, ~300px from the actual defect
    # at x=794-1030 — unrelated content, not a repair artifact). Score against OVERLAP with
    # the real defect site instead — that is what this bake-off is actually testing.
    at_defect_site = det is not None and boxes_overlap(det, tuple(meta["bbox_px"]))
    cleared = det is None or not at_defect_site
    sd = seam_delta(full_arr, tuple(meta["bbox_px"]), band=4)

    return {"skin": skin, "model": model, "cleared_by_detector": cleared,
            "detector_flag_bbox": list(det) if det else None,
            "flag_at_defect_site": at_defect_site, "seam_delta": round(sd, 2)}


def main():
    rows = []
    for skin in CROPS_META:
        for model in MODELS:
            r = score_one(skin, model)
            if r:
                rows.append(r)
    json.dump(rows, open(os.path.join(HERE, "det_scores.json"), "w"), indent=2)
    print(f"{len(rows)} scored -> det_scores.json")
    for r in rows:
        print(f"  {r['skin']:16s} {r['model']:15s} cleared={r['cleared_by_detector']!s:5s} "
              f"seam_delta={r['seam_delta']}")


if __name__ == "__main__":
    main()
