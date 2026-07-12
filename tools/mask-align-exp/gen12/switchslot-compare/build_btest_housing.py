#!/usr/bin/env python3
"""build_btest_housing — apply "option B" (inpaint a housing shaped to match the switch) to a
skin's shuffle track, for real (not the throwaway switchslot-compare demo — this edits the
skin's own paint.png in place, in the skin's own assets-<id>/ dir).

Method (per the task brief: cut switch sprite -> alpha silhouette -> dilate -> mask that shape
-> inpaint a recessed housing matching the switch silhouette in the theme material):
  1. Load the biref-cut lever sprite (assets-<id>_biref/shuffle_lever.png, alpha-trimmed) and
     regions.json's shuffle track/detents (TOGGLE_TRACK_ENABLED contract).
  2. SWEEP the lever's own binary silhouette along the travel axis between the two detents
     (union of the mask at N interpolated positions) -- this is the correct "trough shaped like
     the switch, PLUS enough travel for it to slide" shape: a Minkowski-sum-style sweep, not just
     the lever's own footprint sitting still. Dilate the swept union a few px for a housing lip
     and further for an outer rim ring, directly in FULL PAINT PIXEL SPACE (no local-crop offset
     math -- the shapes are built straight onto a full-canvas-sized array using the same
     fraction->pixel coords regions.json already carries).
  3. Erase the EXISTING (wrong) baked housing across the full old track bbox via
     erase12.erase_classical (a flat, housing-free patch) -- same approach prep_ab.py used to
     build switchslot-compare's shared backdrops.
  4. Crop a square context window around the track (erase12._square_crop_box) from the erased
     backdrop, and from a copy of that crop with the swept housing mask's outline drawn/filled as
     a bright guide colour -- send BOTH images to fal-ai/gemini-25-flash-image/edit (image_urls
     accepts multiple refs) with a prompt asking it to paint a recessed housing matching the
     guide outline in the theme's own material.
  5. COMPOSITE the model's result back constrained to the swept mask (feathered ~6px), on TOP of
     the flat erased backdrop -- this GUARANTEES the final housing's silhouette matches the swept
     lever shape exactly regardless of what the model actually painted outside it (mask-
     constrained composite, not a free paste of the whole crop).
  6. Backs up the pre-treatment paint.png to paint-before-btest.png, writes the new paint.png,
     and the caller re-runs build_player.py so the player picks up the new housing (paint.png is
     the player's ONLY source for the housing pixels -- build_player.py's .phone background is
     paint.png directly, no separate housing asset to regenerate).

Real fal spend: 1 call to fal-ai/gemini-25-flash-image/edit (~$0.04/call, flat per fal's listed
price) per skin. Usage: python3 build_btest_housing.py <assets-dir> [--dry-run]
"""
import argparse, json, os, sys, time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
from erase12 import erase_classical, detect_bbox, _square_crop_box  # noqa: E402

FAL_ENDPOINT = "fal-ai/gemini-25-flash-image/edit"
FAL_PRICE = 0.0398  # fal listed price, confirmed elsewhere in this dir (erase12.py's ERASE_MODEL_CHAIN comment)

HOUSING_PROMPT_TMPL = (
    "This is a crop of a skeuomorphic device control panel, {material}. The bright MAGENTA "
    "shape marks the exact footprint of a two-position slider's housing/trough that must be "
    "carved into the body here. Replace the magenta region with a real RECESSED channel/trough "
    "in the device's own material — same material, colour and lighting as the surrounding body "
    "— carved to EXACTLY the magenta silhouette (do not round it off into a plain pill/oval; "
    "preserve any waist, taper or lobe the magenta outline has). The trough floor should be "
    "darker/recessed relative to the surrounding raised body, with a subtle rim/bevel at the "
    "transition. It must be EMPTY (no lever, no thumb, no bolt installed inside it). Change "
    "absolutely nothing outside the magenta region: same materials, same lighting, same camera "
    "angle, same framing, no new objects, no text."
)


def load_fal_key():
    envp = "/Users/conner/dev/central/.env"
    for line in open(envp):
        line = line.strip()
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("FAL_KEY not found in central/.env")


