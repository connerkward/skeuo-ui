#!/usr/bin/env python3
"""Diagnosis pass — is the image model's near-zero IoU coordinate NOISE or a
coordinate-FRAME mismatch? Fits a per-axis affine (gt_center = a*pred_center + b,
least squares over matched controls) and re-scores after applying it; also tests
the visualizer/album_art label swap observed in test A. Writes out/diagnosis.json
and labeled overlay PNGs (viz/overlay-*.png): GREEN = regions.json ground truth,
RED = model prediction as returned, ORANGE = prediction after affine rescue.
"""
import os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
VIZ = os.path.join(HERE, "viz")
os.makedirs(VIZ, exist_ok=True)
import run_tests as T
import score as S

GT = {n: r["device"] for n, r in json.load(open(os.path.join(T.ASSET, "regions.json")))["regions"].items()}
PAINT = Image.open(os.path.join(T.ASSET, "paint.png")).convert("RGB")
PW, PH = PAINT.size
SCALE = 760 / PW


def load_pred(key):
    resp = json.load(open(os.path.join(OUT, f"{key}_raw.json")))
    texts, _, _ = T.extract_parts(resp)
    parsed, _ = T.try_parse_json("".join(texts))
    out = {}
    for p in parsed or []:
        if isinstance(p, dict) and p.get("name") in GT:
            try:
                out[p["name"]] = [float(p["x"]), float(p["y"]), float(p["w"]), float(p["h"])]
            except (KeyError, TypeError, ValueError):
                pass  # e.g. c_text_model's playpause row came back without "h"
    return out


def affine_fit(pd, exclude=()):
    names = [n for n in GT if n in pd and n not in exclude]
    fits = {}
    for ax in (0, 1):
        p = np.array([pd[n][ax] + pd[n][ax + 2] / 2 for n in names])
        g = np.array([GT[n][ax] + GT[n][ax + 2] / 2 for n in names])
        A = np.vstack([p, np.ones(len(p))]).T
        (a, b), *_ = np.linalg.lstsq(A, g, rcond=None)
        resid = a * p + b - g
        dim = PW if ax == 0 else PH
        fits["xy"[ax]] = {"scale": round(float(a), 4), "offset": round(float(b), 4),
                          "rms_px": round(float(np.sqrt(np.mean(resid ** 2))) * dim, 1),
                          "max_px": round(float(np.max(np.abs(resid))) * dim, 1),
                          "n": len(names)}
    return fits


def apply_affine(pd, fits):
    out = {}
    for n, v in pd.items():
        cx, cy = v[0] + v[2] / 2, v[1] + v[3] / 2
        cx2 = fits["x"]["scale"] * cx + fits["x"]["offset"]
        cy2 = fits["y"]["scale"] * cy + fits["y"]["offset"]
        w2 = v[2] * fits["x"]["scale"]
        h2 = v[3] * fits["y"]["scale"]
        out[n] = [cx2 - w2 / 2, cy2 - h2 / 2, w2, h2]
    return out


def rescore(pd):
    smry, _rows = S.score_pred([{"name": n, "x": v[0], "y": v[1], "w": v[2], "h": v[3]}
                                for n, v in pd.items()])
    return smry


def draw_overlay(key, pd, pd_fixed=None):
    im = PAINT.resize((int(PW * SCALE), int(PH * SCALE)))
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except Exception:
        font = ImageFont.load_default()

    def box(v, color, label):
        x0, y0 = v[0] * PW * SCALE, v[1] * PH * SCALE
        x1, y1 = (v[0] + v[2]) * PW * SCALE, (v[1] + v[3]) * PH * SCALE
        dr.rectangle([x0, y0, x1, y1], outline=color, width=2)
        tw = dr.textlength(label, font=font)
        dr.rectangle([x0, max(0, y0 - 16), x0 + tw + 6, max(16, y0)], fill=(0, 0, 0))
        dr.text((x0 + 3, max(0, y0 - 15)), label, fill=color, font=font)

    for n, v in GT.items():
        box(v, (0, 230, 80), f"GT {n}")
    for n, v in pd.items():
        box(v, (255, 60, 60), f"pred {n}")
    if pd_fixed:
        for n, v in pd_fixed.items():
            box(v, (255, 170, 0), f"fix {n}")
    p = os.path.join(VIZ, f"overlay-{key}.png")
    im.save(p)
    return p


def main():
    diag = {}
    for key in ["a_text_only", "b_interleaved", "c_text_model"]:
        pd = load_pred(key)
        entry = {"raw": rescore(pd)}
        # test A showed a visualizer/album_art LABEL swap — evaluate it for all, but
        # only KEEP the swap when it actually improves (C labels them correctly;
        # forcing the swap there would corrupt the affine fit with two bad points)
        pd_sw = dict(pd)
        if "visualizer" in pd and "album_art" in pd:
            trial = dict(pd)
            trial["visualizer"], trial["album_art"] = pd["album_art"], pd["visualizer"]
            sw_score = rescore(trial)
            entry["label_swap_vis_album"] = sw_score
            if (sw_score["mean_iou"] or 0) > (entry["raw"]["mean_iou"] or 0):
                pd_sw = trial
                entry["swap_kept"] = True
            else:
                entry["swap_kept"] = False
        fits = affine_fit(pd_sw, exclude=())
        entry["affine_fit"] = fits
        pd_fix = apply_affine(pd_sw, fits)
        entry["swap_plus_affine"] = rescore(pd_fix)
        draw_overlay(key, pd, pd_fix if key != "c_text_model" else None)
        diag[key] = entry
        print(f"{key}: raw meanIoU={entry['raw']['mean_iou']} → swap+affine meanIoU={entry['swap_plus_affine']['mean_iou']} "
              f"ctrErr {entry['raw']['mean_center_err_px']} → {entry['swap_plus_affine']['mean_center_err_px']}px "
              f"(y-fit scale={fits['y']['scale']} rms={fits['y']['rms_px']}px)")
    json.dump(diag, open(os.path.join(OUT, "diagnosis.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
