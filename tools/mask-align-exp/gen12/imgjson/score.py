#!/usr/bin/env python3
"""Score the imgjson test outputs deterministically against ground truth.

Ground truth: assets-wc-goldshield/regions.json regions[name].device — normalized
[x,y,w,h] over paint.png's own pixel frame (2304x3712), verified by cropping (the
device boxes land exactly on the painted controls; see run_tests.py header).

Metrics per test: JSON parse ok, n controls returned/matched, per-control IoU,
mean/median IoU, mean center error in px (paint.png frame), worst control.
Writes out/scores.json.
"""
import os, json
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
import run_tests as T  # reuse ASSET path + try_parse_json

PAINT_W, PAINT_H = Image.open(os.path.join(T.ASSET, "paint.png")).size
GT = {n: r["device"] for n, r in json.load(open(os.path.join(T.ASSET, "regions.json")))["regions"].items()}


def iou(a, b):
    ax0, ay0, aw, ah = a; bx0, by0, bw, bh = b
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0: return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    return inter / (aw * ah + bw * bh - inter)


def center_err_px(a, b):
    acx, acy = a[0] + a[2] / 2, a[1] + a[3] / 2
    bcx, bcy = b[0] + b[2] / 2, b[1] + b[3] / 2
    return (((acx - bcx) * PAINT_W) ** 2 + ((acy - bcy) * PAINT_H) ** 2) ** 0.5


def score_pred(pred_list):
    rows, matched = {}, 0
    for item in pred_list if isinstance(pred_list, list) else []:
        if not isinstance(item, dict): continue
        n = item.get("name")
        if n not in GT: continue
        try:
            box = [float(item["x"]), float(item["y"]), float(item["w"]), float(item["h"])]
        except (KeyError, TypeError, ValueError):
            continue
        matched += 1
        rows[n] = {"pred": box, "gt": GT[n], "iou": round(iou(box, GT[n]), 4),
                   "center_err_px": round(center_err_px(box, GT[n]), 1)}
    ious = [r["iou"] for r in rows.values()]
    errs = [r["center_err_px"] for r in rows.values()]
    smry = {
        "n_returned": len(pred_list) if isinstance(pred_list, list) else 0,
        "n_matched": matched,
        "mean_iou": round(sum(ious) / len(ious), 4) if ious else None,
        "median_iou": round(sorted(ious)[len(ious) // 2], 4) if ious else None,
        "min_iou": round(min(ious), 4) if ious else None,
        "mean_center_err_px": round(sum(errs) / len(errs), 1) if errs else None,
        "max_center_err_px": round(max(errs), 1) if errs else None,
        "worst_control": min(rows, key=lambda n: rows[n]["iou"]) if rows else None,
    }
    return smry, rows


def main():
    raw = json.load(open(os.path.join(OUT, "results_raw.json")))
    scores = {}
    for key, res in raw.items():
        # Re-derive from the full saved Vertex response (source of truth), joining
        # text parts with "" — see run_tests.py: Vertex splits the text stream at
        # arbitrary byte boundaries (mid-number), so any injected separator corrupts
        # the JSON.
        resp = json.load(open(os.path.join(OUT, f"{key}_raw.json")))
        texts, _imgs, _fin = T.extract_parts(resp)
        parsed, err = T.try_parse_json("".join(texts)) if texts else (None, "no text parts")
        entry = {"parse_ok": parsed is not None, "parse_error": err,
                 "finishReason": res.get("finishReason"),
                 "n_text_parts": res.get("n_text_parts"), "n_image_parts": res.get("n_image_parts"),
                 "seconds": res.get("seconds")}
        if parsed is not None:
            smry, rows = score_pred(parsed)
            entry["summary"] = smry
            entry["per_control"] = rows
        scores[key] = entry
    json.dump(scores, open(os.path.join(OUT, "scores.json"), "w"), indent=2)
    for k, v in scores.items():
        s = v.get("summary", {})
        print(f"{k}: parse_ok={v['parse_ok']} matched={s.get('n_matched')}/10 "
              f"meanIoU={s.get('mean_iou')} medIoU={s.get('median_iou')} "
              f"meanCtrErr={s.get('mean_center_err_px')}px worst={s.get('worst_control')}")


if __name__ == "__main__":
    main()
