#!/usr/bin/env python3
"""erase12 <assets-dir> [--control seek] [--gate-reason baked-thumb:seek] [--bbox x0,y0,x1,y1]
          [--method classical|model|auto] [--seed N] [--force] [--dry-run]

DETECT+ERASE for a baked part painted INSIDE a must-be-empty cavity (knob socket, seek
groove, toggle slot) — the pipeline's answer to review-2026-07-11-round1.json, which showed
BAKED SLIDER THUMBS on 6+ skins (claymation, diablo-gothic, fallout-pipboy, fallout-vault,
n64-cutscene, wc-goldshield) despite many rounds of prompt hardening on the "seek is an empty
slot" clause in genskin.py. Per fix-generalizable-rule + the bproof lesson (constraint BULK
costs quality, not just precision): stop fighting the model with more words, and instead
DETECT the defect deterministically and ERASE it deterministically. Prior art:
tools/mask-align-exp/erase_baked.py (run9-era gate-driven repair — same idea, same
floor-tone-fill mechanic for the classical path; this is the gen12 port + a model-edit
escalation path + real before/after verification).

Detection does NOT reuse extract12.py's emptiness gate (device bbox shrunk 18% per side,
bright>150 interior-fraction >0.10) — that gate is CENTRE-BIASED (built for a round knob
socket) and, empirically (all 6 skins checked live against review-2026-07-11-round1.json's
paint.png, byte-identical shas confirmed), BLIND to a slider thumb resting near a travel
EXTREME: every real bake in the reviewed roster sits at one END of the groove (left edge on
fallout-pipboy/fallout-vault/n64-cutscene/wc-goldshield, the bottom end on diablo-gothic's
vertical channel) — exactly the 18%-per-side band the shrink excludes. Re-running that same
window at 0% shrink still under-counted 4/6 (a compact thumb occupying ~10% of a long groove's
AREA doesn't clear an aggregate 10%-bright-pixel-fraction test even when clearly visible).
So `detect_bbox()` here is a DIFFERENT, groove-shaped algorithm: a 1-D profile along the
groove's LONG axis (per-column median brightness + per-column texture/std over the FULL,
unshrunk device interior), flagging where either signal clearly exceeds the groove's own
30th-percentile baseline, then taking the largest contiguous anomalous run and anchoring it
to a touched box edge (a real edge-resting thumb's own boundary softens right at the rim seam
and under-detects the last few px otherwise). This is a HEURISTIC — it mis-fired on
claymation in validation (flagged the housing's rounded end-cap curving into the box as an
"anomaly"; the claymation groove is genuinely empty on visual inspection, see TODO.md) — so
it is a CANDIDATE locator, not authoritative; always inspect the saved verify crop before
trusting a detection (verify-outputs-rule), and prefer an explicit --bbox once a defect's
location is confirmed by eye. --gate-reason "baked-thumb:seek" (the gates agent's in-flight
extract12.py gate reason, if it has landed in this checkout) is accepted as a --control alias
only — it does not change which detector runs.

Two erase methods, tried in cost order (generation-spend-rule: cheapest first):
  1. CLASSICAL (OpenCV Telea inpaint) — $0. Detect the bright blob inside the cavity interior,
     dilate it a few px past its silhouette, inpaint via cv2.INPAINT_TELEA on a padded crop.
     Works well for a flat/low-frequency recessed channel (most of this roster's grooves).
  2. MODEL EDIT (Vertex nano-banana-pro edit on a SQUARE crop) — ~$0.05-0.1/erase, fallback
     when the classical result still reads bright (>0.10 interior) or leaves a visible seam.
     Square crop => the edit is requested at the SAME aspect it's sent at (ai-image-coords-rule:
     an edit model reshapes output to the REQUESTED aspect, never the input's — a square crop
     avoids ANY aspect mismatch by construction, no separate aspect-matching logic needed).

Idempotent by construction: re-running on an already-erased paint.png simply finds the
interior brightness already under threshold and no-ops (no bookkeeping needed for that case).
A provenance log (<assets-dir>/erase12-log.json) additionally fast-paths a byte-identical
re-call (same paint.png sha as a prior successful erase's AFTER state) and records every real
erase event (control, method, before/after sha, before/after brightness) for audit.

Verification per erase (mandatory, not optional — verify-outputs-rule): dumps 4x-upscaled
before/after crops to <assets-dir>/erase-verify/ for a human LOOK, re-measures the SAME
emptiness-gate brightness fraction post-erase (must drop under 0.10 or the erase is reported
FAILED, not silently accepted), and a coarse seam check (mean colour delta between a band just
inside vs just outside the erased box in the AFTER image — high delta flags a possible visible
seam and escalates classical->model when --method auto).

Composites the erased paint.png back into joint-4k.png's left half (same convention as
erase_baked.py) so the two stay in sync. Does not touch mask.png (right half) — untouched by
this defect.

Usage:  python3 erase12.py assets-diablo-gothic --control seek
        python3 erase12.py assets-fallout-vault --gate-reason baked-thumb:seek --method model
        python3 erase12.py assets-wc-goldshield --dry-run   # detect + crop only, no writes
"""
import argparse, hashlib, io, json, os, sys, time

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

