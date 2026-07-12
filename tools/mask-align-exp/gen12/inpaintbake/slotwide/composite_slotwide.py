#!/usr/bin/env python3
"""composite_slotwide — paste each model's whole-slot repair back onto the FULL source skin at
the crop box, using the SAME feathered-blend logic as erase12.py's edit_model() (12% margin
soft-alpha ramp, full-strength interior fading to 0 at the crop border) — the seam this shows
is the seam production actually ships, per the task's instruction to reuse erase12's compositing.
Adapted for RECTANGULAR crops (erase12's original assumed a square crop): separate x/y ramps.
"""
import json, os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
META = json.load(open(os.path.join(HERE, "slot_crops_meta.json")))
MODELS = ["lama", "bria", "vertex"]


def feathered_composite(base_img, out_img, crop_box):
    cx0, cy0, cx1, cy1 = crop_box
    target_size = (cx1 - cx0, cy1 - cy0)  # (w, h)
    if out_img.size != target_size:
        out_img = out_img.resize(target_size, Image.LANCZOS)
    out_arr = np.asarray(out_img.convert("RGB")).astype(float)
    h, w = out_arr.shape[0], out_arr.shape[1]
    mx = max(4, int(w * 0.12))
    my = max(4, int(h * 0.12))
    ramp_x = np.ones(w); ramp_x[:mx] = np.linspace(0, 1, mx); ramp_x[-mx:] = np.linspace(1, 0, mx)
    ramp_y = np.ones(h); ramp_y[:my] = np.linspace(0, 1, my); ramp_y[-my:] = np.linspace(1, 0, my)
    alpha = np.minimum(ramp_y[:, None], ramp_x[None, :])[:, :, None]
    base_arr = np.asarray(base_img.convert("RGB")).astype(float)
    region = base_arr[cy0:cy1, cx0:cx1]
    blended = region * (1 - alpha) + out_arr * alpha
    new_arr = base_arr.copy()
    new_arr[cy0:cy1, cx0:cx1] = blended
    return Image.fromarray(new_arr.astype(np.uint8))


def main():
    out_dir = os.path.join(HERE, "composited")
    os.makedirs(out_dir, exist_ok=True)
    for skin, meta in META.items():
        base_img = Image.open(meta["before_path"]).convert("RGB")
        crop_box = tuple(meta["crop_box"])
        for model in MODELS:
            res_path = os.path.join(HERE, "results", f"{skin}__{model}.png")
            if not os.path.exists(res_path):
                print(f"[skip] {skin} x {model}: no result")
                continue
            out_img = Image.open(res_path)
            composited = feathered_composite(base_img, out_img, crop_box)
            out_path = os.path.join(out_dir, f"{skin}__{model}__full.png")
            composited.save(out_path)
            # also save a zoomed seam crop: slot box padded 1.5x for the review page
            sx0, sy0, sx1, sy1 = meta["slot_box_px"]
            sw, sh = sx1 - sx0, sy1 - sy0
            zx0 = max(0, sx0 - sw * 0.25); zy0 = max(0, sy0 - sh * 0.25)
            zx1 = min(composited.width, sx1 + sw * 0.25); zy1 = min(composited.height, sy1 + sh * 0.25)
            seam = composited.crop((int(zx0), int(zy0), int(zx1), int(zy1)))
            seam.save(os.path.join(out_dir, f"{skin}__{model}__seam.png"))
            print(f"[ok] {skin} x {model} -> {out_path}")


if __name__ == "__main__":
    main()
