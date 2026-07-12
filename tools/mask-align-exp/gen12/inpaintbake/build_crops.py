#!/usr/bin/env python3
"""build_crops — extract fair, identical, ~1MP native-res crops + binary erase-masks for the
inpaint bake-off (docs/experiments/2026-07-12-inpaint-bakeoff.md), one per genuine baked-thumb
defect already confirmed live by erase12.py (see erase12-log.json per skin — NOT the claymation
false-positive, which erase12's own docstring records as a detector mis-fire on a genuinely
empty groove).

Source: erasegallery/mainline/assets-<skin>/before.png — the FULL 2304x3712 pre-erase paint
(defect still present), copied there by the erase12 gallery-proof pass. bbox_px comes from the
matching erase12-log.json entry (the real detected defect box, pixel space).

Crop is a FIXED 1024x1024 native-resolution square (no upscaling — unlike the 4x-upscaled
erase-verify/ crops), centered on the defect bbox, clamped to image bounds. Every finalist model
in the bake-off gets the SAME crop + SAME mask for a given skin — that is the controlled-
comparison contract (parallel-by-default-rule's "write the exact seam contract first").

Mask: binary, white (255) = erase region = bbox dilated 14px, black elsewhere. Saved as L-mode
PNG. Not feathered — models that want a soft mask do their own internal blending; a crisp mask
matches what fal's inpaint schemas describe ("binary mask where white indicates areas to erase").
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
CROP_SIDE = 1024
MASK_DILATE = 14

SKINS = ["diablo-gothic", "fallout-pipboy", "fallout-vault", "n64-cutscene", "wc-goldshield"]

MATERIAL = {
    "diablo-gothic": "dark carved obsidian/gothic metal channel with glowing rune inlay",
    "fallout-pipboy": "worn olive-drab painted metal recessed slot, retro-futuristic terminal casing",
    "fallout-vault": "brushed steel vault-door control channel with yellow hazard trim",
    "n64-cutscene": "chunky 90s-console beige/grey plastic recessed slider channel",
    "wc-goldshield": "ornate gold-shield emblem metal groove, warm brass tones",
}


def load_bbox(skin):
    log = json.load(open(os.path.join(GEN12, f"assets-{skin}", "erase12-log.json")))
    # prefer the most recent entry (last in list)
    entry = log[-1]
    return entry["bbox_px"], entry.get("seed")


def square_crop(W, H, bbox, side):
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = min(side, W, H)
    half = side / 2
    cx0 = int(min(max(0, cx - half), W - side))
    cy0 = int(min(max(0, cy - half), H - side))
    return cx0, cy0, cx0 + side, cy0 + side


def main():
    out_meta = {}
    for skin in SKINS:
        before_path = os.path.join(GEN12, "erasegallery", "mainline", f"assets-{skin}", "before.png")
        if not os.path.exists(before_path):
            print(f"[skip] {skin}: no before.png at {before_path}")
            continue
        bbox_px, seed = load_bbox(skin)
        img = Image.open(before_path).convert("RGB")
        W, H = img.size
        crop_box = square_crop(W, H, bbox_px, CROP_SIDE)
        cx0, cy0, cx1, cy1 = crop_box
        crop = img.crop(crop_box)

        # mask: bbox translated into crop-local coords, dilated
        bx0, by0, bx1, by1 = bbox_px
        lx0, ly0, lx1, ly1 = bx0 - cx0, by0 - cy0, bx1 - cx0, by1 - cy0
        mask_arr = np.zeros((crop.size[1], crop.size[0]), np.uint8)
        lx0d, ly0d = max(0, lx0 - MASK_DILATE), max(0, ly0 - MASK_DILATE)
        lx1d, ly1d = min(crop.size[0], lx1 + MASK_DILATE), min(crop.size[1], ly1 + MASK_DILATE)
        mask_arr[ly0d:ly1d, lx0d:lx1d] = 255
        mask_img = Image.fromarray(mask_arr, mode="L")

        crop_dir = os.path.join(HERE, "crops")
        os.makedirs(crop_dir, exist_ok=True)
        crop_path = os.path.join(crop_dir, f"{skin}-crop.png")
        mask_path = os.path.join(crop_dir, f"{skin}-mask.png")
        crop.save(crop_path)
        mask_img.save(mask_path)

        out_meta[skin] = {
            "before_path": before_path,
            "crop_path": crop_path,
            "mask_path": mask_path,
            "full_size": [W, H],
            "bbox_px": bbox_px,
            "crop_box": list(crop_box),
            "bbox_in_crop": [lx0, ly0, lx1, ly1],
            "seed": seed,
            "material": MATERIAL[skin],
        }
        print(f"[ok] {skin}: crop={crop.size} bbox_in_crop={[lx0,ly0,lx1,ly1]}")

    json.dump(out_meta, open(os.path.join(HERE, "crops_meta.json"), "w"), indent=2)
    print(f"\n{len(out_meta)} crops built -> {os.path.join(HERE, 'crops_meta.json')}")


if __name__ == "__main__":
    main()
