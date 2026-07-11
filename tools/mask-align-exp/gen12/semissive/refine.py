#!/usr/bin/env python3
"""semissive/refine.py — Stage 2: GEOMETRIC REFINER + composite.

For each region judge.py named, one fal-ai/sam-3/image call: native text `prompt` (the
judge's label) + `box_prompts` seeded from the judge's rough box (padded ~20%, per the
research doc). $0.005/call.

EMPIRICAL FINDING (2026-07-11, logged in the experiment record): SAM-3's text-prompt
grounding operates at OBJECT/PART granularity, not sub-object MATERIAL granularity. Tested
live on diablo-gothic's rune band — regardless of prompt wording ("glowing red rune glyphs"
vs "bright orange glowing rune strokes, not the grey stone"), SAM-3 returned the whole raised
stone horn the runes are carved on (coverage ~0.6-0.9% of the full image, bbox matching the
judge's seed almost exactly), not just the glyph strokes. This is CORRECT SAM-3 behavior (it
segments "the object"), just not the granularity the research doc's "crisp mask" language
implied. Fix, layered here (Stage 2b): treat the SAM mask as a TRUSTED ROI ("the judge said
something in here should glow"), then apply a lightweight, DETERMINISTIC local hue+brightness
gate STRICTLY WITHIN that ROI (never expanding past its boundary) to pick the actually-warm/
bright sub-pixels. This is the same relative/local-gating principle pbr_pass.py's top-hat
used — but now correctly SCOPED to the judge-named object instead of the whole image, which
is exactly what fixes the classical pass's false-positive failure mode (fa-pod's uniformly-
bright shell reading as "more glow" than diablo's actual glyphs) while staying crisp.

Composites the per-region refined masks x judge color/intensity into emissive.png, matching
pbr_pass.py's OWN contract (RGBA: RGB = glow-blended color, alpha = coverage mask) and a
lights[] point-light list shaped like pbr_pass.py's meta.json (uv/color/energy) — same file
NAME/FORMAT, written to semissive/out/<id>/, never touching pbr_pass.py or its outputs.

Usage: python3 refine.py <skin-id> [<skin-id> ...] [--min-score 0.5]
"""
import json
import os
import sys
import time

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

from common import (hex_to_rgb01, hue_window, load_fal, load_skin, record_cost, rgb01_to_hue,
                     skin_paths, smoothstep, upload_fal)

SAM_MODEL = "fal-ai/sam-3/image"
SAM_URL = f"https://queue.fal.run/{SAM_MODEL}"
SAM_COST_USD = 0.005
PAD_FRAC = 0.20        # box padding, per research doc
MIN_SCORE = 0.5        # below this, drop the region (sam_snap.py precedent: MIN_SCORE=0.55)
LOCAL_GATE_MIN_FRAC = 0.05   # if the local hue+brightness gate keeps <5% of the SAM ROI,
                             # fall back to the raw SAM mask (never emit an empty glow silently)


def font(sz):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", sz)
    except Exception:
        return ImageFont.load_default()


def sam_call(fal_key, image_url, prompt, box_px):
    payload = {
        "image_url": image_url, "prompt": prompt,
        "box_prompts": [{"x_min": box_px[0], "y_min": box_px[1],
                          "x_max": box_px[2], "y_max": box_px[3]}],
        "apply_mask": False, "include_boxes": True, "include_scores": True,
        "return_multiple_masks": False,
    }
    sub = requests.post(SAM_URL, headers={"Authorization": f"Key {fal_key}",
                                           "Content-Type": "application/json"},
                         json=payload).json()
    t0 = time.time()
    while True:
        st = requests.get(sub["status_url"], headers={"Authorization": f"Key {fal_key}"}).json()
        if st.get("status") == "COMPLETED":
            break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 90:
            raise RuntimeError(f"SAM-3 failed: {st}")
        time.sleep(1.2)
    return requests.get(sub["response_url"], headers={"Authorization": f"Key {fal_key}"}).json()


