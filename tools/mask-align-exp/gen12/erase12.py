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
  2. MODEL EDIT on a SQUARE crop — fallback when the classical result still reads bright
     (>0.10 interior) or leaves a visible seam. As of 2026-07-12, ERASE_MODEL_CHAIN (below)
     replaces the old single Vertex gemini-3-pro-image-preview default with a two-model chain
     chosen live off inpaintbake/arm5's bake-off: gemini-2.5-flash PRIMARY (Vertex-direct,
     $0.039/erase, 4/4 clean incl. rune-glow preservation with no glow clause) -> gpt-image-2
     FALLBACK (fal, different model family, $0.0548/erase, 3/4 clean + 1 soft) —
     erase_model_gemini25()/erase_model_gpt_image2()/run_model_chain(). The OLD default
     (gemini-3-pro-image-preview, ~$0.134-0.241/erase) stays selectable as a deep fallback via
     erase_model_vertex_pro() / --method model-pro.
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

# GROOVE_ASPECT_MIN / MIN_BLOB_FRAC: fix for the confirmed steam-porthole targeting bug (TODO.md
# "detect_bbox() targeting bug" entry). Root cause, reproduced live against the real function on
# the git-recovered pre-erase paint.png (sha 163f3beb1247): the ORIGINAL detect_bbox() always
# collapsed the device window to a 1-D profile along a single "long axis" and then blindly
# EXTENDED the result to the window's FULL cross-axis (by design — a real groove thumb usually
# does fill the groove's own width, and a softened rim edge needs the extension). That's correct
# for a genuinely elongated slider groove (this roster's real "seek" windows are all aspect >=
# 3.87 — see the audit in the commit that added this comment) but WRONG for a compact, near-
# square control like a knob's device rect (this roster's "vol" windows are all aspect 1.61):
# collapsing a round knob's 2-D wrong-icon defect (a duplicated play/pause pictogram baked into
# steam-porthole's vol socket, see inpaintbake/arm5/build_arm5_crops.py) to a 1-D profile and then
# force-extending it to the FULL window height produced a 21x313px SLIVER
# ((1136,2042,1157,2355) — confirmed by re-running detect_bbox() on the real recovered paint,
# vs. the true ~311x313px defect) instead of the object's real 2-D extent. Both erase models then
# "failed" on that garbage crop regardless of model quality (gemini regenerated the icon in
# place; gpt-image-2 returned a solid black square over the sliver). GROOVE_ASPECT_MIN gates which
# path runs: elongated windows (a real groove) keep the original validated 1-D long-axis path
# unchanged; compact/near-square windows (a knob, or any control whose device rect isn't
# elongated) now run `_compact_blob_bbox()` — a real 2-D connected-component search that reports
# the anomalous blob's OWN measured bounding box on both axes, never force-extending either one.
GROOVE_ASPECT_MIN = 2.0   # long/short device-window ratio required to trust the groove path.
                          # Comfortably separates this roster's two shapes (slider windows 3.87-
                          # 24.0, knob windows all 1.61) with margin on both sides.
MIN_BLOB_FRAC = 0.15      # a compact-path blob whose extent on EITHER axis is under this fraction
                          # of the window's own extent on that axis is too thin to be a real baked
                          # part (rim seam / texture noise) — rejected, not auto-erased.

