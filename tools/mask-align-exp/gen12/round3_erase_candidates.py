#!/usr/bin/env python3
"""round3_erase_candidates — build NON-DESTRUCTIVE erase-candidate previews for the round-3
review page. For each confirmed-baked-thumb skin, runs the two valid eraser tiers named in the
round-3 task (Vertex $0.134/repair via erase12.py's own erase_model(); Bria Eraser $0.04/
generation, fal-ai/bria/eraser — see docs/experiments/2026-07-12-inpaint-bakeoff.md), composites
each result back onto the FULL skin using the SAME feathered-composite math erase12.py's
erase_model() uses (mirrored here, not reimplemented differently), and writes:
  round3-erase/<skin>/candidate-vertex.png   (full paint.png-sized composite, candidate A)
  round3-erase/<skin>/candidate-bria.png     (full paint.png-sized composite, candidate B)
  round3-erase/<skin>/seam-vertex.png, seam-bria.png   (4x upscaled seam crops for review)
  round3-erase/erase-candidates.json          (per-skin cost, seam-delta, paths)

Does NOT write assets-<skin>/paint.png — production is untouched; the review page lets the
human pick a candidate (or none) via the accept/reject controls (generation-spend-rule +
"do not commit" per this task's brief).

Usage: python3 round3_erase_candidates.py claymation fallout-vault steam-porthole ...
"""
import io, json, os, re, sys, time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import erase12  # reuse detect_bbox / _square_crop_box / erase_model / seam_delta / sha12 verbatim

OUT_DIR = os.path.join(HERE, "round3-erase")
os.makedirs(OUT_DIR, exist_ok=True)

VERTEX_PRICE = 0.134
BRIA_PRICE = 0.04


def load_fal_key():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise RuntimeError("FAL_KEY not found in central/.env")


def feathered_composite(paint_img, out_square, cx0, cy0, cx1, cy1):
    """Verbatim port of erase12.py:erase_model()'s tail — soft alpha ramp (full-strength
    interior, fading to 0 over the outer ~12% margin) so the composite boundary lands on a
    smooth gradient instead of a hard edge. Kept as a standalone function (not imported from
    erase12 directly) so a non-Vertex candidate — Bria here — gets the IDENTICAL composite
    math without erase12.py needing a refactor mid-flight while other agents may be using it."""
    out_arr = np.asarray(out_square).astype(float)
    side = out_arr.shape[0]
    margin = max(4, int(side * 0.12))
    ramp = np.ones(side)
    ramp[:margin] = np.linspace(0, 1, margin)
    ramp[-margin:] = np.linspace(1, 0, margin)
    alpha = np.minimum(ramp[:, None], ramp[None, :])[:, :, None]
    base_arr = np.asarray(paint_img.convert("RGB")).astype(float)
    region = base_arr[cy0:cy1, cx0:cx1]
    blended = region * (1 - alpha) + out_arr * alpha
    new_arr = base_arr.copy()
    new_arr[cy0:cy1, cx0:cx1] = blended
    return Image.fromarray(new_arr.astype(np.uint8))


def erase_bria(assets_dir, paint_img, bbox, fal_client):
    """fal-ai/bria/eraser: image_url + mask_url (binary, white=erase), no prompt. Same square
    crop framing as erase12.erase_model() (ai-image-coords-rule: square avoids any aspect
    mismatch), same feathered composite-back."""
    import cv2
    W, H = paint_img.size
    cx0, cy0, cx1, cy1 = erase12._square_crop_box(W, H, bbox)
    crop = paint_img.crop((cx0, cy0, cx1, cy1)).convert("RGB")
    x0, y0, x1, y1 = bbox
    mask = np.zeros((cy1 - cy0, cx1 - cx0), np.uint8)
    mx0, my0 = max(0, x0 - cx0), max(0, y0 - cy0)
    mx1, my1 = min(cx1 - cx0, x1 - cx0), min(cy1 - cy0, y1 - cy0)
    mask[my0:my1, mx0:mx1] = 255
    mask = cv2.dilate(mask, np.ones((9, 9), np.uint8), iterations=2)
    mask_img = Image.fromarray(mask)

    tmp_img = os.path.join(assets_dir, "_round3_bria_crop_in.png")
    tmp_mask = os.path.join(assets_dir, "_round3_bria_mask_in.png")
    crop.save(tmp_img)
    mask_img.save(tmp_mask)
    img_url = fal_client.upload_file(tmp_img)
    mask_url = fal_client.upload_file(tmp_mask)
    result = fal_client.subscribe("fal-ai/bria/eraser",
                                   arguments={"image_url": img_url, "mask_url": mask_url,
                                              "mask_type": "manual"},
                                   with_logs=False)
    img_info = result.get("image") or (result.get("images") or [None])[0]
    url = img_info["url"] if isinstance(img_info, dict) else img_info
    import urllib.request
    data = urllib.request.urlopen(url, timeout=60).read()
    out = Image.open(io.BytesIO(data)).convert("RGB").resize(crop.size, Image.LANCZOS)
    for p in (tmp_img, tmp_mask):
        try:
            os.remove(p)
        except OSError:
            pass
    composited = feathered_composite(paint_img, out, cx0, cy0, cx1, cy1)
    return composited, (cx0, cy0, cx1, cy1)


