#!/usr/bin/env python3
"""build_composites (arm 5) -- pastes each result crop back onto its FULL source skin using the
exact same feathered-blend compositing math erase12.py:erase_model() ships in production (full-
strength interior, alpha ramps to 0 over the outer ~12% margin) -- ported verbatim from
../build_composites.py (verify-outputs-rule SS7: verify in the real runtime, not a
reimplementation). Read-only against arm5_crops_meta.json + results/; only writes under web/.
"""
import json, os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "web", "composite")
RESULTS_DIR = os.path.join(HERE, "results")

CROPS_META = json.load(open(os.path.join(HERE, "arm5_crops_meta.json")))
MODELS = ["gemini25-flash", "gpt-image-2"]

FULLSKIN_THUMB_W = 340
SEAM_PAD_FRAC = 0.5
SEAM_THUMB_W = 480
JPEG_Q = 88


def feathered_paste(base_rgb_arr, result_crop_img, crop_box):
    cx0, cy0, cx1, cy1 = crop_box
    side_w = cx1 - cx0
    side_h = cy1 - cy0
    out = result_crop_img.convert("RGB")
    if out.size != (side_w, side_h):
        out = out.resize((side_w, side_h), Image.LANCZOS)
    out_arr = np.asarray(out).astype(float)

    def ramp(n):
        margin = max(4, int(n * 0.12))
        r = np.ones(n)
        r[:margin] = np.linspace(0, 1, margin)
        r[-margin:] = np.linspace(1, 0, margin)
        return r

    ramp_x = ramp(side_w)
    ramp_y = ramp(side_h)
    alpha = np.minimum(ramp_y[:, None], ramp_x[None, :])[:, :, None]

    region = base_rgb_arr[cy0:cy1, cx0:cx1].astype(float)
    blended = region * (1 - alpha) + out_arr * alpha
    new_arr = base_rgb_arr.copy()
    new_arr[cy0:cy1, cx0:cx1] = blended.astype(np.uint8)
    return new_arr


def draw_box(img, crop_box, color=(230, 40, 40), width=None):
    im = img.copy()
    d = ImageDraw.Draw(im)
    w = width or max(2, im.size[0] // 400)
    d.rectangle(crop_box, outline=color, width=w)
    return im


def padded_seam_box(crop_box, W, H, pad_frac=SEAM_PAD_FRAC):
    x0, y0, x1, y1 = crop_box
    w, h = x1 - x0, y1 - y0
    px, py = int(w * pad_frac / 2), int(h * pad_frac / 2)
    return (max(0, x0 - px), max(0, y0 - py), min(W, x1 + px), min(H, y1 + py))


def save_pair(img, out_prefix, thumb_w):
    full_path = f"{out_prefix}-full.jpg"
    thumb_path = f"{out_prefix}-thumb.jpg"
    img.convert("RGB").save(full_path, "JPEG", quality=JPEG_Q)
    scale = thumb_w / img.size[0]
    thumb = img.convert("RGB").resize((thumb_w, max(1, int(img.size[1] * scale))), Image.LANCZOS)
    thumb.save(thumb_path, "JPEG", quality=JPEG_Q)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0
    for skin, meta in CROPS_META.items():
        before_img = Image.open(meta["before_path"]).convert("RGB")
        W, H = before_img.size
        crop_box = tuple(meta["crop_box"])
        seam_box = padded_seam_box(crop_box, W, H)

        before_boxed = draw_box(before_img, crop_box)
        p = os.path.join(OUT_DIR, f"{skin}__BEFORE-fullskin")
        save_pair(before_boxed, p, FULLSKIN_THUMB_W)
        before_seam = before_img.crop(seam_box)
        p = os.path.join(OUT_DIR, f"{skin}__BEFORE-seam")
        save_pair(before_seam, p, SEAM_THUMB_W)

        base_arr = np.asarray(before_img)
        for model in MODELS:
            result_path = os.path.join(RESULTS_DIR, f"{skin}__{model}.png")
            if not os.path.exists(result_path):
                print(f"[missing] {skin} x {model}")
                continue
            result_crop = Image.open(result_path)
            composite_arr = feathered_paste(base_arr, result_crop, crop_box)
            composite_img = Image.fromarray(composite_arr, mode="RGB")

            boxed = draw_box(composite_img, crop_box)
            p = os.path.join(OUT_DIR, f"{skin}__{model}-fullskin")
            save_pair(boxed, p, FULLSKIN_THUMB_W)

            seam = composite_img.crop(seam_box)
            p = os.path.join(OUT_DIR, f"{skin}__{model}-seam")
            save_pair(seam, p, SEAM_THUMB_W)

            count += 1
            print(f"[ok] {skin} x {model}")

    print(f"\n{count} composites built -> {OUT_DIR}")


if __name__ == "__main__":
    main()