# ERASE_MODEL_CHAIN: default two-model fallback chain for the model-edit escalation step,
# REPLACING the old single Vertex gemini-3-pro-image-preview default (2026-07-12, user-chosen
# per docs/experiments/2026-07-12-inpaint-bakeoff.md's arm5 — 5 genuine slider-groove skins,
# SAME plain erase prompt below, no glow/rune/inlay clause):
#   1. gemini-2.5-flash — Vertex-direct (generation-spend-rule SS3: Google models go direct,
#      not fal-wrapped), $0.039/call at the 2K tier. 4/4 CLEAN in arm5, including the ornate
#      rune-glow diablo-gothic case — the plain prompt preserves the glow naturally with no
#      glow clause needed (a PRESERVE-GLOW variant was tried and discarded: it over-constrained
#      the model into INVENTING new glow ornamentation, see inpaintbake/arm5/discarded-
#      glowclause/). ~6x cheaper than the old gemini-3-pro default (was silently billed at the
#      4K tier, $0.241/call — see the TODO.md entry directly above this session's).
#   2. gpt-image-2 — fal (OpenAI-hosted only via fal, no direct API key held here — a legitimate
#      fal-hosted exception per generation-spend-rule SS3), quality=medium, $0.0548/call
#      (confirmed live, inpaintbake/arm5/cost_log.json; "high" measured ~$0.22/call, 4x, rejected).
#      3/4 + 1 SOFT (diablo-gothic: clean erase but the rune-glow partially lost mid-groove) in
#      arm5. Different model family from Gemini — the point of a fallback.
# Both models HARD-failed steam-porthole in arm5 (gemini regenerated the play/pause button in
# place; gpt-image-2 returned a solid black square) — NOT a model-quality gap, a DETECTION bug:
# detect_bbox() anchored the mask on an ambiguous play/pause button, not the slider thumb. See
# the TODO.md entry filed alongside this change. A bad crop dooms any model.
# gemini-3-pro-image-preview (the OLD default) stays fully intact and selectable as a deep
# fallback via erase_model_vertex_pro() / --method model-pro — not deleted, just no longer the
# default chain a bare `--method model`/`auto` run tries first.
ERASE_MODEL_CHAIN = ["gemini-2.5-flash", "gpt-image-2"]
VERTEX_GEMINI25_MODEL = "gemini-2.5-flash-image"
GEMINI25_PRICE = 0.039       # Vertex 2K tier, confirmed inpaintbake/arm4 + arm5
GPT_IMAGE2_QUALITY = "medium"
GPT_IMAGE2_PRICE = 0.0548    # fal, quality=medium, confirmed inpaintbake/arm5/cost_log.json (5/5 calls)
# rough per-erase cost table for the final report line — base model name (floor_darken finishing
# passes are $0, so "<model>+floor_darken" reuses the base model's price)
COST_ESTIMATE = {
    "classical": 0.0,
    "gemini-2.5-flash": GEMINI25_PRICE,
    "gpt-image-2": GPT_IMAGE2_PRICE,
    "gemini-3-pro": 0.134,  # 2K tier (this roster's crops); 0.241 if a future crop exceeds 2048px
}

