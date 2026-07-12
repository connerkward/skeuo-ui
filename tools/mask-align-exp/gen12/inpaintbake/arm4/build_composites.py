#!/usr/bin/env python3
"""build_composites (arm 4) — paste each arm-4 model result CROP back onto its full source
skin, using the exact same feathered-blend compositing math erase12.py:erase_model() ships in
production (full-strength interior, alpha ramps to 0 over the outer ~12% margin) — same as the
parent inpaintbake/build_composites.py and editors/build_composites.py (verify-outputs-rule §7:
verify in the real runtime, not a reimplementation).

Compares 5 candidates per skin:
  vertex           — Vertex gemini-3-pro-image baseline, REUSED from ../results (0 fresh spend)
  gemini31-flash   — arm-3's best cheap instruction-editor, REUSED from ../editors/results (0 fresh spend)
  flux-pro-erase   — NEW this arm: fal-ai/flux-pro/v1/erase, $0.004/MP, no-prompt dedicated eraser
  object-removal   — NEW this arm: fal-ai/object-removal/mask, $0.006/img, no-prompt dedicated eraser
  gemini25-flash-glow — NEW this arm: gemini-2.5-flash-image + glow-preserve clause, Vertex-direct, $0.039/img

Read-only against ../ and ../editors/; only writes under arm4/.
"""
import json, os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
INPAINTBAKE = os.path.dirname(HERE)      # inpaintbake/ (read-only)
EDITORS = os.path.join(INPAINTBAKE, "editors")  # arm-3 (read-only)
OUT_DIR = os.path.join(HERE, "web", "composite")
RESULTS_DIR = os.path.join(HERE, "results")               # this arm's own NEW results
PARENT_RESULTS_DIR = os.path.join(INPAINTBAKE, "results")  # read-only: vertex baseline
EDITORS_RESULTS_DIR = os.path.join(EDITORS, "results")      # read-only: gemini31-flash

CROPS_META = json.load(open(os.path.join(INPAINTBAKE, "crops_meta.json")))
SKINS = ["diablo-gothic", "wc-goldshield", "fallout-vault"]
MODELS = ["vertex", "gemini31-flash", "flux-pro-erase", "object-removal", "gemini25-flash-glow"]
MODEL_RESULTS_DIR = {
    "vertex": PARENT_RESULTS_DIR,
    "gemini31-flash": EDITORS_RESULTS_DIR,
    "flux-pro-erase": RESULTS_DIR,
    "object-removal": RESULTS_DIR,
    "gemini25-flash-glow": RESULTS_DIR,
}
MODEL_EXT = {
    "vertex": "png", "gemini31-flash": "png", "flux-pro-erase": "png",
    "object-removal": "png", "gemini25-flash-glow": "png",
}

FULLSKIN_THUMB_W = 340
SEAM_PAD_FRAC = 0.5
SEAM_THUMB_W = 480
JPEG_Q = 88


def feathered_paste(base_rgb_arr, result_crop_img, crop_box):
    """Same blend as production erase12.py:erase_model() / all sibling arms' build_composites.py."""
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
    for skin in SKINS:
        meta = CROPS_META[skin]
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
            result_path = os.path.join(MODEL_RESULTS_DIR[model], f"{skin}__{model}.{MODEL_EXT[model]}")
            if not os.path.exists(result_path):
                print(f"[skip] {skin} x {model}: no result at {result_path}")
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
