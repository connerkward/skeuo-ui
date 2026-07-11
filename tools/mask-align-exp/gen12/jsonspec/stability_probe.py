#!/usr/bin/env python3
"""Stability probe (2026-07-11, round 2) — is the box_2d transposition bonus_probe.py found
(n=1, mean IoU 0.79 under the [ymin,xmin,XMAX,YMAX] reading) a STABLE quirk of this model, or a
one-off? A stable quirk is calibratable (flip two array slots and trust the numbers); an
unstable one isn't — this is the make-or-break question bonus_probe.py's own docstring flagged
as untested ("the transposition's stability across calls is untested").

Design: 3 more calls, SAME Google-documented convention (box_2d=[ymin,xmin,ymax,xmax]@0-1000)
as bonus_probe.py:
  - repeat_seed72 / repeat_seed73: same wc-goldshield paint.png, same prompt, different seeds
    (this model's generateContent only exposes `seed` for variation on this endpoint).
  - crosscheck_diablo_seed74: a DIFFERENT skin (assets-diablo-gothic/paint.png), same prompt
    shape, to check the behavior isn't specific to one image's content.

Each call is scored two ways against its own regions.json ground truth, reusing bonus_probe's
box2d_to_xywh + imgjson's score.iou/center_err_px (imported, not reimplemented):
  1. "as documented" — Google's literal [ymin,xmin,ymax,xmax] order.
  2. "as transposed" — bonus_probe's observed [ymin,xmin,XMAX,YMAX] reading.
Whichever reading wins per call, and whether the SAME reading wins on every call, answers the
stability question.

RESULT (2026-07-11 run, seeds 72/73/74 + bonus_probe's seed 71): the transposition is
UNSTABLE. Seed 71 emitted [ymin,xmin,XMAX,YMAX]; seeds 72/73/74 all emitted Google's
DOCUMENTED [ymin,xmin,ymax,xmax]. Element order varies call-to-call → not calibratable by a
fixed slot-swap. See stability_probe.json.

Usage:
  python3 stability_probe.py            -> 3 Vertex calls, writes stability_probe.json
  python3 stability_probe.py --rescore  -> no API calls; rescore from saved stability_*_raw.json
                                           (falls back to the box_2d arrays recorded in an
                                           existing stability_probe.json for any call whose
                                           raw file is missing — seed72's raw was swept by the
                                           2026-07-11 unscoped-git-commit incident, see
                                           docs/INCIDENTS.md)
Cost: 3 Vertex generateContent calls, image model, TEXT+IMAGE modality, JSON-only ask
(~$0.05 each) => ~$0.15 total. --rescore is $0.
"""
import os, sys, json, time, base64

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
IMGJSON = os.path.join(GEN12, "imgjson")
sys.path.insert(0, IMGJSON)
sys.path.insert(0, HERE)
import run_tests as T          # noqa: E402  (proven imgjson harness — endpoint, retry, extract_parts, try_parse_json)
import score as S               # noqa: E402  (iou() / center_err_px() — reused verbatim)
from bonus_probe import box2d_to_xywh  # noqa: E402  (same transform, not re-typed)

CALLS = [
    {"tag": "repeat_seed72", "asset": "assets-wc-goldshield", "seed": 72},
    {"tag": "repeat_seed73", "asset": "assets-wc-goldshield", "seed": 73},
    {"tag": "crosscheck_diablo_seed74", "asset": "assets-diablo-gothic", "seed": 74},
]


def load_gt(asset_dir):
    regions = json.load(open(os.path.join(GEN12, asset_dir, "regions.json")))
    return {n: r["device"] for n, r in regions["regions"].items()}, regions["roles"], list(regions["regions"].keys())


def build_prompt(roles, roster):
    return (
        "This image is a top-down skeuomorphic media-player skin. It contains exactly these "
        "10 controls, each present exactly once: " + ", ".join(f"{n} ({roles[n]})" for n in roster) + ".\n\n"
        "Detect the 2d bounding boxes of all 10 controls listed above. Output a JSON list of "
        "bounding boxes where each entry contains the 2D bounding box in the key \"box_2d\" and "
        "the control name in the key \"label\". The box_2d should be [ymin, xmin, ymax, xmax] "
        "normalized to 0-1000, relative to this image's own width and height. Do not include "
        "any control not in the list above. Do not omit any control in the list."
    )