def swept_housing_mask(canvas_w, canvas_h, lever_alpha_path, track_frac, detents_frac, vertical,
                        n_steps=14, housing_dilate=10, rim_dilate=26):
    """Build the swept (Minkowski-sum-style) housing silhouette directly on a full-canvas-sized
    binary array: union of the lever's OWN alpha silhouette pasted at N positions interpolated
    between the two detents, then dilated for a housing lip + a wider rim ring. Returns
    (housing_mask u8, rim_ring u8, tight_bbox) all canvas_h x canvas_w."""
    lever_im = Image.open(lever_alpha_path).convert("RGBA")
    lever_a = np.asarray(lever_im)[:, :, 3]
    lever_bin = (lever_a > 100).astype(np.uint8)
    lh, lw = lever_bin.shape
    tx, ty, tw, th = track_frac
    track_cx = (tx + tw / 2) * canvas_w
    track_cy = (ty + th / 2) * canvas_h
    d0, d1 = detents_frac
    canvas = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    for i in range(n_steps):
        f = i / (n_steps - 1)
        pos = d0 + (d1 - d0) * f
        if vertical:
            cx, cy = track_cx, pos * canvas_h
        else:
            cx, cy = pos * canvas_w, track_cy
        x0 = int(round(cx - lw / 2)); y0 = int(round(cy - lh / 2))
        x1, y1 = x0 + lw, y0 + lh
        sx0, sy0 = max(0, -x0), max(0, -y0)
        dx0, dy0 = max(0, x0), max(0, y0)
        dx1, dy1 = min(canvas_w, x1), min(canvas_h, y1)
        if dx1 <= dx0 or dy1 <= dy0:
            continue
        sub = lever_bin[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
        canvas[dy0:dy1, dx0:dx1] = np.maximum(canvas[dy0:dy1, dx0:dx1], sub)
    ys, xs = np.where(canvas > 0)
    if len(ys) == 0:
        raise RuntimeError("swept mask is empty — check track/detents/lever inputs")
    pad = housing_dilate + rim_dilate + 8
    bx0, bx1 = max(0, xs.min() - pad), min(canvas_w, xs.max() + pad)
    by0, by1 = max(0, ys.min() - pad), min(canvas_h, ys.max() + pad)

    def dilate(bin_u8, px):
        if px <= 0:
            return bin_u8
        im = Image.fromarray(bin_u8 * 255)
        return (np.asarray(im.filter(ImageFilter.MaxFilter(2 * px + 1))) > 127).astype(np.uint8)

    sub_canvas = canvas[by0:by1, bx0:bx1]
    housing_sub = dilate(sub_canvas, housing_dilate)
    rim_sub = dilate(sub_canvas, housing_dilate + rim_dilate)
    housing_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    rim_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    housing_mask[by0:by1, bx0:bx1] = housing_sub
    rim_mask[by0:by1, bx0:bx1] = rim_sub
    rim_ring = np.clip(rim_mask.astype(int) - housing_mask.astype(int), 0, 1).astype(np.uint8)
    return housing_mask * 255, rim_ring * 255, (bx0, by0, bx1, by1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assets_dir")
    ap.add_argument("--material", default="a dark metal/organic body")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ASSETS = os.path.abspath(args.assets_dir)
    sid = os.path.basename(ASSETS).replace("assets-", "")
    BIREF = ASSETS + "_biref"

    regs = json.load(open(os.path.join(ASSETS, "regions.json")))
    r = regs["regions"]["shuffle"]
    track = r.get("track") or r["device"]
    vertical = bool(r.get("vertical", track[3] > track[2]))
    detents = r.get("detents")
    lever_path = os.path.join(BIREF, "shuffle_lever.png")
    if not detents or not os.path.exists(lever_path):
        sys.exit(f"[btest] {sid}: not a TOGGLE_TRACK skin (missing detents or shuffle_lever.png) — B "
                  f"treatment as written only targets the lever/track architecture")

    paint_path = os.path.join(ASSETS, "paint.png")
    paint = Image.open(paint_path).convert("RGB")
    W, H = paint.size
    print(f"[btest] {sid} canvas {W}x{H} track={track} detents={detents} vertical={vertical}")

    housing_mask, rim_ring, bbox = swept_housing_mask(W, H, lever_path, track, detents, vertical)
    print(f"[btest] swept housing bbox={bbox} housing-px={int((housing_mask>0).sum())} "
          f"rim-px={int((rim_ring>0).sum())}")

    before_path = os.path.join(ASSETS, "paint-before-btest.png")
    if not os.path.exists(before_path):
        paint.save(before_path)
        print(f"[btest] saved pre-treatment backup -> {before_path}")

    # 1. erase the existing (wrong) housing across the full old track bbox
    tx, ty, tw, th = track
    old_bbox = (int(tx * W), int(ty * H), int((tx + tw) * W), int((ty + th) * H))
    erased, _ = erase_classical(paint, old_bbox, pad_frac=0.35)
    erased.save(os.path.join(ASSETS, "_btest_erased.png"))
    print(f"[btest] erased old housing over {old_bbox}")

    if args.dry_run:
        Image.fromarray(housing_mask).save(os.path.join(ASSETS, "_btest_housing_mask.png"))
        Image.fromarray(rim_ring).save(os.path.join(ASSETS, "_btest_rim_mask.png"))
        print("[btest] --dry-run: wrote mask previews, no fal spend")
        return

    # 2. square crop around the swept housing bbox from the ERASED backdrop
    bx0, by0, bx1, by1 = bbox
    cx0, cy0, cx1, cy1 = _square_crop_box(W, H, (bx0, by0, bx1, by1), pad_frac=0.6, min_side=420)
    crop = erased.crop((cx0, cy0, cx1, cy1)).convert("RGB")

    # 3. build the MAGENTA guide image: same crop, with the housing silhouette filled magenta
    guide = crop.copy()
    guide_arr = np.asarray(guide).copy()
    hmask_crop = housing_mask[cy0:cy1, cx0:cx1] > 0
    guide_arr[hmask_crop] = [255, 0, 255]
    guide_img = Image.fromarray(guide_arr)

    tmp_crop = os.path.join(ASSETS, "_btest_crop.png")
    tmp_guide = os.path.join(ASSETS, "_btest_guide.png")
    crop.save(tmp_crop)
    guide_img.save(tmp_guide)

    os.environ["FAL_KEY"] = load_fal_key()
    import fal_client
    crop_url = fal_client.upload_file(tmp_crop)
    guide_url = fal_client.upload_file(tmp_guide)
    prompt = HOUSING_PROMPT_TMPL.format(material=args.material)
    print(f"[btest] calling {FAL_ENDPOINT} (~${FAL_PRICE})")
    t0 = time.time()
    result = fal_client.subscribe(FAL_ENDPOINT, arguments={
        "image_urls": [crop_url, guide_url], "prompt": prompt,
    }, with_logs=False)
    dt = time.time() - t0
    images = result.get("images") or [result.get("image")]
    img_info = images[0]
    url = img_info["url"] if isinstance(img_info, dict) else img_info
    import urllib.request
    data = urllib.request.urlopen(url, timeout=60).read()
    out_path = os.path.join(ASSETS, "_btest_raw_result.png")
    open(out_path, "wb").write(data)
    print(f"[btest] fal result -> {out_path} ({dt:.1f}s)")

    model_out = Image.open(out_path).convert("RGB")
    if model_out.size != crop.size:
        model_out = model_out.resize(crop.size, Image.LANCZOS)
    model_arr = np.asarray(model_out).astype(float)

    # 4. composite: model pixels ONLY within the (feathered) swept housing mask, everything else
    # reverts to the flat ERASED backdrop — guarantees the final silhouette == the swept lever
    # shape regardless of what the model painted outside it.
    from scipy import ndimage as ndi
    full_mask_f = (housing_mask.astype(float) / 255.0)
    full_mask_blur = ndi.gaussian_filter(full_mask_f, sigma=3.0)
    mask_crop = full_mask_blur[cy0:cy1, cx0:cx1][:, :, None]
    erased_crop_arr = np.asarray(erased.crop((cx0, cy0, cx1, cy1)).convert("RGB")).astype(float)
    blended_crop = erased_crop_arr * (1 - mask_crop) + model_arr * mask_crop

    final_arr = np.asarray(erased.convert("RGB")).astype(float).copy()
    final_arr[cy0:cy1, cx0:cx1] = blended_crop
    final_img = Image.fromarray(final_arr.astype(np.uint8))
    final_img.save(paint_path)
    print(f"[btest] {sid}: wrote matched housing -> {paint_path} (spend ~${FAL_PRICE})")

    for p in (tmp_crop, tmp_guide, os.path.join(ASSETS, "_btest_erased.png")):
        try:
            os.remove(p)
        except OSError:
            pass


if __name__ == "__main__":
    main()
