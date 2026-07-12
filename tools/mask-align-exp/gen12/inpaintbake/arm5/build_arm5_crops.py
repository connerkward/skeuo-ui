#!/usr/bin/env python3
"""build_arm5_crops — arm-5 crop/mask builder.

Reuses the parent inpaintbake/crops_meta.json's 3 crops verbatim (diablo-gothic continuity
skin + fallout-pipboy + n64-cutscene, neither tested in arm-3's editors/ set) — no re-crop, no
re-spend, paths point straight at ../crops/*.png.

Builds TWO NEW crops for material diversity beyond arm-3's set (diablo-gothic, wc-goldshield,
fallout-vault): claymation (clay, seek/slider) and steam-porthole (brass, vol/knob — see note
below). Same method as ../build_crops.py: fixed 1024x1024 native-res square centered on the
real detected defect bbox_px, mask = bbox dilated 14px, binary L-mode PNG.

Source images: neither skin has a surviving full-resolution "defect present" paint.png on disk
(claymation's erase succeeded -- defect_found_after=false -- so current paint.png is already
clean; steam-porthole's current paint.png reflects the manual-finish repair). Both were
recovered from git history by matching erase12-log.json's before_sha (sha256[:12] of the paint
blob) against historical commits of assets-<skin>/paint.png:
  claymation:      commit 8c97ef9ae4a18a703dc8e282c75398eb851f2d76 (sha 1449b99f1b39)
  steam-porthole:  commit e8f249db9fc27ce7a480c27a7c9f88e2dd1938c5 (sha 163f3beb1247)
Both extracted at full native 2304x3712 and cached here as crops/<skin>-before-full-source.png.

NOTE on steam-porthole: the orchestrator asked for a "baked-slider" skin here, but a repo-wide
grep of every assets-*/erase12-log.json for control=="seek" found genuine seek defects on only
6 skins total (the 5 already in crops_meta.json + claymation) -- steam-porthole never had one
(regions.json's seek.bakedThumb.flag is False for this skin). Its only confirmed real baked-
thumb-style defect is on "vol" -- but erase12-log.json's own bbox_px for that entry,
[1133,2051,1157,2346] (24px wide x 295px tall), is a BUGGED detection: verified by cropping it
that it does NOT bound the vol knob at all -- it's a narrow sliver over the neighboring
play/pause button. Ground truth was instead derived independently (verify-outputs-rule: don't
trust a single logged number) by diffing the recovered pre-erase paint.png against the current
(post-manual-fix) paint.png: the real changed region is [991,2046,1302,2358], which matches
regions.json's vol.device bbox almost exactly. Visually confirming both ends: BEFORE shows the
round vol-knob housing wrongly baked with a duplicated PLAY/PAUSE pictogram (a wrong-icon
generation defect, not a slider thumb); AFTER shows the correct empty round dial socket. This
substitutes the real, verified vol-knob wrong-icon defect for the requested-but-nonexistent
seek slider; it still delivers brass-material diversity and adds a ROUND-housing/wrong-icon
failure mode the rest of the roster (all rectangular slider grooves) doesn't test.
"""
import json, os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INPAINTBAKE = os.path.dirname(HERE)
CROP_SIDE = 1024
MASK_DILATE = 14

PARENT_META = json.load(open(os.path.join(INPAINTBAKE, "crops_meta.json")))
REUSE_SKINS = ["diablo-gothic", "fallout-pipboy", "n64-cutscene"]

NEW_SKINS = {
    "claymation": {
        "source": os.path.join(HERE, "crops", "claymation-before-full-source.png"),
        "bbox_px": [1705, 1653, 1859, 1823],
        "seed": 662,
        "material": "soft claymation/plasticine sculpted channel, warm ochre clay with visible fingerprint texture",
        "control": "seek",
        "provenance": "git 8c97ef9ae4a18a703dc8e282c75398eb851f2d76, sha256[:12]=1449b99f1b39",
    },
    "steam-porthole": {
        "source": os.path.join(HERE, "crops", "steam-porthole-before-full-source.png"),
        "bbox_px": [991, 2046, 1302, 2358],  # ground-truth diff bbox, NOT erase12-log's bugged
                                              # [1133,2051,1157,2346] -- see module docstring
        "seed": 952,
        "material": "polished brass steampunk porthole housing, riveted trim, round recessed dial socket",
        "control": "vol (round knob, wrong-icon defect -- see module docstring: no genuine seek defect exists for this skin)",
        "provenance": "git e8f249db9fc27ce7a480c27a7c9f88e2dd1938c5, sha256[:12]=163f3beb1247; "
                       "bbox re-derived via before/after pixel diff, cross-checked against "
                       "regions.json vol.device",
    },
}


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

    for skin in REUSE_SKINS:
        m = dict(PARENT_META[skin])
        m["reused_from"] = "../crops_meta.json (no rebuild)"
        out_meta[skin] = m
        print(f"[reuse] {skin}: {m['crop_path']}")

    for skin, cfg in NEW_SKINS.items():
        img = Image.open(cfg["source"]).convert("RGB")
        W, H = img.size
        bbox_px = cfg["bbox_px"]
        crop_box = square_crop(W, H, bbox_px, CROP_SIDE)
        cx0, cy0, cx1, cy1 = crop_box
        crop = img.crop(crop_box)

        bx0, by0, bx1, by1 = bbox_px
        lx0, ly0, lx1, ly1 = bx0 - cx0, by0 - cy0, bx1 - cx0, by1 - cy0
        mask_arr = np.zeros((crop.size[1], crop.size[0]), np.uint8)
        lx0d, ly0d = max(0, lx0 - MASK_DILATE), max(0, ly0 - MASK_DILATE)
        lx1d, ly1d = min(crop.size[0], lx1 + MASK_DILATE), min(crop.size[1], ly1 + MASK_DILATE)
        mask_arr[ly0d:ly1d, lx0d:lx1d] = 255
        mask_img = Image.fromarray(mask_arr, mode="L")

        crop_path = os.path.join(HERE, "crops", f"{skin}-crop.png")
        mask_path = os.path.join(HERE, "crops", f"{skin}-mask.png")
        crop.save(crop_path)
        mask_img.save(mask_path)

        out_meta[skin] = {
            "before_path": cfg["source"],
            "crop_path": crop_path,
            "mask_path": mask_path,
            "full_size": [W, H],
            "bbox_px": bbox_px,
            "crop_box": list(crop_box),
            "bbox_in_crop": [lx0, ly0, lx1, ly1],
            "seed": cfg["seed"],
            "material": cfg["material"],
            "control": cfg["control"],
            "provenance": cfg["provenance"],
        }
        print(f"[ok] {skin}: crop={crop.size} bbox_in_crop={[lx0,ly0,lx1,ly1]}")

    json.dump(out_meta, open(os.path.join(HERE, "arm5_crops_meta.json"), "w"), indent=2)
    print(f"\n{len(out_meta)} crops -> arm5_crops_meta.json")


if __name__ == "__main__":
    main()
