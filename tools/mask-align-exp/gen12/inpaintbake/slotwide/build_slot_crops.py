#!/usr/bin/env python3
"""build_slot_crops — SECOND bake-off arm (isolated in slotwide/, sibling of ../inpaintbake).

Hypothesis under test: does masking the WHOLE slider slot (the full groove/track), not just a
tight crop around the baked thumb, blend more coherently than patching a tight hole?

Slot extent per skin is READ, not hand-authored (placement-invariants-rule §1): each skin's
../../assets-<skin>/regions.json "seek" region's "device" rect IS already the computed groove
box — extract12.py's travel-walk algorithm (dark-core + per-side rim walk, material-agnostic)
overwrites regions[SLIDER]["device"] post-extraction to exactly bound the walked groove on the
travel axis, keeping the original fit-bbox width on the across axis. So region.device * full_size
gives the real slot box in full-skin pixel space — no manual re-measurement.

Crop = slot box + context padding, EXPANDED further (never cropped down) so its aspect ratio
lands within Gemini/Vertex's supported imageConfig.aspectRatio enum (confirmed live via web
search, ai-image-coords-rule: {1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9}) — sending
Vertex a mismatched aspect makes it SQUISH the output and every baked coordinate drifts, so the
crop sent to Vertex (and, for a single-crop-single-mask contract, to Bria/LaMa too) is pre-shaped
to match exactly what we request. LaMa/Bria have no aspect constraint, so the extra context is
free real material for them to blend from — same crop, same mask, all three models.

Mask = the ORIGINAL slot box (not the padded context) dilated by a small margin, so the model
repaints the full track but the surrounding context stays real pixels it can match against.
"""
import json, os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INPAINTBAKE = os.path.dirname(HERE)
GEN12 = os.path.dirname(INPAINTBAKE)

SKINS = ["diablo-gothic", "wc-goldshield", "fallout-vault"]
MATERIAL = {
    "diablo-gothic": "dark carved obsidian/gothic metal channel with glowing rune inlay",
    "wc-goldshield": "ornate gold-shield emblem metal groove, warm brass tones",
    "fallout-vault": "brushed steel vault-door control channel with yellow hazard trim",
}

CONTEXT_PAD_FRAC = 0.15     # context padding around the slot, before aspect-fitting
MASK_DILATE = 10            # px dilation of the slot box itself for the mask
VERTEX_ASPECTS = [(1, 1), (3, 2), (2, 3), (3, 4), (4, 3), (4, 5), (5, 4), (9, 16), (16, 9), (21, 9)]


def nearest_aspect(w, h):
    """Closest Vertex-supported aspect ratio to w/h, compared in log space (symmetric for
    wide vs tall)."""
    r = w / h
    best = min(VERTEX_ASPECTS, key=lambda ar: abs(np.log(ar[0] / ar[1]) - np.log(r)))
    return best


def expand_to_aspect(x0, y0, x1, y1, target_w, target_h, W, H):
    """Expand box (never shrink) so its aspect ratio == target_w/target_h, centered on the
    original box, clamped to image bounds."""
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    target_ratio = target_w / target_h
    cur_ratio = w / h
    if cur_ratio < target_ratio:
        # too tall/narrow -> widen
        new_w = h * target_ratio
        new_h = h
    else:
        # too wide/short -> heighten
        new_w = w
        new_h = w / target_ratio
    nx0, nx1 = cx - new_w / 2, cx + new_w / 2
    ny0, ny1 = cy - new_h / 2, cy + new_h / 2
    # clamp into image, preserving size where possible by shifting
    if nx0 < 0:
        nx1 -= nx0; nx0 = 0
    if nx1 > W:
        nx0 -= (nx1 - W); nx1 = W
    if ny0 < 0:
        ny1 -= ny0; ny0 = 0
    if ny1 > H:
        ny0 -= (ny1 - H); ny1 = H
    nx0 = max(0, nx0); ny0 = max(0, ny0)
    nx1 = min(W, nx1); ny1 = min(H, ny1)
    return int(round(nx0)), int(round(ny0)), int(round(nx1)), int(round(ny1))