def local_gate(src, val, sat, hue, mask_bool, color_hex):
    """Stage 2b — deterministic hue+brightness+saturation gate STRICTLY inside mask_bool.
    Returns a float gate in [0,1], zero outside mask_bool. See module docstring for why this
    exists: SAM-3's text-prompt grounding returns the whole OBJECT (e.g. the stone horn the
    runes are carved on), not the glyph strokes themselves — this isolates the genuinely
    bright+saturated+on-hue sub-pixels within that trusted ROI. Percentile thresholds are
    HIGH (80th) and ANDed across three signals (not just brightness) so a warm-toned but
    desaturated stone highlight doesn't get swept in with the actual glyphs — tested live on
    diablo-gothic: a 55th-percentile brightness-only gate washed ~45% of the ROI orange
    (whole-panel glow, not glyph-shaped); this tighter 3-way gate is what actually isolates
    the glyphs (see experiment record for the before/after)."""
    if not mask_bool.any():
        return np.zeros(val.shape, np.float32), False
    hc = rgb01_to_hue(hex_to_rgb01(color_hex))
    hmask = hue_window(hue, hc, 30)
    vals_in, sats_in = val[mask_bool], sat[mask_bool]
    v_thr = float(np.percentile(vals_in, 80))
    s_thr = float(np.percentile(sats_in, 75))
    bright = smoothstep(v_thr * 0.92, max(v_thr * 1.06, v_thr + 0.02), val)
    saturated = smoothstep(s_thr * 0.85, max(s_thr * 1.05, s_thr + 0.03), sat)
    gate = hmask * bright * saturated
    gate[~mask_bool] = 0
    kept_frac = float((gate > 0.35).sum()) / max(1, mask_bool.sum())
    fallback = False
    if kept_frac < LOCAL_GATE_MIN_FRAC:
        gate = mask_bool.astype(np.float32) * 0.7   # raw SAM ROI at reduced intensity
        fallback = True
    return gate, fallback


