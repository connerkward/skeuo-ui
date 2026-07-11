#!/usr/bin/env python3
"""redetect_knob — fix the knobticks review-page crop-anchoring bug (2026-07-11 rescore).

Root cause the user flagged: score_knobticks.py's knob_crop_box() anchors every crop at the
TEMPLATE's expected knob_center_frac from results.json. Most of these 7 gens have layout
drift (confirmed in axis-rescore.json / adjudication.json), so template-anchored crops frame
the wrong area or clip the knob off-center — exactly the failure sota-eye-review-rule's "Crop
discipline" section warns about (anchor on DETECTED positions, never template-expected ones).

Detection method (material-agnostic, no new generations, $0): each gen's `mask.png` is the
model's OWN region mask, pixel-aligned to paint.png, with the volume-knob's guide colour
(results.json['keys']['vol']) painted as a solid blob -- both at the knob's DEVICE-area socket
AND at the loose cap in the bottom sprite-strip band. This is a far more reliable "where did
the model actually put the knob" signal than a template-anchored guess or a Hough-circle sweep
on the painted texture (which the theme art would confound): classify every mask pixel to its
NEAREST of the gen's 10 known guide colours (handles per-gen colour drift from JPEG/paint
softening), keep pixels nearest to 'vol' within an absolute distance gate (rejects background),
split into device region (top 75%, DEVF) vs strip region (bottom 25%), and take the LARGEST
connected component in each as the real blob. Centroid + sqrt(area/pi) radius -> detected
knob position, independent of the template.

Every detection is written to <dir>/detect.json AND visually spot-checked by eye (Read tool,
outside this script) before being published -- this script only measures and re-cuts; the
human/agent look-and-confirm step happens after running it (see knobticks review notes).

Writes per gen: detect.json, crop-knob.png (raw, re-anchored), crop-knob-labeled.png (studio
overlay), crop-cap-strip.png (re-anchored to the strip-band blob). Updates scores.json in
place (adds "detected", replaces "deterministic" with a center-corrected recompute, keeps the
old one as "deterministic_template_anchored_OLD" for audit).

Usage: python3 redetect_knob.py
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from score_knobticks import detect_ticks, angle_from_12, label_crop  # reuse proven tick detector

DEVF = 0.75          # device region fraction of paint height (genskin.py DEV_H/H)
COLOR_DIST_GATE = 150.0   # abs RGB distance a pixel must be within its nearest-key colour
MIN_BLOB_AREA_FRAC = 0.0008   # of paint area; below this a "detection" is noise, not a knob
MAX_ASPECT = 2.4      # bbox w/h or h/w beyond this -> probably not a clean circular blob


def classify_blob(mask_arr, keys, target_name, y_lo_frac, y_hi_frac):
    """Largest connected component nearest-classified as `target_name`'s guide colour, within
    the given vertical band. Returns dict(found, cx_frac, cy_frac, r_frac, area_px, bbox) or
    dict(found=False)."""
    names = list(keys.keys())
    palette = np.array([keys[n] for n in names], dtype=float)
    h, w, _ = mask_arr.shape
    flat = mask_arr.reshape(-1, 3).astype(float)
    d2 = ((flat[:, None, :] - palette[None, :, :]) ** 2).sum(2)
    nearest = np.argmin(d2, axis=1)
    neardist = np.sqrt(d2[np.arange(len(flat)), nearest])
    tidx = names.index(target_name)
    m = (nearest == tidx) & (neardist < COLOR_DIST_GATE)
    m = m.reshape(h, w)
    y0, y1 = int(h * y_lo_frac), int(h * y_hi_frac)
    band = np.zeros_like(m)
    band[y0:y1, :] = m[y0:y1, :]
    lbl, n = ndimage.label(band)
    if n == 0:
        return {"found": False}
    sizes = ndimage.sum(band, lbl, range(1, n + 1))
    best = int(np.argmax(sizes)) + 1
    area = float(sizes[best - 1])
    if area < MIN_BLOB_AREA_FRAC * h * w:
        return {"found": False, "reason": f"largest component too small ({area:.0f}px, "
                                           f"{area/(h*w)*100:.3f}% of frame)"}
    ys, xs = np.nonzero(lbl == best)
    x0b, x1b, y0b, y1b = xs.min(), xs.max(), ys.min(), ys.max()
    bw, bh = x1b - x0b + 1, y1b - y0b + 1
    aspect = max(bw / max(bh, 1), bh / max(bw, 1))
    if aspect > MAX_ASPECT:
        return {"found": False, "reason": f"largest component too elongated (aspect {aspect:.2f}) "
                                           f"-- likely not a single circular blob"}
    cx, cy = float(xs.mean()), float(ys.mean())
    radius = math.sqrt(area / math.pi)
    return {"found": True, "cx_frac": cx / w, "cy_frac": cy / h, "r_frac": radius / w,
            "area_px": area, "bbox": [int(x0b), int(y0b), int(x1b), int(y1b)],
            "n_components_in_band": int(n)}


def crop_box_for(cx, cy, r, w, h, pad_factor=3.2):
    """Half-width = pad_factor * r -> padding beyond the knob edge = (pad_factor-1)*r >= 2.2r,
    satisfying the >=2x-extent pad the sota-eye-review-rule crop-discipline section requires."""
    half = r * pad_factor
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    return (int(x0), int(y0), int(x1), int(y1))


def process_one(d):
    tag = os.path.basename(d).replace("assets-knobticks-", "")
    paint_p, mask_p = os.path.join(d, "paint.png"), os.path.join(d, "mask.png")
    if not (os.path.exists(paint_p) and os.path.exists(mask_p)):
        print(f"[{tag}] no paint/mask -- generation failure, nothing to re-crop (unchanged)")
        return None
    res = json.load(open(os.path.join(d, "results.json")))
    keys = res["keys"]
    paint = Image.open(paint_p).convert("RGB")
    mask_im = Image.open(mask_p).convert("RGB")
    w, h = paint.size
    assert mask_im.size == (w, h), f"{tag}: mask/paint size mismatch {mask_im.size} vs {(w,h)}"
    mask_arr = np.asarray(mask_im)

    device = classify_blob(mask_arr, keys, "vol", 0.0, DEVF)
    strip = classify_blob(mask_arr, keys, "vol", DEVF, 1.0)

    tfx, tfy = res["knob_center_frac"]; tr = res["knob_r_frac"]
    template = {"cx_frac": tfx, "cy_frac": tfy, "r_frac": tr}

    out = {"tag": tag, "method": "mask_guide_color_nearest_classify_largest_component",
           "template": template, "device_detection": device, "strip_detection": strip}

    if device["found"]:
        cx, cy, r = device["cx_frac"] * w, device["cy_frac"] * h, device["r_frac"] * w
        tcx, tcy = tfx * w, tfy * h
        dx_px, dy_px = cx - tcx, cy - tcy
        dist_px = math.hypot(dx_px, dy_px)
        out["offset_vs_template"] = {
            "dx_px": round(dx_px, 1), "dy_px": round(dy_px, 1), "dist_px": round(dist_px, 1),
            "dx_frac": round(dx_px / w, 4), "dy_frac": round(dy_px / h, 4),
            "dist_frac_of_width": round(dist_px / w, 4),
            "dist_in_knob_radii": round(dist_px / (tr * w), 2),
        }
        box = crop_box_for(cx, cy, r, w, h)
        crop = paint.crop(box)
        crop.save(os.path.join(d, "crop-knob.png"))
        cx_local, cy_local = cx - box[0], cy - box[1]
        det = detect_ticks(crop, cx_local, cy_local, r)
        out["deterministic_ticks_recentered"] = det
        labeled = label_crop(crop, [
            f"{tag}", f"DETECTED (mask centroid), NOT template",
            f"offset vs template: {out['offset_vs_template']['dist_in_knob_radii']}x radius "
            f"(dx={out['offset_vs_template']['dx_frac']:+.3f} dy={out['offset_vs_template']['dy_frac']:+.3f} frac)",
            f"ring={det['ring_radius_factor']} peaks={det['n_peaks']} span={det['span_deg']}",
            "STUDIO OVERLAY - not sent to model"])
        labeled.save(os.path.join(d, "crop-knob-labeled.png"))
        out["crop_box_device"] = list(box)
        out["detection_failed"] = False
    else:
        # sota-eye-review-rule: a failed detection must NOT ship a silently-wrong crop --
        # fall back to showing the full paint, clearly labeled.
        out["detection_failed"] = True
        out["deterministic_ticks_recentered"] = {"ring_radius_factor": None, "n_peaks": 0,
                                                   "peak_degs": [], "span_deg": None}
        fallback = paint.copy()
        d_draw = ImageDraw.Draw(fallback)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        except Exception:
            font = ImageFont.load_default()
        msg = f"DETECTION FAILED -- full frame shown ({device.get('reason','no vol-colour blob found')})"
        d_draw.rectangle([0, 0, w, 90], fill=(0, 0, 0))
        d_draw.text((16, 16), msg, fill=(255, 210, 60), font=font)
        fallback.save(os.path.join(d, "crop-knob.png"))
        fallback.save(os.path.join(d, "crop-knob-labeled.png"))
        out["crop_box_device"] = None
        print(f"[{tag}] DEVICE DETECTION FAILED: {device.get('reason')}")

    if strip["found"]:
        scx, scy, sr = strip["cx_frac"] * w, strip["cy_frac"] * h, strip["r_frac"] * w
        sbox = crop_box_for(scx, scy, sr, w, h, pad_factor=2.6)
        paint.crop(sbox).save(os.path.join(d, "crop-cap-strip.png"))
        out["crop_box_strip"] = list(sbox)
    else:
        out["crop_box_strip"] = None
        print(f"[{tag}] STRIP (cap) DETECTION FAILED: {strip.get('reason')} -- leaving old crop-cap-strip.png")

    json.dump(out, open(os.path.join(d, "detect.json"), "w"), indent=2)
    print(f"[{tag}] device_found={device['found']} strip_found={strip['found']} "
          f"offset={out.get('offset_vs_template')}")
    return out


def main():
    dirs = sorted(d for d in os.listdir(HERE) if d.startswith("assets-knobticks-"))
    results = {}
    for dn in dirs:
        r = process_one(os.path.join(HERE, dn))
        if r:
            results[r["tag"]] = r

    # fold the recentered detection into scores.json (preserve the old crop-derived
    # deterministic reading for audit, per human-labeled-data-rule "never lose data")
    scores_p = os.path.join(HERE, "scores.json")
    scores = json.load(open(scores_p))
    for rec in scores:
        det = results.get(rec["tag"])
        if not det:
            continue
        rec["deterministic_template_anchored_OLD"] = rec.get("deterministic")
        rec["deterministic"] = det["deterministic_ticks_recentered"]
        rec["detected_knob"] = {
            "device": det["device_detection"], "strip": det["strip_detection"],
            "offset_vs_template": det.get("offset_vs_template"),
            "detection_failed": det["detection_failed"],
        }
    json.dump(scores, open(scores_p, "w"), indent=2)
    print(f"\n[redetect_knob] updated scores.json for {len(results)} gens")


if __name__ == "__main__":
    main()