def score_reading(parsed, gt, transpose):
    """transpose=False: box_2d taken as Google's documented [ymin,xmin,ymax,xmax].
    transpose=True: bonus_probe's observed [ymin,xmin,XMAX,YMAX] (slot 2 is xmax, slot 3 is
    ymax — undo by swapping slots 2/3 back to canonical order before the xywh transform).

    Scores against the PASSED gt, NOT S.score_pred — S.score_pred reads module-level S.GT
    (always wc-goldshield), which silently mis-scored the diablo cross-check on this probe's
    first run (caught because the per-control transposition_flags — computed against the
    correct gt — disagreed with the IoU table). Both paints are 2304x3712, so
    S.center_err_px's module-level PAINT_W/H is dimensionally correct for either skin."""
    if not isinstance(parsed, list):
        return None, None
    rows = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = item.get("label")
        box_2d = item.get("box_2d")
        if name not in gt or not (isinstance(box_2d, list) and len(box_2d) == 4):
            continue
        try:
            b = [float(v) for v in box_2d]
        except (TypeError, ValueError):
            continue
        if transpose:
            b = [b[0], b[1], b[3], b[2]]  # undo the observed swap -> canonical [ymin,xmin,ymax,xmax]
        box = box2d_to_xywh(b)
        rows[name] = {"pred": box, "gt": gt[name], "iou": round(S.iou(box, gt[name]), 4),
                      "center_err_px": round(S.center_err_px(box, gt[name]), 1)}
    ious = [r["iou"] for r in rows.values()]
    errs = [r["center_err_px"] for r in rows.values()]
    smry = {
        "n_returned": len(parsed), "n_matched": len(rows),
        "mean_iou": round(sum(ious) / len(ious), 4) if ious else None,
        "median_iou": round(sorted(ious)[len(ious) // 2], 4) if ious else None,
        "min_iou": round(min(ious), 4) if ious else None,
        "mean_center_err_px": round(sum(errs) / len(errs), 1) if errs else None,
        "max_center_err_px": round(max(errs), 1) if errs else None,
        "worst_control": min(rows, key=lambda n: rows[n]["iou"]) if rows else None,
    }
    return smry, rows


def transposition_flags(parsed, gt):
    """Per-control raw-order check, independent of the IoU scoring: does box_2d slot 2 sit
    near gt xmax and slot 3 near gt ymax (the TRANSPOSED emission), or slot 2 near gt ymax and
    slot 3 near gt xmax (the DOCUMENTED emission)? 60/1000 tolerance."""
    flags = {}
    if not isinstance(parsed, list):
        return flags
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = item.get("label")
        box_2d = item.get("box_2d")
        if name not in gt or not (isinstance(box_2d, list) and len(box_2d) == 4):
            continue
        gx0, gy0, gw, gh = gt[name]
        gt_xmax_1000 = round((gx0 + gw) * 1000)
        gt_ymax_1000 = round((gy0 + gh) * 1000)
        b2, b3 = box_2d[2], box_2d[3]
        flags[name] = {
            "box_2d": box_2d, "gt_xmax_1000": gt_xmax_1000, "gt_ymax_1000": gt_ymax_1000,
            "matches_transposed_reading": abs(b2 - gt_xmax_1000) < 60 and abs(b3 - gt_ymax_1000) < 60,
            "matches_documented_reading": abs(b3 - gt_xmax_1000) < 60 and abs(b2 - gt_ymax_1000) < 60,
        }
    return flags


def call_vertex(asset_dir, prompt, seed, tag):
    b64 = base64.b64encode(open(os.path.join(GEN12, asset_dir, "paint.png"), "rb").read()).decode()
    body = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "seed": seed, "candidateCount": 1},
    }
    return T._post_with_retry(T.endpoint(T.IMAGE_MODEL), body, tag)