def main():
    parent_meta = json.load(open(os.path.join(INPAINTBAKE, "crops_meta.json")))
    out_meta = {}
    for skin in SKINS:
        before_path = os.path.join(INPAINTBAKE, "..", "erasegallery", "mainline",
                                    f"assets-{skin}", "before.png")
        before_path = os.path.normpath(before_path)
        regions_path = os.path.join(GEN12, f"assets-{skin}", "regions.json")
        regs = json.load(open(regions_path))
        seek = regs["regions"]["seek"]
        device = seek["device"]  # [x,y,w,h] normalized to FULL paint.png dims (post-extraction
                                  # this IS the walked groove box — see extract12.py L780-787)
        vertical = bool(seek.get("vertical"))

        img = Image.open(before_path).convert("RGB")
        W, H = img.size

        sx0 = device[0] * W
        sy0 = device[1] * H
        sw = device[2] * W
        sh = device[3] * H
        sx1, sy1 = sx0 + sw, sy0 + sh

        # slot box (the actual groove) in full-skin px — this is the MASK basis
        slot_box = (sx0, sy0, sx1, sy1)

        # context-padded box (visual context for the crop, before aspect-fitting)
        padx = sw * CONTEXT_PAD_FRAC
        pady = sh * CONTEXT_PAD_FRAC
        cx0, cy0 = max(0, sx0 - padx), max(0, sy0 - pady)
        cx1, cy1 = min(W, sx1 + padx), min(H, sy1 + pady)

        # aspect-fit: expand (never shrink) to the nearest Vertex-supported aspect ratio so
        # the model isn't asked to squish/stretch our content (ai-image-coords-rule)
        aw, ah = nearest_aspect(cx1 - cx0, cy1 - cy0)
        fx0, fy0, fx1, fy1 = expand_to_aspect(cx0, cy0, cx1, cy1, aw, ah, W, H)
        crop_box = (fx0, fy0, fx1, fy1)
        crop = img.crop(crop_box)

        # mask: the SLOT box (not the padded context), dilated slightly, in crop-local coords
        lx0 = max(0, int(slot_box[0] - fx0) - MASK_DILATE)
        ly0 = max(0, int(slot_box[1] - fy0) - MASK_DILATE)
        lx1 = min(crop.size[0], int(slot_box[2] - fx0) + MASK_DILATE)
        ly1 = min(crop.size[1], int(slot_box[3] - fy0) + MASK_DILATE)
        mask_arr = np.zeros((crop.size[1], crop.size[0]), np.uint8)
        mask_arr[ly0:ly1, lx0:lx1] = 255
        mask_img = Image.fromarray(mask_arr, mode="L")

        crop_dir = os.path.join(HERE, "crops")
        crop_path = os.path.join(crop_dir, f"{skin}-slotcrop.png")
        mask_path = os.path.join(crop_dir, f"{skin}-slotmask.png")
        crop.save(crop_path)
        mask_img.save(mask_path)

        vertex_aspect_str = f"{aw}:{ah}"
        out_meta[skin] = {
            "before_path": before_path,
            "crop_path": crop_path,
            "mask_path": mask_path,
            "full_size": [W, H],
            "slot_box_px": [round(v, 1) for v in slot_box],
            "crop_box": list(crop_box),
            "mask_in_crop": [lx0, ly0, lx1, ly1],
            "vertical": vertical,
            "vertex_aspect": vertex_aspect_str,
            "seed": parent_meta.get(skin, {}).get("seed"),
            "material": MATERIAL[skin],
        }
        print(f"[ok] {skin}: slot={[round(v) for v in slot_box]} "
              f"crop={crop.size} (aspect->{vertex_aspect_str}) mask={[lx0,ly0,lx1,ly1]}")

    json.dump(out_meta, open(os.path.join(HERE, "slot_crops_meta.json"), "w"), indent=2)
    print(f"\n{len(out_meta)} slot crops built -> slot_crops_meta.json")


if __name__ == "__main__":
    main()
