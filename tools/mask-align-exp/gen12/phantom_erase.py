#!/usr/bin/env python3
"""phantom_erase.py — erase a PHANTOM/duplicate control or baked text at a MANUAL pixel bbox.

erase12.py's detect_bbox() is purpose-built for a groove/socket's OWN device window (a baked
slider thumb, a wrong icon inside a knob's socket) — it locates the defect BY SEARCHING that
control's own device bbox. It cannot locate a defect that is NOT inside any named control's
device window at all: an extra unclaimed 7th button the paint model drew, a duplicate icon
glyph baked onto a real button's face, or decorative rune/word text baked into a frame/gauge.
Those are exactly this round's targets (Round-4 gate's `phantom-control:<loc>` reason, plus
two ungated "wordless-device" violations spotted by eye: myst-arcanum's "EMPTY" arc text and
wc-goldshield's runic frame text).

Rather than reinventing the model-edit plumbing, this reuses erase12.py's own building blocks
(fix-generalizable-rule / discover-before-building-rule — don't rewrite what already works):
  - genskin.edit_vertex() — the same Vertex gemini-2.5-flash-image call, same 2K/4K tier logic
  - erase12._square_crop_box() / erase12._feathered_composite() — identical seam contract
  - erase12._square_crop_and_mask() / genskin.edit_fal_gpt_image2() — the SAME fallback model
  - erase12.save_verify_crops() — same 4x-upscaled before/after crop convention
  - erase12.sha12() / erase12-log.json — same provenance log, so this tool's erasures show up
    in the SAME audit trail as groove/socket erasures (control label prefixed "phantom:"/"text:"
    to distinguish from a real named control)

Only the DEFECT LOCATOR differs: no detect_bbox() search — the caller supplies an explicit
pixel bbox (from the gate's own `phantom-control:px(...)` reason, or from direct visual
inspection for an ungated defect) and an explicit prompt tailored to what's actually being
removed (a whole extra button vs. just an icon glyph on a real button's face vs. baked text).

No automatic re-detect / auto-escalation loop (detect_bbox() doesn't generalize to an arbitrary
phantom shape) — verification here is a human/SOTA-eye look at the saved verify crop, per
verify-outputs-rule + sota-eye-review-rule. Use --escalate to explicitly force the gpt-image-2
fallback on a call you've already judged failed.

Usage:
  python3 phantom_erase.py assets-fa-pod --label phantom-shuffle \
      --bbox 1219,1959,1540,2280 --prompt "..." --seed 71
  python3 phantom_erase.py assets-fa-pod --label phantom-shuffle --bbox ... --prompt ... --dry-run
  python3 phantom_erase.py assets-fa-pod --label phantom-shuffle --bbox ... --prompt ... --escalate
"""
import argparse, io, json, os, sys, time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import erase12 as E  # reuse crop/composite/verify/log plumbing — see module docstring


def erase_gemini25(assets_dir, paint_img, bbox, prompt, seed):
    """Same crop/edit/composite as erase12.erase_model_gemini25(), but with an EXPLICIT prompt
    instead of erase12's own groove-specific ERASE_PROMPT constant."""
    from genskin import edit_vertex
    W, H = paint_img.size
    cx0, cy0, cx1, cy1 = E._square_crop_box(W, H, bbox)
    crop_side = cx1 - cx0
    vertex_tier = "2K" if crop_side <= 2048 else "4K"
    crop = paint_img.crop((cx0, cy0, cx1, cy1)).convert("RGB")
    tmp = os.path.join(assets_dir, "_phantom_erase_crop_in.png")
    crop.save(tmp)
    try:
        png_bytes = edit_vertex(tmp, prompt, seed, aspect="1:1", image_size=vertex_tier,
                                 model=E.VERTEX_GEMINI25_MODEL)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    out = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return E._feathered_composite(paint_img, out, (cx0, cy0, cx1, cy1)), (cx0, cy0, cx1, cy1)


