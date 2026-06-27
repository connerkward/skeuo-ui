#!/usr/bin/env python3
"""Combiner for the button-alignment grader.

CLI: python grade.py <skin-id> [--shift S] [--no-vlm]

- Loads public/generated/<id>-frame.png + <id>-template.json.
- If --shift S (normalized, e.g. 0.18): translate EVERY interactive rect by
  (+S, +S) BEFORE grading. This synthesizes a KNOWN-MISALIGNED skin (the boxes
  now point off their painted features) -> labeled negatives for calibration.
- Builds the labeled overlay (overlay.build_overlay), runs det.grade_det +
  vlm.grade_vlm, and COMBINES per control with the AND rule:

      aligned = det.aligned AND vlm.aligned

  Rationale: a control is only "on target" if BOTH an independent pixel-saliency
  check (det: is real image detail where the box is) AND a vision model (vlm: does
  the box sit on the painted control) agree. AND is conservative: either signal
  can VETO. We also report how often the two disagree (the seam where one fired
  and the other didn't), so the combine rule's effect is measurable, not asserted.

- Writes .proof/grade-<id>[-shiftS].jpg = overlay tinted with the COMBINED verdict
  (green=aligned / red=mis) + a header strip with the skin score (fraction aligned).
- Writes tools/align-grader/last-<id>.json (or last-<id>-shiftS.json).

The det signal is independent of the template that placed the rects (it measures
frame pixels); the vlm sees the same shifted overlay. Shifting the rects moves the
boxes off the real painted controls, so BOTH halves should flip to misaligned —
that is the independent ground-truth construction (verify-outputs-rule s2/s3).
"""
import json
import os
import sys
import tempfile
import copy

from PIL import Image, ImageDraw, ImageFont

from common import load_template, interactive_regions
from overlay import build_overlay, _font
from det import grade_det
from vlm import grade_vlm

GEN_DIR = "/Users/conner/dev/skeuo-ui/public/generated"
PROOF_DIR = "/Users/conner/dev/skeuo-ui/.proof"
GREEN = (60, 220, 110)
RED = (235, 70, 70)


def _shifted_template_file(template, shift):
    """Return path to a temp template JSON with every interactive rect moved
    by (+shift, +shift). Non-interactive (display) regions are left as-is."""
    t = copy.deepcopy(template)
    inter_ids = {key for key, _ in interactive_regions(template)}
    for i, r in enumerate(t.get("regions", [])):
        key = r.get("id") or r.get("bind") or f"region{i}"
        if key in inter_ids:
            rect = r["rect"]
            rect["x"] = rect["x"] + shift
            rect["y"] = rect["y"] + shift
    fd, path = tempfile.mkstemp(suffix="-shifted-template.json")
    with os.fdopen(fd, "w") as f:
        json.dump(t, f)
    return path


def _header(out_path, score, n_aligned, n_total, title):
    """Prepend a header strip with the score onto the saved JPEG (in place)."""
    img = Image.open(out_path).convert("RGB")
    W, H = img.size
    strip_h = max(56, int(round(H * 0.045)))
    canvas = Image.new("RGB", (W, H + strip_h), (18, 18, 24))
    canvas.paste(img, (0, strip_h))
    draw = ImageDraw.Draw(canvas)
    font = _font(max(20, int(round(strip_h * 0.42))))
    pct = 100.0 * score
    color = GREEN if score >= 0.999 else (RED if score < 0.5 else (240, 200, 80))
    txt = f"{title}   score {pct:.0f}%  ({n_aligned}/{n_total} aligned)"
    draw.text((14, strip_h * 0.25), txt, fill=color, font=font)
    canvas.save(out_path, "JPEG", quality=88)