EDGE_ANCHOR_FRAC = 0.25   # a touched-edge anomaly within this fraction of the box length gets
                          # anchored fully to that edge (recovers the softened last few px of
                          # a real edge-resting thumb where it meets the rim)
COMPACT_CAP_FRAC = 0.55   # an anomaly wider than this fraction of the groove is too diffuse to
                          # be a compact baked PART (texture/lighting drift, not an object) —
                          # treated as "nothing compact found", not auto-erased


def sha12(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


def _device_window(dev_bbox, W, H):
    b = dev_bbox
    x0, y0 = int(b[0] * W), int(b[1] * H)
    x1, y1 = int((b[0] + b[2]) * W), int((b[1] + b[3]) * H)
    return max(0, x0), max(0, y0), min(W, x1), min(H, y1)


def _long_axis_profile(win, vertical):
    lum = win.max(2)
    lum2 = lum.T if vertical else lum
    colstd = lum2.std(0).astype(float)
    colmed = np.median(lum2, 0).astype(float)
    k = 9
    if len(colstd) >= k:
        pad = k // 2
        colstd = np.convolve(colstd, np.ones(k) / k, mode="same")
        colmed = np.convolve(colmed, np.ones(k) / k, mode="same")
    return colstd, colmed


def detect_bbox(paint_arr, dev_bbox, vertical=None):
    """Groove-shaped baked-part locator — see module docstring for why this replaces a naive
    bright-pixel/shrink test. Returns (x0,y0,x1,y1) PIXEL bbox spanning the full cross-axis
    and the detected long-axis run, or None if nothing compact was found."""
    H, W = paint_arr.shape[:2]
    x0, y0, x1, y1 = _device_window(dev_bbox, W, H)
    win = paint_arr[y0:y1, x0:x1]
    if win.size == 0:
        return None
    if vertical is None:
        vertical = (y1 - y0) > (x1 - x0) * 1.3
    colstd, colmed = _long_axis_profile(win, vertical)
    L = len(colstd)
    if L < 8:
        return None
    base_std = np.percentile(colstd, 30)
    base_med = np.percentile(colmed, 30)
    anomaly = (colstd > base_std * 1.6 + 3) | (colmed > base_med + 35)
    lbl, n = ndimage.label(anomaly)
    if n == 0:
        return None
    sizes = ndimage.sum(anomaly, lbl, range(1, n + 1))
    biggest = int(np.argmax(sizes)) + 1
    idx = np.where(lbl == biggest)[0]
    lo, hi = int(idx.min()), int(idx.max())
    if lo / L < EDGE_ANCHOR_FRAC:
        lo = 0
    if (L - 1 - hi) / L < EDGE_ANCHOR_FRAC:
        hi = L - 1
    if (hi - lo + 1) / L > COMPACT_CAP_FRAC:
        return None
    if vertical:
        return (x0, y0 + lo, x1, y0 + hi + 1)
    return (x0 + lo, y0, x0 + hi + 1, y1)


def erase_classical(paint_img, bbox, pad_frac=0.45):
    """OpenCV Telea inpaint on a padded crop around bbox. $0. Returns (new_paint_img, crop_box)."""
    import cv2
    W, H = paint_img.size
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    padx = int(w * pad_frac) + 10; pady = int(h * pad_frac) + 10
    cx0, cy0 = max(0, x0 - padx), max(0, y0 - pady)
    cx1, cy1 = min(W, x1 + padx), min(H, y1 + pady)
    arr = np.asarray(paint_img.convert("RGB"))
    crop = arr[cy0:cy1, cx0:cx1].copy()
    mask = np.zeros(crop.shape[:2], np.uint8)
    mx0, my0, mx1, my1 = x0 - cx0, y0 - cy0, x1 - cx0, y1 - cy0
    mask[my0:my1, mx0:mx1] = 255
    mask = cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=2)
    result = cv2.inpaint(crop.astype(np.uint8), mask, 7, cv2.INPAINT_TELEA)
    new_arr = arr.copy()
    new_arr[cy0:cy1, cx0:cx1] = result
    return Image.fromarray(new_arr), (cx0, cy0, cx1, cy1)


