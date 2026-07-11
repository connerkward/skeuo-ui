#!/usr/bin/env python3
"""Bonus probe (2026-07-11) — does honoring GOOGLE'S OWN DOCUMENTED bounding-box convention
fix the broken y-frame the imgjson experiment found?

imgjson/run_tests.py test A asked gemini-3-pro-image-preview (the IMAGE model) for boxes in
an AD-HOC convention: {"name","x","y","w","h"}, x/y = top-left, normalized 0..1 against the
image's OWN pixel frame. Result: raw mean IoU 0.003; diagnose.py's affine fit found x came
back correct (scale 0.999) but y came back compressed (best-fit gt = 0.66*pred + 0.12,
suspiciously close to a square-letterbox/padding remap — as if the model reasons in some
internal square-ish preprocessed frame, not the image's real non-square 2304x3712 frame).

Google's OWN documented bounding-box convention (ai.google.dev/gemini-api/docs/
image-understanding, fetched 2026-07-11) is DIFFERENT on three counts: (1) order
[ymin, xmin, ymax, xmax] not [x,y,w,h]; (2) scale 0-1000 integers, not 0-1 floats; (3) it is
documented under "image understanding" (text/understanding models), with NO stated model
scope covering image-GENERATION models (gemini-3-pro-image-preview / "Nano Banana Pro") —
the imgjson test A was already off-label by asking the image-gen model for boxes at all, and
this probe additionally asks whether at least matching Google's OWN coordinate convention
(instead of our ad-hoc one) rescues the y-frame.

Single Vertex call, same model/image/roster as imgjson test A (gemini-3-pro-image-preview,
responseModalities=["TEXT","IMAGE"] — TEXT-alone is HTTP 400 per imgjson's own finding),
scored against the SAME regions.json ground truth via imgjson's own IoU/center-error code
(imported, not reimplemented).

Usage: python3 bonus_probe.py   -> writes bonus_probe.json
"""
import os, sys, json, time
IMGJSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "imgjson")
sys.path.insert(0, IMGJSON)
import run_tests as T   # noqa: E402  (proven imgjson harness — imported, not edited/copied)
import score as S        # noqa: E402  (iou() / center_err_px() — reused verbatim)

HERE = os.path.dirname(os.path.abspath(__file__))

GOOGLE_PROMPT = (
    "This image is a top-down skeuomorphic media-player skin. It contains exactly these "
    "10 controls, each present exactly once: " + ", ".join(f"{n} ({T.ROLES[n]})" for n in T.ROSTER) + ".\n\n"
    "Detect the 2d bounding boxes of all 10 controls listed above. Output a JSON list of "
    "bounding boxes where each entry contains the 2D bounding box in the key \"box_2d\" and "
    "the control name in the key \"label\". The box_2d should be [ymin, xmin, ymax, xmax] "
    "normalized to 0-1000, relative to this image's own width and height. Do not include "
    "any control not in the list above. Do not omit any control in the list."
)


def box2d_to_xywh(box_2d):
    """[ymin,xmin,ymax,xmax] @ 0-1000 (Google's documented convention) -> [x,y,w,h] @ 0-1
    (this repo's / imgjson's ground-truth convention) so we can reuse score.iou/center_err_px
    unmodified."""
    ymin, xmin, ymax, xmax = box_2d
    x, y = xmin / 1000.0, ymin / 1000.0
    w, h = (xmax - xmin) / 1000.0, (ymax - ymin) / 1000.0
    return [x, y, w, h]


def main():
    print("[bonus_probe] calling gemini-3-pro-image-preview with GOOGLE'S documented "
          "box_2d [ymin,xmin,ymax,xmax]@0-1000 convention...", flush=True)
    t0 = time.time()
    resp = T.call_image_model(GOOGLE_PROMPT, ["TEXT", "IMAGE"], seed=71)
    dt = time.time() - t0
    json.dump(resp, open(os.path.join(HERE, "bonus_probe_raw.json"), "w"), indent=2)
    texts, imgs, finish = T.extract_parts(resp)
    raw_text = "".join(texts)
    parsed, err = T.try_parse_json(raw_text) if texts else (None, "no text parts")
    print(f"[bonus_probe] {dt:.1f}s finish={finish} text_parts={len(texts)} "
          f"image_parts={len(imgs)} parse_ok={parsed is not None}")

    pred_list = []
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name = item.get("label")
            box_2d = item.get("box_2d")
            if name not in S.GT or not (isinstance(box_2d, list) and len(box_2d) == 4):
                continue
            try:
                xywh = box2d_to_xywh([float(v) for v in box_2d])
            except (TypeError, ValueError):
                continue
            pred_list.append({"name": name, "x": xywh[0], "y": xywh[1], "w": xywh[2], "h": xywh[3]})

    smry, rows = S.score_pred(pred_list)
    out = {
        "probe": "bonus_google_box_convention",
        "model": T.IMAGE_MODEL, "endpoint": "vertex generateContent (global)",
        "prompt_convention": "google-documented: box_2d=[ymin,xmin,ymax,xmax] normalized 0-1000",
        "prior_convention_ref": "imgjson/run_tests.py test A: {name,x,y,w,h} x,y=top-left norm 0-1 (raw mean IoU 0.003, y-frame scale~0.66-0.73 offset~0.06-0.12)",
        "seconds": round(dt, 1), "finishReason": finish,
        "n_text_parts": len(texts), "n_image_parts": len(imgs),
        "parse_ok": parsed is not None, "parse_error": err,
        "n_returned": len(parsed) if isinstance(parsed, list) else 0,
        "n_matched_scoreable": len(pred_list),
        "raw_text_head": raw_text[:1500],
        "summary": smry, "per_control": rows,
    }
    json.dump(out, open(os.path.join(HERE, "bonus_probe.json"), "w"), indent=2)
    print(f"[bonus_probe] mean_iou={smry.get('mean_iou')} mean_ctr_err_px={smry.get('mean_center_err_px')} "
          f"(compare vs test A raw mean_iou=0.003, ctr_err=507px)")
    print("-> bonus_probe.json")


if __name__ == "__main__":
    main()