def save_seam_crop(paint_img, box, path, upscale=4, pad=24):
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(paint_img.width, x1 + pad), min(paint_img.height, y1 + pad)
    c = paint_img.crop((x0, y0, x1, y1))
    c = c.resize((c.width * upscale, c.height * upscale), Image.LANCZOS)
    c.save(path)


def main():
    skins = sys.argv[1:]
    if not skins:
        raise SystemExit("usage: round3_erase_candidates.py <skin> [<skin> ...]")
    os.environ["FAL_KEY"] = load_fal_key()
    import fal_client

    results = {}
    total_cost = 0.0
    for skin in skins:
        assets_dir = os.path.join(HERE, f"assets-{skin}")
        regs = json.load(open(os.path.join(assets_dir, "regions.json")))
        r = regs["regions"]["seek"]
        paint_img = Image.open(os.path.join(assets_dir, "paint.png")).convert("RGB")
        paint_arr = np.asarray(paint_img)
        vertical = r.get("vertical")
        bbox = erase12.detect_bbox(paint_arr, r["device"], vertical=vertical)
        if bbox is None:
            # deterministic detector found nothing compact (expected — these skins were
            # flagged by the VLM/gate-OR, not necessarily the classical detector); fall back
            # to the full device window so a candidate can still be built for review.
            H, W = paint_arr.shape[:2]
            bbox = erase12._device_window(r["device"], W, H)
            print(f"[round3-erase] {skin}: detect_bbox found nothing compact, using full device window {bbox}")
        else:
            print(f"[round3-erase] {skin}: detected bbox {bbox}")

        skin_dir = os.path.join(OUT_DIR, skin)
        os.makedirs(skin_dir, exist_ok=True)
        entry = {"bbox_px": list(bbox)}

        seed = 71
        results_path = os.path.join(assets_dir, "results.json")
        if os.path.exists(results_path):
            seed = json.load(open(results_path)).get("seed", 71)

        # --- Vertex ---
        t0 = time.time()
        try:
            vertex_img, vcrop = erase12.erase_model(assets_dir, paint_img, bbox, seed)
            vertex_img.save(os.path.join(skin_dir, "candidate-vertex.png"))
            save_seam_crop(vertex_img, vcrop, os.path.join(skin_dir, "seam-vertex.png"))
            seam_v = erase12.seam_delta(np.asarray(vertex_img), bbox)
            still_v = erase12.detect_bbox(np.asarray(vertex_img), r["device"], vertical=vertical) is not None
            entry["vertex"] = {"cost": VERTEX_PRICE, "seconds": round(time.time() - t0, 1),
                                "seam_delta": round(seam_v, 1), "still_flagged": bool(still_v),
                                "crop_box_px": list(vcrop)}
            total_cost += VERTEX_PRICE
            print(f"[round3-erase] {skin}: vertex candidate OK seam={seam_v:.1f} still_flagged={still_v}")
        except Exception as e:
            entry["vertex"] = {"error": str(e)}
            print(f"[round3-erase] {skin}: vertex FAILED: {e}")

        # --- Bria ---
        t0 = time.time()
        try:
            bria_img, bcrop = erase_bria(assets_dir, paint_img, bbox, fal_client)
            bria_img.save(os.path.join(skin_dir, "candidate-bria.png"))
            save_seam_crop(bria_img, bcrop, os.path.join(skin_dir, "seam-bria.png"))
            seam_b = erase12.seam_delta(np.asarray(bria_img), bbox)
            still_b = erase12.detect_bbox(np.asarray(bria_img), r["device"], vertical=vertical) is not None
            entry["bria"] = {"cost": BRIA_PRICE, "seconds": round(time.time() - t0, 1),
                              "seam_delta": round(seam_b, 1), "still_flagged": bool(still_b),
                              "crop_box_px": list(bcrop)}
            total_cost += BRIA_PRICE
            print(f"[round3-erase] {skin}: bria candidate OK seam={seam_b:.1f} still_flagged={still_b}")
        except Exception as e:
            entry["bria"] = {"error": str(e)}
            print(f"[round3-erase] {skin}: bria FAILED: {e}")

        # before crop, for the review page's side-by-side
        save_seam_crop(paint_img, bbox, os.path.join(skin_dir, "seam-before.png"))
        results[skin] = entry
        print(f"[round3-erase] {skin}: done, running total ${total_cost:.3f}")
        if total_cost > 0.6:
            print(f"[round3-erase] WARNING: approaching $0.6 spend cap (${total_cost:.3f}) — stopping")
            break

    json.dump({"skins": results, "total_cost": round(total_cost, 3),
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
              open(os.path.join(OUT_DIR, "erase-candidates.json"), "w"), indent=2)
    print(f"[round3-erase] DONE total_cost=${total_cost:.3f} -> {OUT_DIR}/erase-candidates.json")


if __name__ == "__main__":
    main()