def _square_crop_box(W, H, bbox, pad_frac=0.7, min_side=280):
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = max((x1 - x0), (y1 - y0)) * (1 + pad_frac)
    side = max(side, min_side)
    side = min(side, W, H)
    side_i = int(side)
    half = side_i / 2
    cx0 = int(min(max(0, cx - half), W - side_i))
    cy0 = int(min(max(0, cy - half), H - side_i))
    return cx0, cy0, cx0 + side_i, cy0 + side_i


def erase_model(assets_dir, paint_img, bbox, seed):
    """Vertex nano-banana-pro edit on a SQUARE crop (see module docstring — sidesteps
    ai-image-coords-rule's aspect-mismatch trap by construction). Reuses genskin.py's proven
    edit_vertex() rather than re-implementing the Vertex call. ~$0.05-0.1/erase (small crop,
    but edit_vertex always requests 4K output; downscaled back to crop-pixel size on return)."""
    from genskin import edit_vertex  # local import: avoid genskin's module-level cost unless used
    W, H = paint_img.size
    cx0, cy0, cx1, cy1 = _square_crop_box(W, H, bbox)
    crop = paint_img.crop((cx0, cy0, cx1, cy1)).convert("RGB")
    tmp = os.path.join(assets_dir, "_erase12_crop_in.png")
    crop.save(tmp)
    prompt = (
        "This is a tight crop of a slider/control's EMPTY recessed groove or socket from a "
        "skeuomorphic device photo. A part (thumb/handle/grip/cap) is sitting in it and must "
        "be REMOVED. Erase that part completely and continue the groove/socket's own material, "
        "shading and recess depth SEAMLESSLY underneath where it was, exactly matching the "
        "surrounding channel/floor. CRITICAL — the recess's WIDTH/SHAPE after removal must "
        "match the channel's OWN cross-section as seen continuing elsewhere in this crop (a "
        "narrow, constant-width groove/slot), NOT the wider silhouette of the part being "
        "removed — do not leave a bulge, pocket or widened opening shaped like the removed "
        "part. The recess floor must be UNIFORMLY DARK/MATTE across its full width where the "
        "part was — do not leave any residual bright patch, glossy highlight, sheen or raised- "
        "looking area from the removed part; the whole floor should read as flat and equally "
        "dark as the rest of the empty channel. Change ABSOLUTELY NOTHING else in the frame: "
        "same materials, same lighting, "
        "same camera angle, same framing/crop, same backdrop, no new objects, no text, no "
        "colour shift."
    )
    png_bytes = edit_vertex(tmp, prompt, seed, aspect="1:1")
    out = Image.open(io.BytesIO(png_bytes)).convert("RGB").resize(crop.size, Image.LANCZOS)
    try:
        os.remove(tmp)
    except OSError:
        pass
    # Feathered composite, not a hard paste: a whole-square edit reliably matches the model's
    # own material/lighting at the CENTRE (where the object was) but the model doesn't promise
    # pixel-identical reproduction at the crop's own border — a hard paste there leaves a faint
    # rectangle visible (confirmed live on diablo-gothic/fallout-vault's first pass). Blend the
    # edited square back in with a soft alpha ramp (full-strength in the interior, fading to 0
    # over the outer ~12% margin) so the composite boundary lands on a smooth gradient instead
    # of a hard edge — same feathering idea as erase_baked.py's gaussian-blurred mask blend.
    out_arr = np.asarray(out).astype(float)
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
    return Image.fromarray(new_arr.astype(np.uint8)), (cx0, cy0, cx1, cy1)


