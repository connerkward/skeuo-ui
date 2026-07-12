#!/usr/bin/env python3
"""build_composites — paste each bake-off model's result CROP back onto its FULL source skin,
using the exact same feathered-blend compositing math erase12.py:erase_model() ships in
production (full-strength interior, alpha ramps to 0 over the outer ~12% margin) — so the seam
shown here is the seam production would actually produce (verify-outputs-rule §7: verify in the
real runtime, not a reimplementation). An isolated 1024x1024 crop can look flawless while the
paste boundary against the surrounding skin incoheres (wrong tone, a visible ring, a hallucinated
object sitting on unrelated material) — that boundary is the real pass/fail signal this script
exists to surface.

For every skin x model pair with a results/<skin>__<model>.png crop, emits four web assets under
web/composite/:
  <skin>__<model>-fullskin-thumb.jpg   full skin, downscaled, crop_box outlined in red
  <skin>__<model>-fullskin-full.jpg    full skin, native res, crop_box outlined in red (click-through)
  <skin>__<model>-seam-thumb.jpg       crop_box padded 1.5x, downscaled (the seam close-up)
  <skin>__<model>-seam-full.jpg        crop_box padded 1.5x, native res (click-through)
Plus a BEFORE variant (the baked-defect original, unmodified) for the same four, so the page can
A/B composite-vs-original at both full-skin and seam-zoom scale.

Usage: python3 build_composites.py
"""
import json, os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "web", "composite")
RESULTS_DIR = os.path.join(HERE, "results")

CROPS_META = json.load(open(os.path.join(HERE, "crops_meta.json")))
MODELS = ["lama", "z-image-turbo", "qwen-inpaint", "flux-pro-fill", "flux-dev-fill", "vertex", "bria-eraser"]

FULLSKIN_THUMB_W = 340   # grid-cell full-skin context thumbnail width
SEAM_PAD_FRAC = 0.5      # seam-zoom = crop_box expanded 1.5x (0.25 added each side)
SEAM_THUMB_W = 480       # grid-cell seam-zoom thumbnail width
JPEG_Q = 88


def feathered_paste(base_rgb_arr, result_crop_img, crop_box):
    """Reimplements erase12.py:erase_model()'s own blend exactly: full-strength interior,
    alpha ramps to 0 over the outer ~12% margin (min 4px) on both axes, applied per-pixel as
    min(ramp_x, ramp_y) so corners fade on both axes at once — same as production."""
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
    new_files = []
    for skin, meta in CROPS_META.items():
        before_img = Image.open(meta["before_path"]).convert("RGB")
        W, H = before_img.size
        crop_box = tuple(meta["crop_box"])
        seam_box = padded_seam_box(crop_box, W, H)

        # BEFORE (baked-defect original, unmodified) — full-skin + seam-zoom, both boxed
        before_boxed = draw_box(before_img, crop_box)
        p = os.path.join(OUT_DIR, f"{skin}__BEFORE-fullskin")
        save_pair(before_boxed, p, FULLSKIN_THUMB_W)
        new_files += [p + "-full.jpg", p + "-thumb.jpg"]
        before_seam = before_img.crop(seam_box)
        p = os.path.join(OUT_DIR, f"{skin}__BEFORE-seam")
        save_pair(before_seam, p, SEAM_THUMB_W)
        new_files += [p + "-full.jpg", p + "-thumb.jpg"]

        base_arr = np.asarray(before_img)
        for model in MODELS:
            result_path = os.path.join(RESULTS_DIR, f"{skin}__{model}.png")
            if not os.path.exists(result_path):
                continue
            result_crop = Image.open(result_path)
            composite_arr = feathered_paste(base_arr, result_crop, crop_box)
            composite_img = Image.fromarray(composite_arr, mode="RGB")

            boxed = draw_box(composite_img, crop_box)
            p = os.path.join(OUT_DIR, f"{skin}__{model}-fullskin")
            save_pair(boxed, p, FULLSKIN_THUMB_W)
            new_files += [p + "-full.jpg", p + "-thumb.jpg"]

            seam = composite_img.crop(seam_box)
            p = os.path.join(OUT_DIR, f"{skin}__{model}-seam")
            save_pair(seam, p, SEAM_THUMB_W)
            new_files += [p + "-full.jpg", p + "-thumb.jpg"]

            count += 1
            print(f"[ok] {skin} x {model}")

    print(f"\n{count} composites built -> {OUT_DIR} ({len(new_files)} files)")


if __name__ == "__main__":
    main()