def get_parsed(tag, asset_dir, seed, rescore):
    """Return (parsed_list, meta). In rescore mode, prefer the saved raw response; fall back
    to the box_2d arrays recorded in an existing stability_probe.json (raw swept — incident)."""
    raw_path = os.path.join(HERE, f"stability_{tag}_raw.json")
    if rescore:
        if os.path.exists(raw_path):
            resp = json.load(open(raw_path))
            texts, _imgs, finish = T.extract_parts(resp)
            parsed, err = T.try_parse_json("".join(texts)) if texts else (None, "no text parts")
            return parsed, {"source": "raw_file", "finishReason": finish,
                            "n_text_parts": len(texts), "parse_ok": parsed is not None, "parse_error": err}
        prev_path = os.path.join(HERE, "stability_probe.json")
        prev = json.load(open(prev_path))
        prev_call = next(c for c in prev["calls"] if c["tag"] == tag)
        parsed = [{"label": n, "box_2d": f["box_2d"]} for n, f in prev_call["transposition_flags"].items()]
        return parsed, {"source": "reconstructed_from_prev_probe_flags (raw swept, see docs/INCIDENTS.md 2026-07-11)",
                        "finishReason": prev_call.get("finishReason"),
                        "n_text_parts": prev_call.get("n_text_parts"),
                        "parse_ok": prev_call.get("parse_ok"), "parse_error": prev_call.get("parse_error"),
                        "seconds": prev_call.get("seconds")}
    gt, roles, roster = load_gt(asset_dir)
    print(f"[{tag}] calling {T.IMAGE_MODEL} on {asset_dir}/paint.png, seed={seed}...", flush=True)
    t0 = time.time()
    resp = call_vertex(asset_dir, build_prompt(roles, roster), seed, tag)
    dt = time.time() - t0
    json.dump(resp, open(raw_path, "w"), indent=2)
    texts, _imgs, finish = T.extract_parts(resp)
    parsed, err = T.try_parse_json("".join(texts)) if texts else (None, "no text parts")
    print(f"[{tag}] {dt:.1f}s finish={finish} text_parts={len(texts)} parse_ok={parsed is not None}")
    return parsed, {"source": "live_call", "seconds": round(dt, 1), "finishReason": finish,
                    "n_text_parts": len(texts), "parse_ok": parsed is not None, "parse_error": err}


def main():
    rescore = "--rescore" in sys.argv
    results = []
    for i, c in enumerate(CALLS):
        gt, _roles, _roster = load_gt(c["asset"])
        parsed, meta = get_parsed(c["tag"], c["asset"], c["seed"], rescore)
        doc_smry, doc_rows = score_reading(parsed, gt, transpose=False)
        trans_smry, trans_rows = score_reading(parsed, gt, transpose=True)
        results.append({
            "tag": c["tag"], "asset": c["asset"], "seed": c["seed"], **meta,
            "documented_reading": {"summary": doc_smry, "per_control": doc_rows},
            "transposed_reading": {"summary": trans_smry, "per_control": trans_rows},
            "transposition_flags": transposition_flags(parsed, gt),
        })
        if not rescore and i < len(CALLS) - 1:
            time.sleep(15)

    verdicts = []
    for r in results:
        doc_iou = (r["documented_reading"]["summary"] or {}).get("mean_iou") or 0
        trans_iou = (r["transposed_reading"]["summary"] or {}).get("mean_iou") or 0
        flags = r["transposition_flags"]
        verdicts.append({
            "tag": r["tag"], "asset": r["asset"], "seed": r["seed"],
            "documented_mean_iou": doc_iou, "transposed_mean_iou": trans_iou,
            "transposed_wins": trans_iou > doc_iou,
            "n_controls_flagged_transposed": sum(1 for f in flags.values() if f["matches_transposed_reading"]),
            "n_controls_flagged_documented": sum(1 for f in flags.values() if f["matches_documented_reading"]),
        })
    all_transposed = all(v["transposed_wins"] for v in verdicts)

    out = {
        "probe": "stability_of_box2d_transposition",
        "prior_n1_result_ref": "jsonspec/bonus_probe.json (seed 71): transposed_reading.summary.mean_iou=0.7892 (median 0.8402, min 0.3732 album_art)",
        "calls": results,
        "cross_call_consistency": {
            "verdicts": verdicts,
            "transposed_reading_wins_every_call": all_transposed,
            "stable_quirk": all_transposed,
            "conclusion": (
                "UNSTABLE. Including bonus_probe's seed-71 call (transposed emission), the element "
                "order varies call-to-call: seed 71 emitted [ymin,xmin,XMAX,YMAX]; seeds 72/73/74 "
                "emitted Google's documented [ymin,xmin,ymax,xmax]. A fixed slot-swap calibration is "
                "therefore wrong on some calls; any consumer must disambiguate the order PER CALL "
                "(e.g. reject boxes whose documented reading yields non-positive w/h, or check both "
                "readings against a template prior)."
            ),
        },
    }
    json.dump(out, open(os.path.join(HERE, "stability_probe.json"), "w"), indent=2)
    print("\n=== stability_probe summary ===")
    for v in verdicts:
        print(f"  {v['tag']:28s} doc_iou={v['documented_mean_iou']:.4f}  trans_iou={v['transposed_mean_iou']:.4f}  "
              f"transposed_wins={v['transposed_wins']}  raw-order flags: T={v['n_controls_flagged_transposed']}/10 "
              f"D={v['n_controls_flagged_documented']}/10")
    print(f"stable_quirk (transposed wins EVERY call) = {all_transposed}")
    print("-> stability_probe.json")


if __name__ == "__main__":
    main()