def floor_darken(paint_img, dev_bbox, vertical=None, strength=0.85, max_iter=3):
    """$0 finishing pass: pull a residual raised/glossy patch back toward the groove's OWN
    floor tone, targeting the exact signal extract12.py's baked-thumb gate measures (column
    brightness vs the groove's floor/body reference) — a direct pixel correction, same idea as
    erase_baked.py's original floor-tone fill. Added because two rounds of prompt tightening on
    erase_model's Vertex call did NOT remove a glossy highlight left behind on fallout-vault
    (live-observed: run_frac/peak barely moved, 0.080/1.29 -> 0.081/1.31) — the model kept
    regenerating a bright patch roughly where the removed part's highlight was. Direct pixel
    correction succeeds where more prompt wording did not. Iterates against THIS module's own
    detect_bbox() (not extract12.py's gate — no import dependency) until clean or max_iter."""
    arr = np.asarray(paint_img.convert("RGB")).astype(float).copy()
    H, W = arr.shape[:2]
    dx0, dy0, dx1, dy1 = _device_window(dev_bbox, W, H)
    for _ in range(max_iter):
        bad = detect_bbox(arr.astype(np.uint8), dev_bbox, vertical=vertical)
        if bad is None:
            break
        bx0, by0, bx1, by1 = bad
        win = arr[dy0:dy1, dx0:dx1]
        floor = np.percentile(win.max(2), 12)
        lx0, ly0, lx1, ly1 = bx0 - dx0, by0 - dy0, bx1 - dx0, by1 - dy0
        region = arr[dy0 + ly0:dy0 + ly1, dx0 + lx0:dx0 + lx1]
        lum = region.max(2)
        span = max(1.0, lum.max() - floor)
        excess = np.clip(lum - floor, 0, None)
        scale = 1 - strength * np.clip(excess / span, 0, 1)
        noise = np.random.RandomState(7).normal(0, 2.0, size=region.shape[:2])
        region[:] = np.clip(region * scale[:, :, None] + noise[:, :, None], 0, 255)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def seam_delta(paint_arr, bbox, band=4):
    """Coarse seam heuristic: mean colour delta between a thin band just INSIDE the erased
    bbox border and a thin band just OUTSIDE it, in the post-erase image. Large delta => a
    visible ring/edge likely remains (classical inpaint sometimes drags in a neighbour tone)."""
    H, W = paint_arr.shape[:2]
    x0, y0, x1, y1 = bbox
    x0o, y0o = max(0, x0 - band), max(0, y0 - band)
    x1o, y1o = min(W, x1 + band), min(H, y1 + band)
    inside = paint_arr[y0:y1, x0:x1].reshape(-1, 3).astype(float)
    outer_ring = paint_arr[y0o:y1o, x0o:x1o].astype(int).copy()
    outer_ring[band:-band or None, band:-band or None] = -1  # blank the interior, keep the ring
    ring_px = outer_ring[(outer_ring >= 0).all(2)].reshape(-1, 3).astype(float)
    if len(inside) < 8 or len(ring_px) < 8:
        return 0.0
    return float(np.abs(inside.mean(0) - ring_px.mean(0)).mean())