def refine_one(sid, min_score=MIN_SCORE):
    p, regs, spec = load_skin(sid)
    judge_path = os.path.join(p["out_dir"], "judge.json")
    if not os.path.exists(judge_path):
        raise SystemExit(f"no judge.json for {sid} — run judge.py first")
    judge = json.load(open(judge_path))
    src_path = os.path.join(p["out_dir"], "src.png")
    src_im = Image.open(src_path).convert("RGB")
    W, H = src_im.size
    src = np.asarray(src_im, np.float32) / 255.0
    val = src.max(axis=-1)
    mn = src.min(axis=-1)
    d = np.maximum(val - mn, 1e-6)
    sat = np.where(val > 0, (val - mn) / np.maximum(val, 1e-6), 0)
    r_, g_, b_ = src[..., 0], src[..., 1], src[..., 2]
    hue = np.zeros((H, W), np.float32)
    m = val == r_; hue[m] = (60 * ((g_ - b_) / d) % 360)[m]
    m = val == g_; hue[m] = (60 * ((b_ - r_) / d) + 120)[m]
    m = val == b_; hue[m] = (60 * ((r_ - g_) / d) + 240)[m]

    fal_key = load_fal()
    img_url = upload_fal(src_path, fal_key)

    mask_dir = os.path.join(p["out_dir"], "masks")
    os.makedirs(mask_dir, exist_ok=True)

    em_rgb = src.copy()
    em_alpha = np.zeros((H, W), np.float32)
    lights = []
    region_records = []
    sam_calls = 0

    draw_im = src_im.copy()
    drw = ImageDraw.Draw(draw_im, "RGBA")

    for i, reg in enumerate(judge.get("emissive_regions", [])):
        box = reg["box"]
        bx0 = max(0.0, box["x"] - box["w"] * PAD_FRAC)
        by0 = max(0.0, box["y"] - box["h"] * PAD_FRAC)
        bx1 = min(1.0, box["x"] + box["w"] * (1 + PAD_FRAC))
        by1 = min(1.0, box["y"] + box["h"] * (1 + PAD_FRAC))
        box_px = [round(bx0 * W), round(by0 * H), round(bx1 * W), round(by1 * H)]
        label = reg.get("label", f"region{i}")

        res = sam_call(fal_key, img_url, label, box_px)
        sam_calls += 1
        result = res.get("result", res)  # run_model/queue shapes both land here
        scores = result.get("scores") or []
        masks = result.get("masks") or []
        score = scores[0] if scores else 0.0
        slug = "".join(c if c.isalnum() else "-" for c in label.lower()).strip("-")[:40] or f"r{i}"

        rec = {"label": label, "why": reg.get("why", ""), "color_hex": reg.get("color_hex"),
               "intensity_0_1": reg.get("intensity_0_1"), "pulse": reg.get("pulse"),
               "judge_box": box, "box_px_padded": box_px, "sam_score": score}

        # box-color for the overlay, drawn regardless of keep/drop
        judge_box_px = [box["x"] * W, box["y"] * H, (box["x"] + box["w"]) * W, (box["y"] + box["h"]) * H]

        if score < min_score or not masks:
            rec["kept"] = False
            rec["drop_reason"] = "low_score" if masks else "no_mask_returned"
            region_records.append(rec)
            drw.rectangle(judge_box_px, outline=(255, 60, 60, 255), width=3)
            drw.text((judge_box_px[0] + 4, judge_box_px[1] + 4), f"{label} DROPPED ({score:.2f})",
                      fill=(255, 255, 255, 255), font=font(26),
                      stroke_width=3, stroke_fill=(120, 0, 0, 255))
            continue

        mask_url = masks[0]["url"]
        mask_png = os.path.join(mask_dir, f"{slug}-sam.png")
        open(mask_png, "wb").write(requests.get(mask_url).content)
        sam_mask = np.asarray(Image.open(mask_png).convert("L")) > 127

        gate, fallback = local_gate(src, val, sat, hue, sam_mask, reg.get("color_hex", "#ffffff"))
        gate_feathered = np.asarray(
            Image.fromarray((np.clip(gate, 0, 1) * 255).astype(np.uint8))
            .filter(ImageFilter.GaussianBlur(2.0)), np.float32) / 255
        Image.fromarray((gate_feathered * 255).astype(np.uint8), "L").save(
            os.path.join(mask_dir, f"{slug}-refined.png"))

        intensity = float(np.clip(reg.get("intensity_0_1", 0.8), 0, 1)) * float(np.clip(score / 0.8, 0.4, 1))
        color = np.array(hex_to_rgb01(reg.get("color_hex", "#ffffff")), np.float32)
        core = gate_feathered * intensity
        em_rgb = np.clip(em_rgb + core[..., None] * color * 1.15, 0, 1)
        em_alpha = np.maximum(em_alpha, core)

        en = gate_feathered * val
        tot_en = float(en.sum())
        if tot_en > 0:
            ys, xs = np.where(gate_feathered > 0.05)
            w_ = en[ys, xs]
            cx = float((xs * w_).sum() / w_.sum()); cy = float((ys * w_).sum() / w_.sum())
            lights.append({"uv": [round(cx / W, 4), round(cy / H, 4)],
                            "color": [round(float(c), 3) for c in color],
                            "energy_raw": tot_en, "label": label})

        rec["kept"] = True
        rec["sam_coverage_frac"] = round(float(sam_mask.mean()), 5)
        rec["refined_coverage_frac"] = round(float((gate_feathered > 0.35).mean()), 5)
        rec["local_gate_fallback_to_raw_sam"] = fallback
        region_records.append(rec)

        sb = result.get("boxes") or []
        if sb:
            cx_, cy_, w_, h_ = sb[0]
            sam_box_px = [(cx_ - w_ / 2) * W, (cy_ - h_ / 2) * H, (cx_ + w_ / 2) * W, (cy_ + h_ / 2) * H]
            drw.rectangle(sam_box_px, outline=(80, 255, 120, 255), width=3)
        drw.rectangle(judge_box_px, outline=(255, 210, 60, 180), width=2)
        lx, ly = judge_box_px[0] + 4, judge_box_px[1] + 4
        tag = f"{label} kept score={score:.2f}" + (" (gate->raw-SAM)" if fallback else "")
        drw.text((lx, ly), tag, fill=(255, 255, 255, 255), font=font(26),
                  stroke_width=3, stroke_fill=(0, 90, 20, 255))

    # normalize light energies to sum 1 (pbr_pass.py convention)
    tot = sum(l["energy_raw"] for l in lights) or 1.0
    for l in lights:
        l["energy"] = round(l.pop("energy_raw") / tot, 3)

    coverage = float(em_alpha.mean())
    Image.fromarray(np.dstack([(em_rgb * 255).astype(np.uint8),
                                (em_alpha * 255).astype(np.uint8)]), "RGBA").save(
        os.path.join(p["out_dir"], "emissive.png"))

    preview = src_im.convert("RGBA")
    preview.alpha_composite(Image.open(os.path.join(p["out_dir"], "emissive.png")))
    preview.convert("RGB").save(os.path.join(p["out_dir"], "preview.png"))

    # legend
    drw.rectangle([8, H - 70, 640, H - 8], fill=(0, 0, 0, 160))
    drw.text((16, H - 60), "green=SAM box (kept)  yellow=judge seed box  red=dropped",
              fill=(255, 255, 255, 255), font=font(22))
    draw_im.save(os.path.join(p["out_dir"], "overlay.png"))

    sam_cost = round(sam_calls * SAM_COST_USD, 5)
    refine_record = {
        "skin": sid, "sam_model": SAM_MODEL, "sam_calls": sam_calls,
        "sam_cost_usd": sam_cost, "min_score": min_score, "pad_frac": PAD_FRAC,
        "local_gate_min_frac": LOCAL_GATE_MIN_FRAC,
        "regions": region_records, "lights": lights, "emissiveCoverage": round(coverage, 5),
        "size": [W, H], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    json.dump(refine_record, open(os.path.join(p["out_dir"], "refine.json"), "w"), indent=2)
    record_cost(p["out_dir"], "refine_sam", sam_cost, f"{sam_calls} SAM-3 calls")
    kept = sum(1 for r in region_records if r.get("kept"))
    print(f"[refine] {sid}: {kept}/{len(region_records)} kept, {sam_calls} SAM calls "
          f"(${sam_cost}), coverage={coverage:.5f} -> "
          f"{os.path.join(p['out_dir'], 'refine.json')}")
    return refine_record


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit("usage: refine.py <skin-id> [<skin-id> ...]")
    for sid in args:
        refine_one(sid)
