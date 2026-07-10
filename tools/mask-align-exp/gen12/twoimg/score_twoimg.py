#!/usr/bin/env python3
"""score_twoimg — run ../extract12.py (pass 1, no matte) on each twoimg gen, collect the
standard gates (leak%, emptiness, controls-found, region-misplacement), PLUS a perimeter-band
hue-distance BLEED-RING metric this experiment needs specifically.

Why a bespoke bleed metric: the abshape verdict (2026-07-09) found the shared leak gate
under-counts residue — it only samples a narrow interior window per control and misses the
thin coloured RING/bezel around a socket or button that is visible at full-res and is exactly
the "ZERO RESIDUE" defect the prompt bans. So for THIS experiment (which is specifically about
whether guide-colour bleed happens at all) we measure the perimeter band around every control's
device bbox — inner edge to a small outward margin — for hue-proximity to that control's own
guide key, independent of extract12's/genskin's own leak gate. This is the axis the hypothesis
is actually about.

Also cuts full-res, 2x-upscaled, LABELED crops per control (every button + every sprite/region,
not just vol/seek/shuffle — abshape found button-ring bleed too) for human/VLM review.

Usage: python3 score_twoimg.py   (no args — walks GENS below)
Writes twoimg/scores.json + per-gen crop-<control>.png + bleedring.json (folded into scores.json).
"""
import os, sys, json, subprocess, colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)

THEMES = ["fa-pod", "wc-goldshield"]
SEEDS = [121, 134]
ARMS = ["control", "treat"]

BAND_FRAC = 0.14      # perimeter band width, as a fraction of the control's own bbox size
HUE_TOL = 16           # degrees (0-255 space) hue tolerance vs the guide key
SAT_FLOOR, VAL_FLOOR = 60, 70


def bleed_ring_pct(paint_hsv, bbox, key_rgb, W, H):
    """Fraction of the perimeter BAND around bbox (outer expand, excluding the interior) whose
    hue is close to key_rgb's hue at reasonable sat/val. bbox is fractional [x,y,w,h] of the
    full paint canvas (extract12's device bbox convention)."""
    x, y, w, h = bbox
    mx, my = w * BAND_FRAC, h * BAND_FRAC
    ox0, oy0 = max(0.0, x - mx), max(0.0, y - my)
    ox1, oy1 = min(1.0, x + w + mx), min(1.0, y + h + my)
    X0, Y0, X1, Y1 = int(ox0 * W), int(oy0 * H), int(ox1 * W), int(oy1 * H)
    if X1 <= X0 or Y1 <= Y0: return 0.0, 0
    win = paint_hsv[Y0:Y1, X0:X1]
    # interior mask to exclude (in local window coords)
    ix0, iy0 = int((x - ox0) * W) if x >= ox0 else 0, int((y - oy0) * H) if y >= oy0 else 0
    ix1, iy1 = int((x + w - ox0) * W), int((y + h - oy0) * H)
    interior = np.zeros(win.shape[:2], dtype=bool)
    interior[max(0, iy0):max(0, iy1), max(0, ix0):max(0, ix1)] = True
    band = ~interior
    kh = int(colorsys.rgb_to_hsv(*[v / 255 for v in key_rgb])[0] * 255)
    hd = np.minimum(np.abs(win[..., 0].astype(int) - kh), 255 - np.abs(win[..., 0].astype(int) - kh))
    hit = band & (hd < HUE_TOL) & (win[..., 1] > SAT_FLOOR) & (win[..., 2] > VAL_FLOOR)
    n_band = int(band.sum())
    return (100.0 * int(hit.sum()) / n_band if n_band else 0.0), n_band


def label_crop(img, text):
    img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    pad = 6
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:
        font = ImageFont.load_default()
    tw = d.textlength(text, font=font) if hasattr(d, "textlength") else len(text) * 11
    d.rectangle([0, 0, tw + pad * 2, 30], fill=(0, 0, 0, 200))
    d.text((pad, 4), text, fill=(255, 255, 80), font=font)
    return img


scores = {}
for theme in THEMES:
    for seed in SEEDS:
        for arm in ARMS:
            tag = f"{theme}-{arm}-{seed}"
            d = os.path.join(HERE, f"assets-twoimg-{tag}")
            if not os.path.exists(os.path.join(d, "paint.png")):
                print(f"[{tag}] no paint.png -- skipping"); continue
            # resume-safe: extract12 is deterministic on the same paint/mask — skip the ~60s
            # rerun when a completed extract.log (with a GATE line) already exists
            elog = os.path.join(d, "extract.log")
            if not (os.path.exists(elog) and "[GATE]" in open(elog).read()):
                p = subprocess.run([sys.executable, os.path.join(GEN12, "extract12.py"), d],
                                    capture_output=True, text=True)
                open(elog, "w").write(p.stdout + p.stderr)
            regions = json.load(open(os.path.join(d, "regions.json")))
            gate = regions.get("gate", {})
            res = json.load(open(os.path.join(d, "results.json")))
            KEYS = {k: tuple(v) for k, v in res["keys"].items()}
            regs = regions.get("regions", {})

            paint = Image.open(os.path.join(d, "paint.png")).convert("RGB")
            W, H = paint.size
            paint_hsv = np.asarray(paint.convert("HSV")).astype(int)

            bleed = {}
            PAD = 0.35
            for name in KEYS:
                bbox = (regs.get(name) or {}).get("device")
                if not bbox:
                    continue
                pct, nband = bleed_ring_pct(paint_hsv, bbox, KEYS[name], W, H)
                bleed[name] = round(pct, 4)
                bx, by, bw, bh = bbox
                px, py = bw * PAD, bh * PAD
                x0 = int(max(0, (bx - px)) * W); x1 = int(min(1, bx + bw + px) * W)
                y0 = int(max(0, (by - py)) * H); y1 = int(min(1, by + bh + py) * H)
                if x1 <= x0 or y1 <= y0: continue
                c = paint.crop((x0, y0, x1, y1))
                c = c.resize((c.width * 2, c.height * 2), Image.LANCZOS)
                c = label_crop(c, f"{name} ({res.get('roles', {}).get(name, '?')})")
                c.save(os.path.join(d, f"crop-{name}.png"))

            worst = max(bleed.items(), key=lambda kv: kv[1]) if bleed else ("none", 0.0)
            scores[tag] = {
                "theme": theme, "arm": arm, "seed": seed,
                "leak_pct": round(100 * (res.get("leak") or 0), 4),
                "empty_ok": gate.get("empty_ok"),
                "controls": gate.get("controls"), "controls_total": gate.get("controls_total"),
                "missing": gate.get("missing"), "seek_cov": gate.get("seek_cov"),
                "reasons": gate.get("reasons"), "dims": res.get("dims"),
                "bleed_ring_pct": bleed,
                "bleed_ring_worst": {"control": worst[0], "pct": worst[1]},
            }
            print(f"[{tag}] leak={scores[tag]['leak_pct']}% empty_ok={scores[tag]['empty_ok']} "
                  f"controls={scores[tag]['controls']}/{scores[tag]['controls_total']} "
                  f"bleed-ring worst={worst[0]}={worst[1]:.3f}%")

json.dump(scores, open(os.path.join(HERE, "scores.json"), "w"), indent=1)
print("-> scores.json")