def grade(skin_id, shift=0.0, use_vlm=True):
    frame = os.path.join(GEN_DIR, f"{skin_id}-frame.png")
    tmpl = os.path.join(GEN_DIR, f"{skin_id}-template.json")
    if not os.path.exists(frame) or not os.path.exists(tmpl):
        raise FileNotFoundError(f"missing frame/template for {skin_id}")

    template = load_template(tmpl)

    # If shifting, build a temp shifted template and grade against THAT so the
    # overlay boxes, det rects, and vlm all see the same moved positions.
    grade_tmpl_path = tmpl
    tmp_to_clean = None
    if shift:
        grade_tmpl_path = _shifted_template_file(template, shift)
        tmp_to_clean = grade_tmpl_path
        template = load_template(grade_tmpl_path)

    suffix = f"-shift{shift}" if shift else ""
    overlay_path = os.path.join(PROOF_DIR, f"grade-{skin_id}{suffix}.jpg")

    # 1) deterministic + plain (untinted) overlay for the vlm to look at.
    det = grade_det(frame, grade_tmpl_path)
    build_overlay(frame, grade_tmpl_path, overlay_path, verdicts=None)

    # controls list for the vlm: bind+kind, in template order.
    controls = [
        {"bind": r.get("bind") or r.get("id"), "kind": r.get("kind")}
        for _, r in interactive_regions(template)
    ]

    # 2) vlm on the labeled overlay.
    if use_vlm:
        vlm = grade_vlm(overlay_path, controls)
    else:
        vlm = {c["bind"]: {"bind": c["bind"], "aligned": True, "votes": [],
                           "confidence": 0.0, "note": "vlm skipped"}
               for c in controls}

    # 3) combine per control (AND), tracking disagreement.
    rows = []
    verdicts = {}        # key -> combined bool, for re-tinting the overlay
    disagreements = 0
    for key, region in interactive_regions(template):
        bind = region.get("bind") or region.get("id")
        kind = region.get("kind")
        d = det.get(key, {"aligned": False, "presence": 0.0, "offset": 1.0,
                          "bind": bind})
        v = vlm.get(bind, {"aligned": False, "votes": [], "confidence": 0.0,
                           "note": "no vlm record"})
        d_al = bool(d.get("aligned"))
        v_al = bool(v.get("aligned"))
        combined = d_al and v_al
        if d_al != v_al:
            disagreements += 1
        verdicts[key] = combined
        rows.append({
            "bind": bind,
            "kind": kind,
            "det": {"presence": d.get("presence"), "offset": d.get("offset"),
                    "aligned": d_al},
            "vlm": {"aligned": v_al, "votes": v.get("votes"),
                    "confidence": v.get("confidence"), "note": v.get("note")},
            "aligned": combined,
        })

    n_total = len(rows)
    n_aligned = sum(1 for r in rows if r["aligned"])
    score = (n_aligned / n_total) if n_total else 0.0

    # 4) re-render the overlay TINTED with combined verdicts + header.
    build_overlay(frame, grade_tmpl_path, overlay_path, verdicts=verdicts)
    title = f"{skin_id}{(' shift '+str(shift)) if shift else ' (as-is)'}"
    _header(overlay_path, score, n_aligned, n_total, title)

    result = {
        "id": skin_id,
        "shift": shift,
        "score": round(score, 4),
        "n_aligned": n_aligned,
        "n_total": n_total,
        "disagreements": disagreements,
        "controls": rows,
    }
    last_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"last-{skin_id}{suffix}.json",
    )
    with open(last_path, "w") as f:
        json.dump(result, f, indent=2)

    if tmp_to_clean and os.path.exists(tmp_to_clean):
        os.remove(tmp_to_clean)

    result["_overlay"] = overlay_path
    result["_last_json"] = last_path
    return result


def main():
    args = sys.argv[1:]
    if not args:
        sys.stderr.write("usage: python grade.py <skin-id> [--shift S] [--no-vlm]\n")
        sys.exit(2)
    skin_id = args[0]
    shift = 0.0
    use_vlm = True
    i = 1
    while i < len(args):
        if args[i] == "--shift":
            shift = float(args[i + 1]); i += 2
        elif args[i] == "--no-vlm":
            use_vlm = False; i += 1
        else:
            i += 1
    res = grade(skin_id, shift=shift, use_vlm=use_vlm)
    printable = {k: v for k, v in res.items() if not k.startswith("_")}
    print(json.dumps(printable, indent=2))
    sys.stderr.write(f"\noverlay: {res['_overlay']}\nlast:    {res['_last_json']}\n")


if __name__ == "__main__":
    main()
