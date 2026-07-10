#!/usr/bin/env python3
"""score_ab — run extract12 (pass 1, no matte) on each abshape gen, collect scores, cut socket crops.

Per gen: leak%% (from genskin_ab's gate, results.json), extract12 emptiness gate + controls
detected /10, plus close-up crops of the vol/seek/shuffle sockets for the index.html grid.
Writes abshape/scores.json.

Round-aware: round 1 (theme fa-pod) kept its original bare dirname/tag
(assets-abshape-<cond>-<seed>, scores key "<cond>-<seed>") for back-compat with
already-scored assets. Any additional theme (round 2+) is dirname/tag-prefixed with its
theme id (assets-abshape-<theme>-<cond>-<seed>, scores key "<theme>-<cond>-<seed>") so
multiple themes' same seeds coexist without collision. See genskin_ab.py's matching OUT
dirname logic.
"""
import os, sys, json, subprocess, re
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
ROUNDS = [
    (None, [("A", 121), ("A", 134), ("B", 121), ("B", 134)]),             # round 1: fa-pod
    ("wc-goldshield", [("A", 121), ("A", 134), ("B", 121), ("B", 134)]),  # round 2
]

scores = {}
for theme, RUNS in ROUNDS:
    for cond, seed in RUNS:
        tag = f"{cond.lower()}-{seed}" if theme is None else f"{theme}-{cond.lower()}-{seed}"
        d = os.path.join(HERE, f"assets-abshape-{tag}")
        if not os.path.exists(os.path.join(d, "paint.png")):
            print(f"[{tag}] no paint.png — skipping"); continue
        # extract12 pass 1 (no matte / no biref)
        p = subprocess.run([sys.executable, os.path.join(GEN12, "extract12.py"), d],
                           capture_output=True, text=True)
        log = p.stdout + p.stderr
        open(os.path.join(d, "extract.log"), "w").write(log)
        regions = json.load(open(os.path.join(d, "regions.json")))
        gate = regions.get("gate", {})
        res = json.load(open(os.path.join(d, "results.json")))
        # per-socket bright-interior fractions from the emptiness gate lines
        empt = dict(re.findall(r"^  (\w+)\s+bright-interior\s+([\d.]+)%", log, re.M))
        scores[tag] = {
            "theme": theme or "fa-pod", "cond": cond, "seed": seed,
            "leak_pct": round(100 * (res.get("leak") or 0), 4),
            "empty_ok": gate.get("empty_ok"),
            "empt_interior_pct": {k: float(v) for k, v in empt.items()},
            "controls": gate.get("controls"), "controls_total": gate.get("controls_total"),
            "missing": gate.get("missing"), "seek_cov": gate.get("seek_cov"),
            "reasons": gate.get("reasons"), "dims": res.get("dims"),
        }
        # crops: vol/seek/shuffle sockets from paint.png, using extract12's DETECTED device
        # bbox (regions.json regions[key].device, frac-of-full-paint-canvas) — NOT the raw
        # template fraction. The model freely rearranges the whole device per generation
        # (see per-gen device bboxes in regions.json vs the fixed template coord), so a crop
        # from the static template lands on the wrong control; the detected bbox is what
        # actually tracks where extract12 (and hence the real pipeline) found each control
        # on THIS paint.
        paint = Image.open(os.path.join(d, "paint.png")).convert("RGB")
        W, H = paint.size
        regs = regions.get("regions", {})
        PAD = 0.35  # fractional padding around the detected bbox, each side
        for name in ("vol", "seek", "shuffle"):
            bbox = (regs.get(name) or {}).get("device")
            if not bbox:
                continue
            bx, by, bw, bh = bbox
            px, py = bw * PAD, bh * PAD
            x0 = int((bx - px) * W); x1 = int((bx + bw + px) * W)
            y0 = int((by - py) * H); y1 = int((by + bh + py) * H)
            c = paint.crop((max(0, x0), max(0, y0), min(W, x1), min(H, y1)))
            if c.width == 0 or c.height == 0:
                continue
            c = c.resize((c.width * 2, c.height * 2), Image.LANCZOS)
            c.save(os.path.join(d, f"crop-{name}.png"))
        print(f"[{tag}] leak={scores[tag]['leak_pct']}% empty_ok={scores[tag]['empty_ok']} "
              f"controls={scores[tag]['controls']}/{scores[tag]['controls_total']} "
              f"missing={scores[tag]['missing']}")

json.dump(scores, open(os.path.join(HERE, "scores.json"), "w"), indent=1)
print("-> scores.json")