# EXACT plain erase prompt — no glow/rune/inlay clause (confirmed: arm5 used a stripped-down
# version of this same instruction and found no glow clause necessary; kept here as the fuller,
# already-hardened wording since erase12.py owns real production skins, not a bake-off crop).
# Shared by every model-edit path below (erase_model_gemini25/erase_model_gpt_image2/
# erase_model_vertex_pro) so all three send the IDENTICAL instruction — the seam contract
# parallel-by-default-rule asks for when comparing model outputs on the same input.
ERASE_PROMPT = (
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


def _compact_blob_bbox(win):
    """2-D connected-component anomaly locator for a NON-elongated (knob/round) control window —
    see the GROOVE_ASPECT_MIN comment for why this exists. Unlike the groove path below, this
    measures the anomalous blob's TRUE bounding box on both axes directly from its pixel
    footprint — no 1-D profile collapse, no forced full-cross-axis extension — so a compact 2-D
    defect (a wrong-icon glyph baked into a round socket) is bounded by where it actually is.
    Returns a (x0,y0,x1,y1) bbox LOCAL to `win`, or None if nothing compact/plausible was found."""
    lum = win.max(2).astype(float)
    h, w = lum.shape
    k = 9
    local_mean = ndimage.uniform_filter(lum, size=k)
    local_sqmean = ndimage.uniform_filter(lum * lum, size=k)
    local_std = np.sqrt(np.clip(local_sqmean - local_mean ** 2, 0, None))
    base_std = np.percentile(local_std, 30)
    base_med = np.percentile(lum, 30)
    anomaly = (local_std > base_std * 1.6 + 3) | (lum > base_med + 35)
    lbl, n = ndimage.label(anomaly)
    if n == 0:
        return None
    sizes = ndimage.sum(anomaly, lbl, range(1, n + 1))
    biggest = int(np.argmax(sizes)) + 1
    ys, xs = np.where(lbl == biggest)
    bx0, bx1 = int(xs.min()), int(xs.max()) + 1
    by0, by1 = int(ys.min()), int(ys.max()) + 1
    if (bx1 - bx0) / w < MIN_BLOB_FRAC or (by1 - by0) / h < MIN_BLOB_FRAC:
        return None  # too thin on one axis to be a real compact part — noise, not a bake
    return bx0, by0, bx1, by1


def detect_bbox(paint_arr, dev_bbox, vertical=None):
    """Groove-shaped baked-part locator — see module docstring for why this replaces a naive
    bright-pixel/shrink test. Returns (x0,y0,x1,y1) PIXEL bbox spanning the full cross-axis
    and the detected long-axis run, or None if nothing compact was found.

    Only runs the 1-D long-axis collapse on windows that are actually ELONGATED
    (GROOVE_ASPECT_MIN) — a genuine slider/seek groove. A compact/near-square window (a knob's
    device rect) routes to `_compact_blob_bbox()` instead, which never force-extends either axis.
    See the GROOVE_ASPECT_MIN module comment for the confirmed steam-porthole failure this fixes."""
    H, W = paint_arr.shape[:2]
    x0, y0, x1, y1 = _device_window(dev_bbox, W, H)
    win = paint_arr[y0:y1, x0:x1]
    if win.size == 0:
        return None
    w_span, h_span = x1 - x0, y1 - y0
    aspect = max(w_span, h_span) / max(1, min(w_span, h_span))
    if aspect < GROOVE_ASPECT_MIN:
        blob = _compact_blob_bbox(win)
        if blob is None:
            return None
        bx0, by0, bx1, by1 = blob
        return (x0 + bx0, y0 + by0, x0 + bx1, y0 + by1)
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


def _feathered_composite(paint_img, out_img, crop_box):
    """Blend a model-edited SQUARE crop back into paint_img with a soft alpha ramp over the
    outer ~12% margin (full-strength in the interior), not a hard paste. A whole-square edit
    reliably matches the model's own material/lighting at the CENTRE (where the object was) but
    the model doesn't promise pixel-identical reproduction at the crop's own border — a hard
    paste there leaves a faint rectangle visible (confirmed live on diablo-gothic/fallout-vault's
    first pass). Same feathering idea as erase_baked.py's gaussian-blurred mask blend. Shared by
    EVERY model-edit path (erase_model_gemini25/erase_model_gpt_image2/erase_model_vertex_pro)
    so the seam behaviour is identical regardless of which model produced the crop."""
    cx0, cy0, cx1, cy1 = crop_box
    crop_size = (cx1 - cx0, cy1 - cy0)
    if out_img.size != crop_size:
        out_img = out_img.resize(crop_size, Image.LANCZOS)
    out_arr = np.asarray(out_img).astype(float)
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


def erase_model_gemini25(assets_dir, paint_img, bbox, seed):
    """PRIMARY of ERASE_MODEL_CHAIN. Same square-crop + Vertex plumbing as
    erase_model_vertex_pro() (sidesteps ai-image-coords-rule's aspect-mismatch trap by
    construction — no separate aspect-matching logic needed) but targets gemini-2.5-flash-image
    via genskin.py:edit_vertex()'s model= param instead of the default gemini-3-pro-image-preview
    — $0.039/call vs gemini-3-pro's $0.134-0.241/call, and 4/4 clean on the real inpaintbake/arm5
    bake-off including the rune-glow diablo-gothic case on this SAME plain ERASE_PROMPT (no glow
    clause needed — see ERASE_MODEL_CHAIN's comment)."""
    from genskin import edit_vertex  # local import: avoid genskin's module-level cost unless used
    W, H = paint_img.size
    cx0, cy0, cx1, cy1 = _square_crop_box(W, H, bbox)
    crop_side = cx1 - cx0
    vertex_tier = "2K" if crop_side <= 2048 else "4K"
    crop = paint_img.crop((cx0, cy0, cx1, cy1)).convert("RGB")
    tmp = os.path.join(assets_dir, "_erase12_crop_in.png")
    crop.save(tmp)
    try:
        png_bytes = edit_vertex(tmp, ERASE_PROMPT, seed, aspect="1:1", image_size=vertex_tier,
                                 model=VERTEX_GEMINI25_MODEL)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    out = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return _feathered_composite(paint_img, out, (cx0, cy0, cx1, cy1)), (cx0, cy0, cx1, cy1)


def _square_crop_and_mask(paint_img, bbox, dilate_px=7, dilate_iter=2):
    """Same SQUARE crop erase_model_gemini25 uses (identical seam contract, so both models in
    the chain see the identical input) PLUS a white-in-black-out erase mask for GPT Image 2's
    MASKED edit (unlike Gemini's whole-crop free edit, GPT edits only the masked pixels). Mask =
    the detect_bbox() defect bbox, dilated a few px past its own silhouette — same dilation idea
    erase_classical()'s inpaint mask already uses."""
    import cv2
    W, H = paint_img.size
    cx0, cy0, cx1, cy1 = _square_crop_box(W, H, bbox)
    crop = paint_img.crop((cx0, cy0, cx1, cy1)).convert("RGB")
    x0, y0, x1, y1 = bbox
    mx0, my0 = max(0, x0 - cx0), max(0, y0 - cy0)
    mx1, my1 = min(cx1 - cx0, x1 - cx0), min(cy1 - cy0, y1 - cy0)
    mask = np.zeros((cy1 - cy0, cx1 - cx0), np.uint8)
    mask[my0:my1, mx0:mx1] = 255
    mask = cv2.dilate(mask, np.ones((dilate_px, dilate_px), np.uint8), iterations=dilate_iter)
    return crop, Image.fromarray(mask), (cx0, cy0, cx1, cy1)


def erase_model_gpt_image2(assets_dir, paint_img, bbox):
    """FALLBACK of ERASE_MODEL_CHAIN — a different model FAMILY from Gemini (OpenAI GPT Image 2,
    fal-hosted). 3/4 clean + 1 soft (partial glow loss) on inpaintbake/arm5's real bake-off, on
    the SAME plain ERASE_PROMPT. Reuses genskin.py's edit_fal_gpt_image2().

    OBSERVED LIVE FAILURE MODE (this task's own verification, 2026-07-12, fallout-pipboy's
    'seek' groove — a NARROW double-rail slot cross-section, not the flat single-channel
    grooves arm5's 5 test skins used): GPT Image 2 filled the whole masked region with a flat
    undifferentiated dark rectangle, losing the narrow-slot/rail geometry entirely — exactly the
    'widened opening' shape-mismatch failure ERASE_PROMPT explicitly warns against. Gemini 2.5
    Flash, run alone on the SAME input/bbox, preserved the narrow-rail cross-section correctly
    (near pixel-identical to the old gemini-3-pro production result). This is WHY
    run_model_chain()'s failure-rescue prefers the FIRST (primary/gemini) attempt, not the last
    — see that function's docstring."""
    from genskin import edit_fal_gpt_image2  # local import, same pattern as edit_vertex above
    crop, mask, crop_box = _square_crop_and_mask(paint_img, bbox)
    cx0, cy0, cx1, cy1 = crop_box
    tmp_img = os.path.join(assets_dir, "_erase12_gpt_in.png")
    tmp_mask = os.path.join(assets_dir, "_erase12_gpt_mask.png")
    crop.save(tmp_img)
    mask.save(tmp_mask)
    try:
        png_bytes, cost = edit_fal_gpt_image2(tmp_img, tmp_mask, ERASE_PROMPT,
                                               quality=GPT_IMAGE2_QUALITY)
    finally:
        for p in (tmp_img, tmp_mask):
            try:
                os.remove(p)
            except OSError:
                pass
    out = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return _feathered_composite(paint_img, out, crop_box), crop_box


def erase_model_vertex_pro(assets_dir, paint_img, bbox, seed):
    """DEEP FALLBACK — the OLD default (Vertex gemini-3-pro-image-preview), kept fully intact
    and selectable via --method model-pro. Not in ERASE_MODEL_CHAIN by default: ~3.4-6x the cost
    of the primary (gemini-2.5-flash) for no measured quality edge on this task (arm5 bake-off).
    Requests the CHEAPEST Vertex tier that still covers the crop's own resolution — see the
    2026-07-12 pricing-tier fix this function's docstring used to carry (now on edit_vertex()'s
    image_size param docs in genskin.py)."""
    from genskin import edit_vertex
    W, H = paint_img.size
    cx0, cy0, cx1, cy1 = _square_crop_box(W, H, bbox)
    crop_side = cx1 - cx0
    vertex_tier = "2K" if crop_side <= 2048 else "4K"
    crop = paint_img.crop((cx0, cy0, cx1, cy1)).convert("RGB")
    tmp = os.path.join(assets_dir, "_erase12_crop_in.png")
    crop.save(tmp)
    try:
        png_bytes = edit_vertex(tmp, ERASE_PROMPT, seed, aspect="1:1", image_size=vertex_tier)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    out = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return _feathered_composite(paint_img, out, (cx0, cy0, cx1, cy1)), (cx0, cy0, cx1, cy1)


MODEL_FNS = {
    "gemini-2.5-flash": lambda assets_dir, paint_img, bbox, seed: erase_model_gemini25(assets_dir, paint_img, bbox, seed),
    "gpt-image-2": lambda assets_dir, paint_img, bbox, seed: erase_model_gpt_image2(assets_dir, paint_img, bbox),
}


def run_model_chain(assets_dir, paint_img, bbox, seed, r, vertical, chain=None):
    """Try each model in ERASE_MODEL_CHAIN (default) in order, re-detecting after each; stop and
    return the first result that reads clean. Returns (new_img, crop_box, winner, tried) where
    `winner` is the succeeding model's name (or None if every model in the chain still shows a
    defect — callers must NOT silently ship that as a pass, per verify-outputs-rule and the
    task's own 'if both fail, surface it').

    On FULL failure (nothing in the chain reads clean), new_img/crop_box hold the FIRST
    (primary/cheapest) attempt, NOT the last. This was verified live (fallout-pipboy's 'seek'
    groove, a narrow double-rail slot): gemini-2.5-flash's own result was visually correct
    (matched the old gemini-3-pro production result almost exactly) but tripped a marginal/
    borderline re-detect flag, so the chain escalated to gpt-image-2 — which produced a
    genuinely WORSE result (collapsed the narrow-rail cross-section into a flat block, see
    erase_model_gpt_image2()'s docstring). seam_delta can't discriminate this case (gpt's flat
    fill actually reads a LOWER/smoother seam-delta than gemini's correct-but-marginally-flagged
    result — the metric measures border colour continuity, not internal shape). Absent a
    reliable $0 shape signal, prefer the PRIMARY model's attempt on full failure: arm5's real
    bake-off found gemini-2.5-flash >= gpt-image-2 in every one of 5 skins tested (never worse),
    so 'first attempt' is the best available fallback ordering, not an arbitrary tiebreak."""
    chain = chain or ERASE_MODEL_CHAIN
    tried = []
    first_img, first_crop_box = None, None
    last_img, last_crop_box = None, None
    for name in chain:
        new_img, crop_box = MODEL_FNS[name](assets_dir, paint_img, bbox, seed)
        if first_img is None:
            first_img, first_crop_box = new_img, crop_box
        last_img, last_crop_box = new_img, crop_box
        new_arr = np.asarray(new_img)
        still_defect = detect_bbox(new_arr, r["device"], vertical=vertical) is not None
        seam = seam_delta(new_arr, bbox)
        print(f"[erase12] {name}: re-detect {'still finds a defect' if still_defect else 'clean'}, "
              f"seam-delta {seam:.1f} (~${COST_ESTIMATE.get(name, 0):.4f})")
        tried.append((name, still_defect))
        if not still_defect:
            return new_img, crop_box, name, tried
    return first_img, first_crop_box, None, tried


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
    ap.add_argument("--method", choices=["classical", "model", "auto", "model-pro"], default="auto",
                     help="model = ERASE_MODEL_CHAIN (gemini-2.5-flash -> gpt-image-2 fallback, "
                          "the 2026-07-12 default); model-pro = force the deep-fallback Vertex "
                          "gemini-3-pro-image-preview path directly, skipping the chain")
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

    if new_img is None and args.method == "model-pro":
        # explicit deep-fallback request — skip the chain, go straight to the old default
        new_img, crop_box = erase_model_vertex_pro(assets_dir, paint_img, bbox, seed)
        method_used = "gemini-3-pro"
        new_arr = np.asarray(new_img)
        still_defect = detect_bbox(new_arr, r["device"], vertical=vertical) is not None
        if still_defect:
            print("[erase12] gemini-3-pro edit still shows a residual patch -> applying floor_darken finishing pass")
            new_img = floor_darken(new_img, r["device"], vertical=vertical)
            method_used = "gemini-3-pro+floor_darken"
            new_arr = np.asarray(new_img)
            still_defect = detect_bbox(new_arr, r["device"], vertical=vertical) is not None
        seam = seam_delta(new_arr, bbox)
        print(f"[erase12] gemini-3-pro edit: re-detect {'still finds a defect' if still_defect else 'clean'}, "
              f"seam-delta {seam:.1f}")

    if new_img is None and args.method in ("model", "auto"):
        # ERASE_MODEL_CHAIN: gemini-2.5-flash primary -> gpt-image-2 fallback (see the module-
        # level ERASE_MODEL_CHAIN comment for why). run_model_chain() re-detects after each
        # model and stops at the first clean result.
        new_img, crop_box, winner, tried = run_model_chain(assets_dir, paint_img, bbox, seed, r, vertical)
        if winner:
            method_used = winner
        else:
            # every model in the chain still shows the defect — $0 finishing pass on the FIRST
            # (primary) attempt before surfacing failure, NOT the last (see run_model_chain()'s
            # docstring for why: the primary's own result is the empirically best available one
            # even when flagged, and the finishing pass never touches shape, only brightness —
            # same rescue the old single-model path applied; see floor_darken() docstring — two
            # rounds of prompt tightening alone didn't clear a residual glossy highlight, direct
            # pixel correction did).
            first_name = tried[0][0] if tried else "unknown"
            print(f"[erase12] model chain exhausted ({', '.join(n for n, _ in tried)}) -> "
                  f"applying floor_darken finishing pass on the primary attempt ({first_name})")
            new_img = floor_darken(new_img, r["device"], vertical=vertical)
            method_used = f"{first_name}+floor_darken"
        new_arr = np.asarray(new_img)
        still_defect = detect_bbox(new_arr, r["device"], vertical=vertical) is not None
        seam = seam_delta(new_arr, bbox)
        print(f"[erase12] model chain result ({method_used}): re-detect "
              f"{'still finds a defect' if still_defect else 'clean'}, seam-delta {seam:.1f} -> "
              f"{'OK' if not still_defect else 'STILL FAILING — needs a human look'} "
              f"(~${COST_ESTIMATE.get(method_used.split('+')[0], 0):.4f})")

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