def erase_gpt_image2(assets_dir, paint_img, bbox, prompt):
    """Same crop+mask/edit/composite as erase12.erase_model_gpt_image2(), explicit prompt."""
    from genskin import edit_fal_gpt_image2
    crop, mask, crop_box = E._square_crop_and_mask(paint_img, bbox)
    cx0, cy0, cx1, cy1 = crop_box
    tmp_img = os.path.join(assets_dir, "_phantom_erase_gpt_in.png")
    tmp_mask = os.path.join(assets_dir, "_phantom_erase_gpt_mask.png")
    crop.save(tmp_img)
    mask.save(tmp_mask)
    try:
        png_bytes, cost = edit_fal_gpt_image2(tmp_img, tmp_mask, prompt, quality=E.GPT_IMAGE2_QUALITY)
    finally:
        for p in (tmp_img, tmp_mask):
            try:
                os.remove(p)
            except OSError:
                pass
    out = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return E._feathered_composite(paint_img, out, crop_box), crop_box


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assets_dir")
    ap.add_argument("--label", required=True, help="log/verify-crop name, e.g. phantom-shuffle, text-frame")
    ap.add_argument("--bbox", required=True, help="x0,y0,x1,y1 PIXEL bbox of the defect")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seed", type=int, default=71)
    ap.add_argument("--escalate", action="store_true", help="use gpt-image-2 fallback instead of gemini-2.5-flash")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    assets_dir = os.path.abspath(args.assets_dir)
    paint_path = os.path.join(assets_dir, "paint.png")
    bbox = tuple(int(v) for v in args.bbox.split(","))
    paint_img = Image.open(paint_path).convert("RGB")

    if args.dry_run:
        vdir = E.save_verify_crops(assets_dir, args.label, paint_img, paint_img, bbox, "dryrun")
        print(f"[phantom_erase] dry-run crop saved to {vdir}")
        return

    before_sha = E.sha12(paint_path)
    log = E.load_log(assets_dir)
    already = [e for e in log if e.get("control") == args.label and e.get("before_sha") == before_sha
               and e.get("status", "").startswith("erased")]
    if already:
        print(f"[phantom_erase] {args.label}: paint.png sha {before_sha} already has a logged erase — no-op (delete the log entry to force)")
        return

    method = "gpt-image-2" if args.escalate else "gemini-2.5-flash"
    fn = erase_gpt_image2 if args.escalate else erase_gemini25
    print(f"[phantom_erase] {args.label}: erasing px{bbox} via {method} ...")
    t0 = time.time()
    if args.escalate:
        new_img, crop_box = fn(assets_dir, paint_img, bbox, args.prompt)
    else:
        new_img, crop_box = fn(assets_dir, paint_img, bbox, args.prompt, args.seed)
    elapsed = time.time() - t0
    print(f"[phantom_erase] {args.label}: {method} returned in {elapsed:.1f}s")

    tag = time.strftime("%Y%m%dT%H%M%S")
    vdir = E.save_verify_crops(assets_dir, args.label, paint_img, new_img, crop_box, tag)

    new_img.save(paint_path)
    joint_path = os.path.join(assets_dir, "joint-4k.png")
    if os.path.exists(joint_path):
        joint = Image.open(joint_path)
        joint.paste(new_img, (0, 0))
        joint.save(joint_path)

    after_sha = E.sha12(paint_path)
    log.append({
        "control": args.label, "method": method, "before_sha": before_sha, "after_sha": after_sha,
        "bbox_px": list(bbox), "crop_box_px": list(crop_box), "seed": args.seed, "ts": tag,
        "status": "erased", "verify_dir": os.path.relpath(vdir, assets_dir),
        "cost_estimate_usd": E.COST_ESTIMATE.get(method, 0),
        "note": "phantom_erase.py: manual-bbox defect (extra button / icon-only / baked text), not a groove/socket detect_bbox() target",
    })
    E.save_log(assets_dir, log)
    print(f"[phantom_erase] {args.label}: {method} erase written — paint.png {before_sha} -> {after_sha}, "
          f"verify crops in {vdir} (~${E.COST_ESTIMATE.get(method, 0):.4f})")


if __name__ == "__main__":
    main()
