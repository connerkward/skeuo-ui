#!/usr/bin/env python3
"""score_jsonspec — run extract12.py (pass 1) + the established gen12 metrics on every
jsonspec gen, reusing PROVEN code (not reinvented):
  - extract12.py gates: emptiness, leak, controls-found, region-misplacement, seek coverage
    (subprocess, identical invocation to twoimg/score_twoimg.py).
  - bleed_ring_pct: perimeter-band guide-hue residue metric, imported from
    twoimg/roster_audit.py — itself a stated-verbatim copy of twoimg/score_twoimg.py's
    metric — so numbers are directly comparable across experiments. (roster_audit is
    imported INSTEAD of score_twoimg because score_twoimg.py has an unguarded top-level
    scoring loop: importing it executes a full twoimg re-score and rewrites twoimg's
    git-tracked regions.json files — hit live on this experiment's first scoring run,
    reverted with git checkout. Note roster_audit's copy returns pct only, not
    (pct, n_band).)
  - drift_table: authored-template-centre vs detected-device-centre drift, imported
    verbatim from twoimg/roster_audit.py (the roster-audit drift method the task calls for).

Usage: python3 score_jsonspec.py   (no args — walks the fixed 2x2x2 matrix)
Writes jsonspec/scores.json + per-gen crop-<control>.png.
"""
import os, sys, json, subprocess, colorsys, importlib.util
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
TWOIMG = os.path.join(GEN12, "twoimg")


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


RA = _load("roster_audit", os.path.join(TWOIMG, "roster_audit.py"))   # bleed_ring_pct + drift_table


def label_crop(img, text):
    """Verbatim copy of twoimg/score_twoimg.py:label_crop (that module can't be imported —
    unguarded top-level scoring loop; see docstring)."""
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

THEMES = ["wc-goldshield", "fa-pod"]
SEEDS = [121, 134]
ARMS = ["control", "treat"]
ALL_CTRLS = ["playpause", "prev", "next", "repeat", "queue", "vol", "seek", "shuffle",
             "visualizer", "album_art"]


def tag(theme, arm, seed): return f"{theme}-{arm}-{seed}"


def score_one(theme, arm, seed):
    t = tag(theme, arm, seed)
    d = os.path.join(HERE, f"assets-jsonspec-{t}")
    if not os.path.exists(os.path.join(d, "paint.png")):
        print(f"[{t}] no paint.png -- skipping"); return None
    elog = os.path.join(d, "extract.log")
    if not (os.path.exists(elog) and "[GATE]" in open(elog).read()):
        p = subprocess.run([sys.executable, os.path.join(GEN12, "extract12.py"), d],
                            capture_output=True, text=True)
        open(elog, "w").write(p.stdout + p.stderr)
    regions = json.load(open(os.path.join(d, "regions.json")))
    gate = regions.get("gate", {})
    res = json.load(open(os.path.join(d, "results.json")))
    KEYS = {k: tuple(v) for k, v in res["keys"].items()}
    template = regions.get("template") or res.get("template") or {}
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
        pct = RA.bleed_ring_pct(paint_hsv, bbox, KEYS[name], W, H)
        bleed[name] = round(pct, 4)
        bx, by, bw, bh = bbox
        px, py = bw * PAD, bh * PAD
        x0 = int(max(0, (bx - px)) * W); x1 = int(min(1, bx + bw + px) * W)
        y0 = int(max(0, (by - py)) * H); y1 = int(min(1, by + bh + py) * H)
        if x1 <= x0 or y1 <= y0: continue
        c = paint.crop((x0, y0, x1, y1)); c = c.resize((c.width * 2, c.height * 2), Image.LANCZOS)
        c = label_crop(c, f"{name} ({res.get('roles', {}).get(name, '?')})")
        c.save(os.path.join(d, f"crop-{name}.png"))

    dt = RA.drift_table(template, regs, W, H) if template else {}
    drift_px = {k: round(v[0], 1) for k, v in dt.items()}
    mean_drift = round(float(np.mean(list(drift_px.values()))), 1) if drift_px else None

    worst = max(bleed.items(), key=lambda kv: kv[1]) if bleed else ("none", 0.0)
    out = {
        "theme": theme, "arm": arm, "seed": seed,
        "leak_pct": round(100 * (res.get("leak") or 0), 4),
        "empty_ok": gate.get("empty_ok"),
        "controls": gate.get("controls"), "controls_total": gate.get("controls_total"),
        "missing": gate.get("missing"), "seek_cov": gate.get("seek_cov"),
        "region_misplaced": [r for r in gate.get("reasons", []) if r.startswith("region-misplaced")],
        "gate_pass": gate.get("PASS"), "reasons": gate.get("reasons"), "dims": res.get("dims"),
        "prompt_len": res.get("prompt_len"),
        "bleed_ring_pct": bleed, "bleed_ring_worst": {"control": worst[0], "pct": worst[1]},
        "mean_bleed_pct": round(float(np.mean(list(bleed.values()))), 4) if bleed else None,
        "drift_px": drift_px, "mean_drift_px": mean_drift,
    }
    print(f"[{t}] gate={'PASS' if out['gate_pass'] else 'FAIL'} leak={out['leak_pct']}% "
          f"controls={out['controls']}/{out['controls_total']} mean_bleed={out['mean_bleed_pct']}% "
          f"mean_drift={out['mean_drift_px']}px")
    return out


def main():
    scores = {}
    for theme in THEMES:
        for seed in SEEDS:
            for arm in ARMS:
                r = score_one(theme, arm, seed)
                if r: scores[tag(theme, arm, seed)] = r
    json.dump(scores, open(os.path.join(HERE, "scores.json"), "w"), indent=1)
    print(f"-> scores.json ({len(scores)} gens)")


if __name__ == "__main__":
    main()