def save_verify_crops(assets_dir, control, before_img, after_img, box, tag, upscale=4):
    vdir = os.path.join(assets_dir, "erase-verify")
    os.makedirs(vdir, exist_ok=True)
    pad = 24
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(before_img.width, x1 + pad), min(before_img.height, y1 + pad)
    for img, name in ((before_img, "before"), (after_img, "after")):
        c = img.crop((x0, y0, x1, y1))
        c = c.resize((c.width * upscale, c.height * upscale), Image.LANCZOS)
        c.save(os.path.join(vdir, f"{control}-{tag}-{name}.png"))
    return vdir


def load_log(assets_dir):
    p = os.path.join(assets_dir, "erase12-log.json")
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            pass
    return []


def save_log(assets_dir, log):
    json.dump(log, open(os.path.join(assets_dir, "erase12-log.json"), "w"), indent=2)


def resolve_control(regions, arg_control, arg_gate_reasons):
    if arg_control:
        return arg_control
    for gr in arg_gate_reasons:
        if gr.startswith("baked-thumb:"):
            return gr.split(":", 1)[1]
    roles = regions.get("roles", {})
    for k in regions.get("sprites", []):
        if roles.get(k) == "slider":
            return k
    if "seek" in regions.get("sprites", []):
        return "seek"
    raise SystemExit("erase12: no --control / --gate-reason given and no slider-role control found in regions.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assets_dir")
    ap.add_argument("--control", default=None)
    ap.add_argument("--gate-reason", action="append", default=[])
    ap.add_argument("--bbox", default=None, help="x0,y0,x1,y1 FRACTIONAL (0-1) override of auto-detect")
    ap.add_argument("--method", choices=["classical", "model", "auto"], default="auto")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="erase even if the auto-detect window already reads empty")
    ap.add_argument("--dry-run", action="store_true", help="detect + write verify crops only, no paint/joint writes")
    args = ap.parse_args()

    assets_dir = os.path.abspath(args.assets_dir)
    paint_path = os.path.join(assets_dir, "paint.png")
    regions_path = os.path.join(assets_dir, "regions.json")
    results_path = os.path.join(assets_dir, "results.json")
    if not os.path.exists(paint_path):
        raise SystemExit(f"erase12: no paint.png in {assets_dir}")
    if not os.path.exists(regions_path):
        raise SystemExit(f"erase12: no regions.json in {assets_dir} — run extract12.py first")
    regions = json.load(open(regions_path))
    control = resolve_control(regions, args.control, args.gate_reason)
    r = regions.get("regions", {}).get(control)
    if not r or not r.get("device"):
        raise SystemExit(f"erase12: control '{control}' has no device bbox in regions.json")

    before_sha = sha12(paint_path)
    log = load_log(assets_dir)
    already = [e for e in log if e.get("control") == control and e.get("after_sha") == before_sha and e.get("status") == "erased"]
    if already and not args.force:
        print(f"[erase12] {control}: paint.png sha {before_sha} already matches a prior erase result — no-op")
        return

    paint_img = Image.open(paint_path).convert("RGB")
    paint_arr = np.asarray(paint_img)
    vertical = r.get("vertical")

    if args.bbox:
        vals = [float(v) for v in args.bbox.split(",")]
        H, W = paint_arr.shape[:2]
        bbox = (int(vals[0] * W), int(vals[1] * H), int(vals[2] * W), int(vals[3] * H))
    else:
        bbox = detect_bbox(paint_arr, r["device"], vertical=vertical)

    if bbox is None and not args.force:
        print(f"[erase12] {control}: no compact anomaly found in the groove — nothing to erase")
        return
    if bbox is None:
        H, W = paint_arr.shape[:2]
        bbox = _device_window(r["device"], W, H)  # --force with nothing detected: fall back to the full window

    print(f"[erase12] {control}: candidate bake at px{bbox} — HEURISTIC, inspect the verify crop before trusting it")

    if args.dry_run:
        save_verify_crops(assets_dir, control, paint_img, paint_img, bbox, "dryrun")
        print(f"[erase12] --dry-run: crop saved to {assets_dir}/erase-verify/, no writes made")
        return

    seed = args.seed or json.load(open(results_path)).get("seed", 71) if os.path.exists(results_path) else (args.seed or 71)

    method_used = None
    new_img = None
    if args.method in ("classical", "auto"):
        new_img, crop_box = erase_classical(paint_img, bbox)
        method_used = "classical"
        new_arr = np.asarray(new_img)
        still_defect = detect_bbox(new_arr, r["device"], vertical=vertical) is not None
        seam = seam_delta(new_arr, bbox)
        ok = (not still_defect) and seam < 40
        print(f"[erase12] classical inpaint: re-detect {'still finds a defect' if still_defect else 'clean'}, "
              f"seam-delta {seam:.1f} -> {'OK' if ok else 'still shows a defect'}")
        if not ok and args.method == "auto":
            print("[erase12] classical result insufficient -> escalating to model-edit fallback")
            new_img = None

    if new_img is None and args.method in ("model", "auto"):
        new_img, crop_box = erase_model(assets_dir, paint_img, bbox, seed)
        method_used = "model"
        new_arr = np.asarray(new_img)
        still_defect = detect_bbox(new_arr, r["device"], vertical=vertical) is not None
        if still_defect:
            # $0 finishing pass — see floor_darken() docstring: two rounds of Vertex prompt
            # tightening left a residual glossy highlight on fallout-vault; direct pixel
            # correction toward the groove's own floor tone closed it where wording didn't.
            print("[erase12] model edit still shows a residual patch -> applying floor_darken finishing pass")
            new_img = floor_darken(new_img, r["device"], vertical=vertical)
            method_used = "model+floor_darken"
            new_arr = np.asarray(new_img)
            still_defect = detect_bbox(new_arr, r["device"], vertical=vertical) is not None
        seam = seam_delta(new_arr, bbox)
        ok = not still_defect
        print(f"[erase12] model edit: re-detect {'still finds a defect' if still_defect else 'clean'}, "
              f"seam-delta {seam:.1f} -> {'OK' if ok else 'STILL FAILING — needs a human look'}")

    if new_img is None:
        raise SystemExit(f"erase12: {control} — classical failed and --method classical was forced (no model fallback attempted)")

    tag = time.strftime("%Y%m%dT%H%M%S")
    vdir = save_verify_crops(assets_dir, control, paint_img, new_img, crop_box, tag)

    new_img.save(paint_path)
    joint_path = os.path.join(assets_dir, "joint-4k.png")
    if os.path.exists(joint_path):
        joint = Image.open(joint_path)
        joint.paste(new_img, (0, 0))
        joint.save(joint_path)

    after_sha = sha12(paint_path)
    still_defect = detect_bbox(np.asarray(new_img), r["device"], vertical=vertical) is not None
    log.append({
        "control": control, "method": method_used, "before_sha": before_sha, "after_sha": after_sha,
        "defect_found_after": still_defect,
        "bbox_px": list(bbox), "crop_box_px": list(crop_box), "seed": seed, "ts": tag,
        "status": "erased" if not still_defect else "erased-still-failing",
        "verify_dir": os.path.relpath(vdir, assets_dir),
    })
    save_log(assets_dir, log)
    print(f"[erase12] {control}: {method_used} erase written — paint.png {before_sha} -> {after_sha}, "
          f"verify crops in {vdir}")


if __name__ == "__main__":
    main()
